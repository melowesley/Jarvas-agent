<#
.SYNOPSIS
    Ferramenta de validacao de sincronizacao e readiness do Jarvas v0.5.0.

.DESCRIPTION
    Executa validacoes estruturais, Git, release e opcionalmente testes,
    gerando um relatorio no formato escolhido (txt, json, md).
    Compativel com Windows PowerShell 5.1+ e PowerShell 7+.

.PARAMETER BaseRef
    Referencia Git base para comparacao. Default: origin/main.

.PARAMETER RunTests
    Se informado, executa pytest tests/ -v e captura resultado.

.PARAMETER OutputFormat
    Formato do relatorio gerado: txt (padrao), json ou md.

.PARAMETER FailOnWarnings
    Se informado, encerra com codigo 1 mesmo quando existem apenas avisos.

.EXAMPLE
    .\VALIDAR_SINCRONIZACAO.ps1
    .\VALIDAR_SINCRONIZACAO.ps1 -RunTests -OutputFormat md
    .\VALIDAR_SINCRONIZACAO.ps1 -BaseRef origin/develop -FailOnWarnings -OutputFormat json
#>

[CmdletBinding()]
param(
    [string]$BaseRef = "origin/main",
    [switch]$RunTests,
    [ValidateSet("txt","json","md")]
    [string]$OutputFormat = "txt",
    [switch]$FailOnWarnings
)

# ---------------------------------------------------------------------------
# Compatibilidade PS 5.1 / PS 7+
# ---------------------------------------------------------------------------
$ErrorActionPreference = "Continue"
if ($PSVersionTable.PSVersion.Major -ge 7) {
    Set-Variable -Name PSNativeCommandUseErrorActionPreference `
        -Value $false -Scope Script -ErrorAction SilentlyContinue
}

# ---------------------------------------------------------------------------
# Configuracao global
# ---------------------------------------------------------------------------
$RepoPath      = $PSScriptRoot
$Timestamp     = Get-Date -Format "yyyyMMdd_HHmmss"
$ScriptStart   = Get-Date
$TargetVersion = "0.5.0"

# Enhanced Git validation
$GitValidation = [ordered]@{
    branch_status = $null
    ahead_behind  = $null
    conflicts     = $null
    worktree      = $null
    diff_vs_base  = $null
}

$ReportExt = switch ($OutputFormat) {
    "json" { "json" }
    "md"   { "md"   }
    default { "txt" }
}
$ReportFile = Join-Path $RepoPath "VALIDACAO_RESULTADO_${Timestamp}.${ReportExt}"

# ---------------------------------------------------------------------------
# Estrutura de dados do relatorio
# ---------------------------------------------------------------------------
$Report = [ordered]@{
    meta = [ordered]@{
        tool             = "VALIDAR_SINCRONIZACAO.ps1"
        version_target   = $TargetVersion
        base_ref         = $BaseRef
        run_tests        = [bool]$RunTests
        output_format    = $OutputFormat
        fail_on_warnings = [bool]$FailOnWarnings
        timestamp        = (Get-Date -Format "dd/MM/yyyy HH:mm:ss")
        ps_version       = $PSVersionTable.PSVersion.ToString()
        repo_path        = $RepoPath
    }
    sections = [ordered]@{
        estrutural = [ordered]@{ items = @(); score = 0; total = 0 }
        hygiene    = [ordered]@{ items = @() }
        git        = [ordered]@{
            items = @()
            validation = $GitValidation
        }
        release    = [ordered]@{ items = @() }
        tests      = [ordered]@{ items = @(); ran = $false }
    }
    summary = [ordered]@{
        warnings  = 0
        criticals = 0
        status    = ""
        duration  = ""
        exit_code = 0
    }
}

$script:Warnings  = 0
$script:Criticals = 0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function New-ReportEntry {
    param([string]$Level, [string]$Message, [string]$Detail = "")
    return [ordered]@{ level = $Level; message = $Message; detail = $Detail }
}

function Invoke-Git {
    param([string[]]$Arguments)
    try {
        $output   = & git @Arguments 2>&1
        $exitCode = $LASTEXITCODE
        $text     = ($output | ForEach-Object { "$_" }) -join "`n"
        return [pscustomobject]@{ Text = $text.Trim(); ExitCode = $exitCode }
    } catch {
        return [pscustomobject]@{ Text = ""; ExitCode = -1 }
    }
}

function Get-GitBranchStatus {
    param([string]$BaseRef)
    $status = [ordered]@{
        current_branch = $null
        ahead_behind   = $null
        conflicts      = $null
        worktree       = $null
        diff_vs_base   = $null
    }

    # Get current branch
    $branchResult = Invoke-Git -Arguments @("rev-parse", "--abbrev-ref", "HEAD")
    $status.current_branch = if ($branchResult.ExitCode -eq 0) { $branchResult.Text } else { "<desconhecida>" }

    # Get ahead/behind count
    $abResult = Invoke-Git -Arguments @("rev-list", "--left-right", "--count", "${BaseRef}...HEAD")
    if ($abResult.ExitCode -eq 0 -and $abResult.Text -match '^\d+\s+\d+$') {
        $parts  = $abResult.Text -split '\s+'
        $status.ahead_behind = @{
            behind = [int]$parts[0]
            ahead  = [int]$parts[1]
        }
    }

    # Check for conflicts
    $conflictFiles = @(
        Get-ChildItem -Path $RepoPath -Recurse -File -Filter "*.swp" `
            -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch "venv" }
    )
    $status.conflicts = @{
        swp_files = $conflictFiles.Count
        merge_head = Test-Path (Join-Path $RepoPath ".git" "MERGE_HEAD")
        rebase_active = (Test-Path (Join-Path $RepoPath ".git" "rebase-merge")) -or
                       (Test-Path (Join-Path $RepoPath ".git" "rebase-apply"))
    }

    # Check worktree status
    $statusResult = Invoke-Git -Arguments @("status", "--porcelain")
    if ($statusResult.ExitCode -eq 0) {
        $changedLines = @($statusResult.Text -split "`n" | Where-Object { $_.Trim() })
        $status.worktree = @{
            modified = $changedLines.Count
            preview = if ($changedLines.Count -gt 0) {
                ($changedLines | Select-Object -First 8) -join " | "
            } else { $null }
        }
    }

    # Check diff vs base
    $diffResult = Invoke-Git -Arguments @("diff", "--name-only", "${BaseRef}...HEAD")
    if ($diffResult.ExitCode -eq 0) {
        $diffFiles = @($diffResult.Text -split "`n" | Where-Object { $_.Trim() })
        $status.diff_vs_base = @{
            files = $diffFiles.Count
            preview = if ($diffFiles.Count -gt 0) {
                ($diffFiles | Select-Object -First 10) -join " | "
            } else { $null }
        }
    }

    return $status
}

function Get-RepositoryHygiene {
    $hygiene = [ordered]@{
        pycache_dirs = 0
        pyc_files    = 0
        pytest_tmp   = $null
        gitignore    = $null
    }

    # __pycache__ directories
    $pycacheDirs = @(
        Get-ChildItem -Path $RepoPath -Recurse -Directory -Filter "__pycache__" `
            -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch "venv" }
    )
    $hygiene.pycache_dirs = $pycacheDirs.Count

    # *.pyc files
    $pycFiles = @(
        Get-ChildItem -Path $RepoPath -Recurse -File -Filter "*.pyc" `
            -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch "venv" }
    )
    $hygiene.pyc_files = $pycFiles.Count

    # .pytest_tmp
    $pytestTmpPath = Join-Path $RepoPath ".pytest_tmp"
    if (Test-Path $pytestTmpPath) {
        $tmpItems = @(Get-ChildItem -Path $pytestTmpPath -Recurse -ErrorAction SilentlyContinue)
        $hygiene.pytest_tmp = @{
            exists = $true
            items = $tmpItems.Count
        }
    } else {
        $hygiene.pytest_tmp = @{
            exists = $false
            items = 0
        }
    }

    # .gitignore coverage
    $gitignorePath = Join-Path $RepoPath ".gitignore"
    if (Test-Path $gitignorePath) {
        $gitignoreContent = Get-Content $gitignorePath -Raw -ErrorAction SilentlyContinue
        $requiredPatterns = @("__pycache__", "*.pyc", ".pytest_cache", "*.egg-info")
        $missingPats = @()
        foreach ($pat in $requiredPatterns) {
            if ($gitignoreContent -notmatch [regex]::Escape($pat)) {
                $missingPats += $pat
            }
        }
        $hygiene.gitignore = @{
            exists = $true
            missing_patterns = $missingPats
            coverage_ok = ($missingPats.Count -eq 0)
        }
    } else {
        $hygiene.gitignore = @{
            exists = $false
            missing_patterns = $requiredPatterns
            coverage_ok = $false
        }
    }

    return $hygiene
}

function Get-ReleaseValidation {
    param([string]$TargetVersion)
    $release = [ordered]@{
        pyproject_version = $null
        version_match = $false
        critical_docs = $null
    }

    # Check pyproject.toml version
    $tomlPath = Join-Path $RepoPath "pyproject.toml"
    if (Test-Path $tomlPath) {
        try {
            $tomlContent = Get-Content $tomlPath -Raw -ErrorAction Stop
            if ($tomlContent -match 'version\s*=\s*["'']([0-9][0-9a-zA-Z.\-]*)["'']') {
                $foundVersion = $Matches[1]
                $release.pyproject_version = $foundVersion
                $release.version_match = ($foundVersion -eq $TargetVersion)
            } else {
                $release.pyproject_version = "NOT_FOUND"
            }
        } catch {
            $release.pyproject_version = "ERROR: $_"
        }
    } else {
        $release.pyproject_version = "MISSING"
    }

    # Check critical documents
    $criticalDocs = @(
        [pscustomobject]@{ Path = "docs\PLANO-v0.5.0-MULTIAGENTE.md"; Label = "Plano Multi-agente v0.5.0" }
        [pscustomobject]@{ Path = "docs\PLANO-MIGRACAO.md";            Label = "Plano de Migracao"         }
        [pscustomobject]@{ Path = "ANALISE_SINCRONIZACAO_v0.5.0.md";   Label = "Analise de Sincronizacao"  }
        [pscustomobject]@{ Path = "PROXIMOS_PASSOS.md";                Label = "Proximos Passos"            }
        [pscustomobject]@{ Path = "README.md";                         Label = "README principal"           }
        [pscustomobject]@{ Path = "LICENSE";                           Label = "Arquivo de Licenca"         }
        [pscustomobject]@{ Path = "CHANGELOG.md";                      Label = "CHANGELOG"                  }
    )

    $docStatus = @()
    foreach ($doc in $criticalDocs) {
        $dp = Join-Path $RepoPath $doc.Path
        $docStatus += [pscustomobject]@{
            path = $doc.Path
            label = $doc.Label
            exists = Test-Path $dp
        }
    }
    $release.critical_docs = $docStatus

    return $release
}

function Add-Item {
    param(
        [string]$Section,
        [string]$Level,
        [string]$Message,
        [string]$Detail = ""
    )
    $entry = New-ReportEntry -Level $Level -Message $Message -Detail $Detail
    $Report.sections[$Section].items += $entry

    switch ($Level) {
        "WARNING"  { $script:Warnings++;  Write-Host "  [AVISO]    $Message" -ForegroundColor Yellow }
        "CRITICAL" { $script:Criticals++; Write-Host "  [CRITICO]  $Message" -ForegroundColor Red }
        "OK"       {                       Write-Host "  [OK]       $Message" -ForegroundColor Green }
        default    {                       Write-Host "  [INFO]     $Message" -ForegroundColor Cyan }
    }
    if ($Detail -and $Detail.Trim()) {
        Write-Host "             > $Detail" -ForegroundColor DarkGray
    }
}

function Invoke-Git {
    param([string[]]$Arguments)
    try {
        $output   = & git @Arguments 2>&1
        $exitCode = $LASTEXITCODE
        $text     = ($output | ForEach-Object { "$_" }) -join "`n"
        return [pscustomobject]@{ Text = $text.Trim(); ExitCode = $exitCode }
    } catch {
        return [pscustomobject]@{ Text = ""; ExitCode = -1 }
    }
}

function Join-Lines {
    param([string[]]$Lines, [string]$Sep = " | ")
    return ($Lines -join $Sep)
}

# ---------------------------------------------------------------------------
# Cabecalho
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "=============================================================" -ForegroundColor Cyan
Write-Host "  Jarvas v$TargetVersion - Validacao de Sincronizacao e Readiness" -ForegroundColor Cyan
Write-Host "  Repositorio : $RepoPath"                                     -ForegroundColor Cyan
Write-Host "  BaseRef     : $BaseRef"                                      -ForegroundColor Cyan
Write-Host "  Formato     : $OutputFormat  | RunTests: $([bool]$RunTests)  | FailOnWarnings: $([bool]$FailOnWarnings)" -ForegroundColor Cyan
Write-Host "=============================================================" -ForegroundColor Cyan
Write-Host ""

# =============================================================================
# SECAO 1 - ESTRUTURAL
# =============================================================================
Write-Host "[1/5] Estrutura do Repositorio" -ForegroundColor Magenta

# Enhanced structural validation with additional checks
$StructChecks = @(
    [pscustomobject]@{ Path = "jarvas";                          Desc = "Diretorio principal jarvas/";      Critical = $true  }
    [pscustomobject]@{ Path = "jarvas\agents";                   Desc = "Modulo jarvas/agents/";            Critical = $false }
    [pscustomobject]@{ Path = "jarvas\managed";                  Desc = "Modulo jarvas/managed/";           Critical = $false }
    [pscustomobject]@{ Path = "jarvas\miners";                   Desc = "Modulo jarvas/miners/";            Critical = $false }
    [pscustomobject]@{ Path = "tests";                           Desc = "Diretorio tests/";                 Critical = $true  }
    [pscustomobject]@{ Path = "docs";                            Desc = "Diretorio docs/";                  Critical = $false }
    [pscustomobject]@{ Path = "pyproject.toml";                  Desc = "pyproject.toml";                   Critical = $true  }
    [pscustomobject]@{ Path = "README.md";                       Desc = "README.md";                        Critical = $false }
    [pscustomobject]@{ Path = ".gitignore";                      Desc = ".gitignore";                       Critical = $false }
    [pscustomobject]@{ Path = "jarvas\api.py";                   Desc = "jarvas/api.py";                    Critical = $true  }
    [pscustomobject]@{ Path = "jarvas\cli.py";                   Desc = "jarvas/cli.py";                    Critical = $true  }
    [pscustomobject]@{ Path = "jarvas\orchestrator.py";          Desc = "jarvas/orchestrator.py";           Critical = $true  }
    [pscustomobject]@{ Path = "jarvas\router.py";                Desc = "jarvas/router.py";                 Critical = $true  }
    [pscustomobject]@{ Path = "jarvas\managed\toolset.py";       Desc = "jarvas/managed/toolset.py";        Critical = $false }
    [pscustomobject]@{ Path = "jarvas\agents\supervisor.py";     Desc = "jarvas/agents/supervisor.py";      Critical = $false }
    [pscustomobject]@{ Path = "docs\PLANO-v0.5.0-MULTIAGENTE.md"; Desc = "docs/PLANO-v0.5.0-MULTIAGENTE.md"; Critical = $false }
    [pscustomobject]@{ Path = "docs\PLANO-MIGRACAO.md";          Desc = "docs/PLANO-MIGRACAO.md";           Critical = $false }
    [pscustomobject]@{ Path = "venv";                            Desc = "Ambiente virtual venv/";            Critical = $false }
    [pscustomobject]@{ Path = "requirements.txt";                Desc = "requirements.txt";                 Critical = $false }
    [pscustomobject]@{ Path = "setup.py";                        Desc = "setup.py";                         Critical = $false }
)

$StructChecks = @(
    [pscustomobject]@{ Path = "jarvas";                          Desc = "Diretorio principal jarvas/";      Critical = $true  }
    [pscustomobject]@{ Path = "jarvas\agents";                   Desc = "Modulo jarvas/agents/";            Critical = $false }
    [pscustomobject]@{ Path = "jarvas\managed";                  Desc = "Modulo jarvas/managed/";           Critical = $false }
    [pscustomobject]@{ Path = "jarvas\miners";                   Desc = "Modulo jarvas/miners/";            Critical = $false }
    [pscustomobject]@{ Path = "tests";                           Desc = "Diretorio tests/";                 Critical = $true  }
    [pscustomobject]@{ Path = "docs";                            Desc = "Diretorio docs/";                  Critical = $false }
    [pscustomobject]@{ Path = "pyproject.toml";                  Desc = "pyproject.toml";                   Critical = $true  }
    [pscustomobject]@{ Path = "README.md";                       Desc = "README.md";                        Critical = $false }
    [pscustomobject]@{ Path = ".gitignore";                      Desc = ".gitignore";                       Critical = $false }
    [pscustomobject]@{ Path = "jarvas\api.py";                   Desc = "jarvas/api.py";                    Critical = $true  }
    [pscustomobject]@{ Path = "jarvas\cli.py";                   Desc = "jarvas/cli.py";                    Critical = $true  }
    [pscustomobject]@{ Path = "jarvas\orchestrator.py";          Desc = "jarvas/orchestrator.py";           Critical = $true  }
    [pscustomobject]@{ Path = "jarvas\router.py";                Desc = "jarvas/router.py";                 Critical = $true  }
    [pscustomobject]@{ Path = "jarvas\managed\toolset.py";       Desc = "jarvas/managed/toolset.py";        Critical = $false }
    [pscustomobject]@{ Path = "jarvas\agents\supervisor.py";     Desc = "jarvas/agents/supervisor.py";      Critical = $false }
    [pscustomobject]@{ Path = "docs\PLANO-v0.5.0-MULTIAGENTE.md"; Desc = "docs/PLANO-v0.5.0-MULTIAGENTE.md"; Critical = $false }
    [pscustomobject]@{ Path = "docs\PLANO-MIGRACAO.md";          Desc = "docs/PLANO-MIGRACAO.md";           Critical = $false }
)

$structPass = 0
foreach ($chk in $StructChecks) {
    $fp = Join-Path $RepoPath $chk.Path
    if (Test-Path $fp) {
        Add-Item -Section "estrutural" -Level "OK" -Message $chk.Desc
        $structPass++
    } else {
        $lvl = if ($chk.Critical) { "CRITICAL" } else { "WARNING" }
        Add-Item -Section "estrutural" -Level $lvl -Message "$($chk.Desc) - NAO ENCONTRADO"
    }
}

$Report.sections.estrutural.score = $structPass
$Report.sections.estrutural.total = $StructChecks.Count
$pct = [math]::Round(($structPass / $StructChecks.Count) * 100)
Write-Host "  Score estrutural: $structPass/$($StructChecks.Count) ($pct%)" -ForegroundColor White
Write-Host ""

# =============================================================================
# SECAO 2 - HIGIENE
# =============================================================================
Write-Host "[2/5] Higiene do Repositorio" -ForegroundColor Magenta

$hygiene = Get-RepositoryHygiene

# __pycache__
if ($hygiene.pycache_dirs -gt 0) {
    Add-Item -Section "hygiene" -Level "WARNING" `
        -Message "$($hygiene.pycache_dirs) diretorio(s) __pycache__ fora de venv" `
        -Detail "Limpar: Remove-Item -Recurse (Get-ChildItem -Directory -Filter __pycache__ -Recurse | Where-Object { $_.FullName -notmatch 'venv' }).FullName"
} else {
    Add-Item -Section "hygiene" -Level "OK" -Message "Nenhum __pycache__ fora de venv"
}

# *.pyc
if ($hygiene.pyc_files -gt 0) {
    Add-Item -Section "hygiene" -Level "WARNING" `
        -Message "$($hygiene.pyc_files) arquivo(s) *.pyc rastreavel(is) fora de venv" `
        -Detail "Limpar: Remove-Item (Get-ChildItem -File -Filter *.pyc -Recurse | Where-Object { $_.FullName -notmatch 'venv' }).FullName"
} else {
    Add-Item -Section "hygiene" -Level "OK" -Message "Nenhum arquivo *.pyc fora de venv"
}

# .pytest_tmp
if ($hygiene.pytest_tmp.exists) {
    if ($hygiene.pytest_tmp.items -gt 0) {
        Add-Item -Section "hygiene" -Level "WARNING" `
            -Message ".pytest_tmp contem $($hygiene.pytest_tmp.items) artefato(s)" `
            -Detail "Limpar: Remove-Item -Recurse .pytest_tmp"
    } else {
        Add-Item -Section "hygiene" -Level "INFO" -Message ".pytest_tmp existe mas esta vazio"
    }
} else {
    Add-Item -Section "hygiene" -Level "OK" -Message "Sem artefatos .pytest_tmp"
}

# .gitignore coverage
if ($hygiene.gitignore.exists) {
    if ($hygiene.gitignore.coverage_ok) {
        Add-Item -Section "hygiene" -Level "OK" `
            -Message ".gitignore cobre os artefatos Python criticos"
    } else {
        Add-Item -Section "hygiene" -Level "WARNING" `
            -Message ".gitignore nao cobre: $($hygiene.gitignore.missing_patterns -join ', ')"
    }
} else {
    Add-Item -Section "hygiene" -Level "CRITICAL" -Message ".gitignore ausente"
}

# __pycache__
$pycacheDirs = @(
    Get-ChildItem -Path $RepoPath -Recurse -Directory -Filter "__pycache__" `
        -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch "venv" }
)
if ($pycacheDirs.Count -gt 0) {
    $detail = ($pycacheDirs.FullName | Select-Object -First 5) -join "; "
    Add-Item -Section "hygiene" -Level "WARNING" `
        -Message "$($pycacheDirs.Count) diretorio(s) __pycache__ fora de venv" `
        -Detail $detail
} else {
    Add-Item -Section "hygiene" -Level "OK" -Message "Nenhum __pycache__ fora de venv"
}

# *.pyc
$pycFilter = "*.pyc"
$pycFiles = @(
    Get-ChildItem -Path $RepoPath -Recurse -File -Filter $pycFilter `
        -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch "venv" }
)
if ($pycFiles.Count -gt 0) {
    $shortPaths = $pycFiles.FullName | Select-Object -First 5 |
        ForEach-Object { $_ -replace [regex]::Escape($RepoPath + "\"), "" }
    Add-Item -Section "hygiene" -Level "WARNING" `
        -Message "$($pycFiles.Count) arquivo(s) *.pyc rastreavel(is) fora de venv" `
        -Detail ($shortPaths -join "; ")
} else {
    Add-Item -Section "hygiene" -Level "OK" -Message "Nenhum arquivo *.pyc fora de venv"
}

# .pytest_tmp
$pytestTmpPath = Join-Path $RepoPath ".pytest_tmp"
if (Test-Path $pytestTmpPath) {
    $tmpItems = @(Get-ChildItem -Path $pytestTmpPath -Recurse -ErrorAction SilentlyContinue)
    if ($tmpItems.Count -gt 0) {
        Add-Item -Section "hygiene" -Level "WARNING" `
            -Message ".pytest_tmp contem $($tmpItems.Count) artefato(s)" `
            -Detail "Limpar: Remove-Item -Recurse .pytest_tmp"
    } else {
        Add-Item -Section "hygiene" -Level "INFO" -Message ".pytest_tmp existe mas esta vazio"
    }
} else {
    Add-Item -Section "hygiene" -Level "OK" -Message "Sem artefatos .pytest_tmp"
}

# .pytest_cache
if (Test-Path (Join-Path $RepoPath ".pytest_cache")) {
    Add-Item -Section "hygiene" -Level "INFO" `
        -Message ".pytest_cache presente (normal; coberto pelo .gitignore)"
}

# .gitignore - cobertura
$gitignorePath = Join-Path $RepoPath ".gitignore"
if (Test-Path $gitignorePath) {
    $gitignoreContent = Get-Content $gitignorePath -Raw -ErrorAction SilentlyContinue
    $requiredPatterns = @("__pycache__", "*.pyc", ".pytest_cache", "*.egg-info")
    $missingPats = @()
    foreach ($pat in $requiredPatterns) {
        if ($gitignoreContent -notmatch [regex]::Escape($pat)) {
            $missingPats += $pat
        }
    }
    if ($missingPats.Count -gt 0) {
        Add-Item -Section "hygiene" -Level "WARNING" `
            -Message ".gitignore nao cobre: $($missingPats -join ', ')"
    } else {
        Add-Item -Section "hygiene" -Level "OK" `
            -Message ".gitignore cobre os artefatos Python criticos"
    }
} else {
    Add-Item -Section "hygiene" -Level "CRITICAL" -Message ".gitignore ausente"
}

Write-Host ""

# =============================================================================
# SECAO 3 - GIT
# =============================================================================
Write-Host "[3/5] Estado Git" -ForegroundColor Magenta

$gitAvailable = $null -ne (Get-Command git -ErrorAction SilentlyContinue)
$gitDirExists = Test-Path (Join-Path $RepoPath ".git")

if (-not $gitAvailable) {
    Add-Item -Section "git" -Level "CRITICAL" -Message "Git nao encontrado no PATH"
} elseif (-not $gitDirExists) {
    Add-Item -Section "git" -Level "CRITICAL" `
        -Message "Diretorio .git nao encontrado - nao e um repositorio Git"
} else {
    Add-Item -Section "git" -Level "OK" -Message "Repositorio Git detectado"

    # Enhanced Git validation
    $gitStatus = Get-GitBranchStatus -BaseRef $BaseRef
    $Report.sections.git.validation = $gitStatus

    # Branch current
    Add-Item -Section "git" -Level "INFO" -Message "Branch atual: $($gitStatus.current_branch)"

    # Ahead/behind
    if ($gitStatus.ahead_behind) {
        $behind = $gitStatus.ahead_behind.behind
        $ahead  = $gitStatus.ahead_behind.ahead
        Add-Item -Section "git" -Level "INFO" `
            -Message "Relacao com ${BaseRef}: behind=$behind | ahead=$ahead"
        if ($behind -gt 0) {
            Add-Item -Section "git" -Level "WARNING" `
                -Message "HEAD esta $behind commit(s) atras de ${BaseRef}" `
                -Detail  "Execute: git pull --rebase $BaseRef"
        }
        if ($ahead -gt 0) {
            Add-Item -Section "git" -Level "WARNING" `
                -Message "HEAD esta $ahead commit(s) a frente de ${BaseRef}" `
                -Detail  "Revisar antes de merge/release"
        }
        if ($behind -eq 0 -and $ahead -eq 0) {
            Add-Item -Section "git" -Level "OK" -Message "Branch sincronizado com ${BaseRef}"
        }
    } else {
        Add-Item -Section "git" -Level "WARNING" `
            -Message "Nao foi possivel comparar HEAD com ${BaseRef}" `
            -Detail  "Verifique: git remote -v"
    }

    # Conflicts
    if ($gitStatus.conflicts.swp_files -gt 0) {
        Add-Item -Section "git" -Level "WARNING" `
            -Message "$($gitStatus.conflicts.swp_files) arquivo(s) .swp fora de venv" `
            -Detail "Limpar: Remove-Item (Get-ChildItem -File -Filter *.swp -Recurse | Where-Object { $_.FullName -notmatch 'venv' }).FullName"
    }
    if ($gitStatus.conflicts.merge_head) {
        Add-Item -Section "git" -Level "CRITICAL" `
            -Message "MERGE_HEAD presente - merge pendente nao concluido" `
            -Detail  "Resolva ou execute: git merge --abort"
    } else {
        Add-Item -Section "git" -Level "OK" -Message "Sem merge pendente"
    }
    if ($gitStatus.conflicts.rebase_active) {
        Add-Item -Section "git" -Level "CRITICAL" `
            -Message "Rebase em andamento detectado" `
            -Detail  "Resolva ou execute: git rebase --abort"
    } else {
        Add-Item -Section "git" -Level "OK" -Message "Sem rebase em andamento"
    }

    # Worktree
    if ($gitStatus.worktree.modified -gt 0) {
        Add-Item -Section "git" -Level "WARNING" `
            -Message "Worktree com $($gitStatus.worktree.modified) arquivo(s) modificado(s)/nao-rastreado(s)" `
            -Detail  $gitStatus.worktree.preview
    } else {
        Add-Item -Section "git" -Level "OK" -Message "Worktree limpo"
    }

    # Diff vs base
    if ($gitStatus.diff_vs_base.files -gt 0) {
        Add-Item -Section "git" -Level "INFO" `
            -Message "$($gitStatus.diff_vs_base.files) arquivo(s) alterado(s) em ${BaseRef}...HEAD" `
            -Detail  $gitStatus.diff_vs_base.preview
    } else {
        Add-Item -Section "git" -Level "INFO" `
            -Message "Nenhuma diferenca de arquivo em ${BaseRef}...HEAD"
    }
}

$gitAvailable = $null -ne (Get-Command git -ErrorAction SilentlyContinue)
$gitDirExists = Test-Path (Join-Path $RepoPath ".git")

if (-not $gitAvailable) {
    Add-Item -Section "git" -Level "CRITICAL" -Message "Git nao encontrado no PATH"
} elseif (-not $gitDirExists) {
    Add-Item -Section "git" -Level "CRITICAL" `
        -Message "Diretorio .git nao encontrado - nao e um repositorio Git"
} else {
    Add-Item -Section "git" -Level "OK" -Message "Repositorio Git detectado"

    # Branch atual
    $branchResult = Invoke-Git -Arguments @("rev-parse", "--abbrev-ref", "HEAD")
    $currentBranch = if ($branchResult.ExitCode -eq 0) { $branchResult.Text } else { "<desconhecida>" }
    Add-Item -Section "git" -Level "INFO" -Message "Branch atual: $currentBranch"

    # Ahead / Behind
    $abResult = Invoke-Git -Arguments @("rev-list", "--left-right", "--count", "${BaseRef}...HEAD")
    if ($abResult.ExitCode -eq 0 -and $abResult.Text -match '^\d+\s+\d+$') {
        $parts  = $abResult.Text -split '\s+'
        $behind = [int]$parts[0]
        $ahead  = [int]$parts[1]
        Add-Item -Section "git" -Level "INFO" `
            -Message "Relacao com ${BaseRef}: behind=$behind | ahead=$ahead"
        if ($behind -gt 0) {
            Add-Item -Section "git" -Level "WARNING" `
                -Message "HEAD esta $behind commit(s) atras de ${BaseRef}" `
                -Detail  "Execute: git pull --rebase $BaseRef"
        }
        if ($ahead -gt 0) {
            Add-Item -Section "git" -Level "WARNING" `
                -Message "HEAD esta $ahead commit(s) a frente de ${BaseRef}" `
                -Detail  "Revisar antes de merge/release"
        }
        if ($behind -eq 0 -and $ahead -eq 0) {
            Add-Item -Section "git" -Level "OK" -Message "Branch sincronizado com ${BaseRef}"
        }
    } else {
        Add-Item -Section "git" -Level "WARNING" `
            -Message "Nao foi possivel comparar HEAD com ${BaseRef}" `
            -Detail  "Verifique: git remote -v"
    }

    # git status --porcelain
    $statusResult = Invoke-Git -Arguments @("status", "--porcelain")
    if ($statusResult.ExitCode -eq 0) {
        $changedLines = @($statusResult.Text -split "`n" | Where-Object { $_.Trim() })
        if ($changedLines.Count -gt 0) {
            $preview = ($changedLines | Select-Object -First 8) -join " | "
            Add-Item -Section "git" -Level "WARNING" `
                -Message "Worktree com $($changedLines.Count) arquivo(s) modificado(s)/nao-rastreado(s)" `
                -Detail  $preview
        } else {
            Add-Item -Section "git" -Level "OK" -Message "Worktree limpo"
        }
    } else {
        Add-Item -Section "git" -Level "WARNING" -Message "Falha ao ler git status --porcelain"
    }

    # Arquivos alterados entre BaseRef e HEAD
    $diffResult = Invoke-Git -Arguments @("diff", "--name-only", "${BaseRef}...HEAD")
    if ($diffResult.ExitCode -eq 0) {
        $diffFiles = @($diffResult.Text -split "`n" | Where-Object { $_.Trim() })
        if ($diffFiles.Count -gt 0) {
            $preview = ($diffFiles | Select-Object -First 10) -join " | "
            Add-Item -Section "git" -Level "INFO" `
                -Message "$($diffFiles.Count) arquivo(s) alterado(s) em ${BaseRef}...HEAD" `
                -Detail  $preview
        } else {
            Add-Item -Section "git" -Level "INFO" `
                -Message "Nenhuma diferenca de arquivo em ${BaseRef}...HEAD"
        }
    }

    # Estados anomalos
    $gitDir = Join-Path $RepoPath ".git"

    if (Test-Path (Join-Path $gitDir "MERGE_HEAD")) {
        Add-Item -Section "git" -Level "CRITICAL" `
            -Message "MERGE_HEAD presente - merge pendente nao concluido" `
            -Detail  "Resolva ou execute: git merge --abort"
    } else {
        Add-Item -Section "git" -Level "OK" -Message "Sem merge pendente"
    }

    if (Test-Path (Join-Path $gitDir "CHERRY_PICK_HEAD")) {
        Add-Item -Section "git" -Level "CRITICAL" `
            -Message "CHERRY_PICK_HEAD presente - cherry-pick pendente" `
            -Detail  "Resolva ou execute: git cherry-pick --abort"
    }

    $rebaseActive = (Test-Path (Join-Path $gitDir "rebase-merge")) -or
                    (Test-Path (Join-Path $gitDir "rebase-apply"))
    if ($rebaseActive) {
        Add-Item -Section "git" -Level "CRITICAL" `
            -Message "Rebase em andamento detectado" `
            -Detail  "Resolva ou execute: git rebase --abort"
    } else {
        Add-Item -Section "git" -Level "OK" -Message "Sem rebase em andamento"
    }

    $mainLock = Join-Path $gitDir "index.lock"
    if (Test-Path $mainLock) {
        Add-Item -Section "git" -Level "CRITICAL" `
            -Message "index.lock presente no repositorio principal" `
            -Detail  "Se seguro remova: del .git\index.lock"
    } else {
        Add-Item -Section "git" -Level "OK" -Message "Sem index.lock no repositorio principal"
    }

    $subLocks = @(
        Get-ChildItem -Path $RepoPath -Recurse -File -Filter "index.lock" `
            -ErrorAction SilentlyContinue |
        Where-Object { $_.DirectoryName -match "\.git" -and $_.FullName -ne $mainLock }
    )
    if ($subLocks.Count -gt 0) {
        Add-Item -Section "git" -Level "WARNING" `
            -Message "$($subLocks.Count) index.lock(s) residual(is) em subrepositorio(s)" `
            -Detail  ($subLocks.FullName -join "; ")
    }

    $swpFilter = "*.swp"
    $swpFiles  = @(Get-ChildItem -Path $gitDir -Filter $swpFilter -ErrorAction SilentlyContinue)
    if ($swpFiles.Count -gt 0) {
        Add-Item -Section "git" -Level "WARNING" `
            -Message "$($swpFiles.Count) arquivo(s) .swp em .git: $($swpFiles.Name -join ', ')"
    } else {
        Add-Item -Section "git" -Level "OK" -Message "Sem arquivos .swp em .git"
    }
}

Write-Host ""

# =============================================================================
# SECAO 4 - RELEASE / VERSAO
# =============================================================================
Write-Host "[4/5] Release e Versao" -ForegroundColor Magenta

$release = Get-ReleaseValidation -TargetVersion $TargetVersion
$Report.sections.release.validation = $release

# Check pyproject.toml version
if ($release.pyproject_version -eq "MISSING") {
    Add-Item -Section "release" -Level "CRITICAL" -Message "pyproject.toml nao encontrado"
} elseif ($release.pyproject_version -eq "NOT_FOUND") {
    Add-Item -Section "release" -Level "CRITICAL" `
        -Message "Campo 'version' nao encontrado no pyproject.toml"
} elseif ($release.pyproject_version -like "ERROR:*") {
    Add-Item -Section "release" -Level "CRITICAL" `
        -Message "Erro ao ler pyproject.toml: $($release.pyproject_version -replace 'ERROR: ')"
} else {
    Add-Item -Section "release" -Level "INFO" `
        -Message "Versao declarada no pyproject.toml: $($release.pyproject_version)"
    if ($release.version_match) {
        Add-Item -Section "release" -Level "OK" `
            -Message "Versao alinhada com a target v$TargetVersion"
    } else {
        Add-Item -Section "release" -Level "CRITICAL" `
            -Message "Versao '$($release.pyproject_version)' difere da target '$TargetVersion'" `
            -Detail  "Ajuste [project].version no pyproject.toml"
    }
}

# Check critical documents
foreach ($doc in $release.critical_docs) {
    if ($doc.exists) {
        Add-Item -Section "release" -Level "OK" -Message "Documento presente: $($doc.label)"
    } else {
        Add-Item -Section "release" -Level "WARNING" `
            -Message "Documento ausente: $($doc.label)" -Detail $doc.path
    }
}

$tomlPath = Join-Path $RepoPath "pyproject.toml"
if (Test-Path $tomlPath) {
    try {
        $tomlContent = Get-Content $tomlPath -Raw -ErrorAction Stop
        if ($tomlContent -match 'version\s*=\s*["'']([0-9][0-9a-zA-Z.\-]*)["'']') {
            $foundVersion = $Matches[1]
            Add-Item -Section "release" -Level "INFO" `
                -Message "Versao declarada no pyproject.toml: $foundVersion"
            if ($foundVersion -eq $TargetVersion) {
                Add-Item -Section "release" -Level "OK" `
                    -Message "Versao alinhada com a target v$TargetVersion"
            } else {
                Add-Item -Section "release" -Level "CRITICAL" `
                    -Message "Versao '$foundVersion' difere da target '$TargetVersion'" `
                    -Detail  "Ajuste [project].version no pyproject.toml"
            }
        } else {
            Add-Item -Section "release" -Level "CRITICAL" `
                -Message "Campo 'version' nao encontrado no pyproject.toml"
        }
    } catch {
        Add-Item -Section "release" -Level "CRITICAL" `
            -Message "Erro ao ler pyproject.toml: $_"
    }
} else {
    Add-Item -Section "release" -Level "CRITICAL" -Message "pyproject.toml nao encontrado"
}

$criticalDocs = @(
    [pscustomobject]@{ Path = "docs\PLANO-v0.5.0-MULTIAGENTE.md"; Label = "Plano Multi-agente v0.5.0" }
    [pscustomobject]@{ Path = "docs\PLANO-MIGRACAO.md";            Label = "Plano de Migracao"         }
    [pscustomobject]@{ Path = "ANALISE_SINCRONIZACAO_v0.5.0.md";   Label = "Analise de Sincronizacao"  }
    [pscustomobject]@{ Path = "PROXIMOS_PASSOS.md";                Label = "Proximos Passos"            }
    [pscustomobject]@{ Path = "README.md";                         Label = "README principal"           }
    [pscustomobject]@{ Path = "LICENSE";                           Label = "Arquivo de Licenca"         }
    [pscustomobject]@{ Path = "CHANGELOG.md";                      Label = "CHANGELOG"                  }
)

foreach ($doc in $criticalDocs) {
    $dp = Join-Path $RepoPath $doc.Path
    if (Test-Path $dp) {
        Add-Item -Section "release" -Level "OK" -Message "Documento presente: $($doc.Label)"
    } else {
        Add-Item -Section "release" -Level "WARNING" `
            -Message "Documento ausente: $($doc.Label)" -Detail $doc.Path
    }
}

Write-Host ""

# =============================================================================
# SECAO 5 - TESTES
# =============================================================================
Write-Host "[5/5] Suite de Testes" -ForegroundColor Magenta

$testDir   = Join-Path $RepoPath "tests"
$testFiles = @(Get-ChildItem -Path $testDir -Filter "test_*.py" -ErrorAction SilentlyContinue)
Add-Item -Section "tests" -Level "INFO" `
    -Message "$($testFiles.Count) arquivo(s) test_*.py encontrado(s) em tests/"

if ($testFiles.Count -gt 0) {
    Add-Item -Section "tests" -Level "OK" -Message "Suite de testes detectada"
} else {
    Add-Item -Section "tests" -Level "WARNING" -Message "Nenhum arquivo test_*.py encontrado"
}

if ($RunTests) {
    $Report.sections.tests.ran = $true
    $pytestAvail = $null -ne (Get-Command pytest -ErrorAction SilentlyContinue)
    if (-not $pytestAvail) {
        Add-Item -Section "tests" -Level "WARNING" `
            -Message "pytest nao encontrado no PATH - tentando via 'python -m pytest'" `
            -Detail  "Instale: pip install pytest"
    }

    Write-Host ""
    Write-Host "  Executando: pytest tests/ -v ..." -ForegroundColor DarkCyan

    $testStart = Get-Date
    try {
        if ($pytestAvail) {
            $pytestOutput = & pytest $testDir -v 2>&1
        } else {
            $pytestOutput = & python -m pytest $testDir -v 2>&1
        }
        $pytestExit = $LASTEXITCODE
    } catch {
        $pytestOutput = @("ERRO: $_")
        $pytestExit   = -1
    }
    $testDuration = [math]::Round(((Get-Date) - $testStart).TotalSeconds, 2)
    $pytestText   = ($pytestOutput | ForEach-Object { "$%" }) -join "`n"

    $summaryLine = ""
    foreach ($line in ($pytestText -split "`n")) {
        if ($line -match '\d+ passed' -or ($line -match 'failed' -and $line -match '\d')) {
            if ($line -match '\d+\.\d+s') { $summaryLine = $line.Trim() }
        }
    }

    $Report.sections.tests["pytest_exit"]     = $pytestExit
    $Report.sections.tests["pytest_summary"]  = $summaryLine
    $Report.sections.tests["pytest_duration"] = "${testDuration}s"
    $Report.sections.tests["pytest_output"]   = $pytestText

    if ($pytestExit -eq 0) {
        $detailMsg = if ($summaryLine) { $summaryLine } else { "Duracao: ${testDuration}s" }
        Add-Item -Section "tests" -Level "OK" `
            -Message "pytest encerrou com sucesso (exit 0)" -Detail $detailMsg
    } else {
        $detailMsg = if ($summaryLine) { $summaryLine } else { "Duracao: ${testDuration}s" }
        Add-Item -Section "tests" -Level "CRITICAL" `
            -Message "pytest encerrou com falha (exit $pytestExit)" -Detail $detailMsg
    }
} else {
    $Report.sections.tests.ran = $false
    Add-Item -Section "tests" -Level "INFO" `
        -Message "Execucao do pytest ignorada (use -RunTests para executar)"
}

$testDir   = Join-Path $RepoPath "tests"
$testFiles = @(Get-ChildItem -Path $testDir -Filter "test_*.py" -ErrorAction SilentlyContinue)
Add-Item -Section "tests" -Level "INFO" `
    -Message "$($testFiles.Count) arquivo(s) test_*.py encontrado(s) em tests/"

if ($testFiles.Count -gt 0) {
    Add-Item -Section "tests" -Level "OK" -Message "Suite de testes detectada"
} else {
    Add-Item -Section "tests" -Level "WARNING" -Message "Nenhum arquivo test_*.py encontrado"
}

if ($RunTests) {
    $Report.sections.tests.ran = $true
    $pytestAvail = $null -ne (Get-Command pytest -ErrorAction SilentlyContinue)
    if (-not $pytestAvail) {
        Add-Item -Section "tests" -Level "WARNING" `
            -Message "pytest nao encontrado no PATH - tentando via 'python -m pytest'" `
            -Detail  "Instale: pip install pytest"
    }

    Write-Host ""
    Write-Host "  Executando: pytest tests/ -v ..." -ForegroundColor DarkCyan

    $testStart = Get-Date
    try {
        if ($pytestAvail) {
            $pytestOutput = & pytest $testDir -v 2>&1
        } else {
            $pytestOutput = & python -m pytest $testDir -v 2>&1
        }
        $pytestExit = $LASTEXITCODE
    } catch {
        $pytestOutput = @("ERRO: $_")
        $pytestExit   = -1
    }
    $testDuration = [math]::Round(((Get-Date) - $testStart).TotalSeconds, 2)
    $pytestText   = ($pytestOutput | ForEach-Object { "$_" }) -join "`n"

    $summaryLine = ""
    foreach ($line in ($pytestText -split "`n")) {
        if ($line -match '\d+ passed' -or ($line -match 'failed' -and $line -match '\d')) {
            if ($line -match '\d+\.\d+s') { $summaryLine = $line.Trim() }
        }
    }

    $Report.sections.tests["pytest_exit"]     = $pytestExit
    $Report.sections.tests["pytest_summary"]  = $summaryLine
    $Report.sections.tests["pytest_duration"] = "${testDuration}s"
    $Report.sections.tests["pytest_output"]   = $pytestText

    if ($pytestExit -eq 0) {
        $detailMsg = if ($summaryLine) { $summaryLine } else { "Duracao: ${testDuration}s" }
        Add-Item -Section "tests" -Level "OK" `
            -Message "pytest encerrou com sucesso (exit 0)" -Detail $detailMsg
    } else {
        $detailMsg = if ($summaryLine) { $summaryLine } else { "Duracao: ${testDuration}s" }
        Add-Item -Section "tests" -Level "CRITICAL" `
            -Message "pytest encerrou com falha (exit $pytestExit)" -Detail $detailMsg
    }
} else {
    $Report.sections.tests.ran = $false
    Add-Item -Section "tests" -Level "INFO" `
        -Message "Execucao do pytest ignorada (use -RunTests para executar)"
}

Write-Host ""

# =============================================================================
# STATUS FINAL
# =============================================================================
$Report.summary.warnings  = $script:Warnings
$Report.summary.criticals = $script:Criticals
$totalDuration = [math]::Round(((Get-Date) - $ScriptStart).TotalSeconds, 2)
$Report.summary.duration  = "${totalDuration}s"

if ($script:Criticals -eq 0 -and $script:Warnings -eq 0) {
    $statusLabel = "ALINHADO"
    $statusColor = "Green"
    $Report.summary.exit_code = 0
} elseif ($script:Criticals -eq 0) {
    $statusLabel = "COM RESSALVAS"
    $statusColor = "Yellow"
    $Report.summary.exit_code = if ($FailOnWarnings) { 1 } else { 0 }
} else {
    $statusLabel = "REQUER ACAO"
    $statusColor = "Red"
    $Report.summary.exit_code = 1
}
$Report.summary.status = $statusLabel

Write-Host "=============================================================" -ForegroundColor Cyan
Write-Host "  RESUMO FINAL" -ForegroundColor White
Write-Host "  Score estrutural : $($Report.sections.estrutural.score)/$($Report.sections.estrutural.total)" -ForegroundColor White
$wColor = if ($script:Warnings  -gt 0) { "Yellow" } else { "Green" }
$cColor = if ($script:Criticals -gt 0) { "Red"    } else { "Green" }
Write-Host "  Avisos           : $script:Warnings"  -ForegroundColor $wColor
Write-Host "  Criticos         : $script:Criticals" -ForegroundColor $cColor
Write-Host "  Duracao          : ${totalDuration}s" -ForegroundColor White
Write-Host ""
Write-Host "  STATUS : $statusLabel" -ForegroundColor $statusColor
Write-Host "=============================================================" -ForegroundColor Cyan
Write-Host ""

# =============================================================================
# GERACAO DO RELATORIO
# =============================================================================

function Get-FormattedItems {
    param([array]$Items)
    $out = @()
    foreach ($i in $Items) {
        $tag = switch ($i.level) {
            "OK"       { "[OK]      " }
            "WARNING"  { "[AVISO]   " }
            "CRITICAL" { "[CRITICO] " }
            default    { "[INFO]    " }
        }
        $line = "$tag $($i.message)"
        if ($i.detail -and $i.detail.Trim()) {
            $line += "`n          Detalhe: $($i.detail)"
        }
        $out += $line
    }
    return $out
}

# Add detailed validation data to report
if ($Report.sections.git.ContainsKey("validation")) {
    $gitVal = $Report.sections.git.validation
    $Report.sections.git["branch_status"] = $gitVal.current_branch
    $Report.sections.git["ahead_behind"]  = $gitVal.ahead_behind
    $Report.sections.git["conflicts"]     = $gitVal.conflicts
    $Report.sections.git["worktree"]      = $gitVal.worktree
    $Report.sections.git["diff_vs_base"]  = $gitVal.diff_vs_base
}

if ($Report.sections.hygiene.ContainsKey("validation")) {
    $hygiene = Get-RepositoryHygiene
    $Report.sections.hygiene["pycache_dirs"] = $hygiene.pycache_dirs
    $Report.sections.hygiene["pyc_files"]    = $hygiene.pyc_files
    $Report.sections.hygiene["pytest_tmp"]   = $hygiene.pytest_tmp
    $Report.sections.hygiene["gitignore"]    = $hygiene.gitignore
}

if ($Report.sections.release.ContainsKey("validation")) {
    $release = $Report.sections.release.validation
    $Report.sections.release["pyproject_version"] = $release.pyproject_version
    $Report.sections.release["version_match"]     = $release.version_match
    $Report.sections.release["critical_docs"]     = $release.critical_docs
}

switch ($OutputFormat) {

    # -------------------------------------------------------------------------
    "txt" {
        $lines = @()
        $lines += "================================================================"
        $lines += "  Jarvas v$TargetVersion - Relatorio de Validacao de Sincronizacao"
        $lines += "  Gerado em : $($Report.meta.timestamp)"
        $lines += "  BaseRef   : $BaseRef"
        $lines += "  PS versao : $($Report.meta.ps_version)"
        $lines += "================================================================"
        $lines += ""

        $secTitles = [ordered]@{
            "estrutural" = "1. ESTRUTURA DO REPOSITORIO"
            "hygiene"    = "2. HIGIENE DO REPOSITORIO"
            "git"        = "3. ESTADO GIT"
            "release"    = "4. RELEASE E VERSAO"
            "tests"      = "5. SUITE DE TESTES"
        }

        foreach ($sec in $secTitles.Keys) {
            $lines += "----------------------------------------------------------------"
            $lines += $secTitles[$sec]
            $lines += "----------------------------------------------------------------"
            $lines += Get-FormattedItems -Items $Report.sections[$sec].items
            if ($sec -eq "estrutural") {
                $p = [math]::Round(($Report.sections.estrutural.score / $Report.sections.estrutural.total) * 100)
                $lines += "  Score: $($Report.sections.estrutural.score)/$($Report.sections.estrutural.total) ($p%)"
            }
            if ($sec -eq "tests" -and $Report.sections.tests.ran) {
                $lines += "  pytest exit : $($Report.sections.tests['pytest_exit'])"
                $lines += "  Resumo      : $($Report.sections.tests['pytest_summary'])"
                $lines += "  Duracao     : $($Report.sections.tests['pytest_duration'])"
            }
            $lines += ""
        }

        $lines += "================================================================"
        $lines += "  RESUMO"
        $lines += "  Avisos   : $script:Warnings"
        $lines += "  Criticos : $script:Criticals"
        $lines += "  Duracao  : $($Report.summary.duration)"
        $lines += "  STATUS   : $statusLabel"
        $lines += "  Exit code: $($Report.summary.exit_code)"
        $lines += "================================================================"

        Set-Content -Path $ReportFile -Value $lines -Encoding UTF8
    }

    # -------------------------------------------------------------------------
    "json" {
        if ($Report.sections.tests.ContainsKey("pytest_output")) {
            $Report.sections.tests.Remove("pytest_output")
        }
        $jsonText = $Report | ConvertTo-Json -Depth 10
        Set-Content -Path $ReportFile -Value $jsonText -Encoding UTF8
    }

    # -------------------------------------------------------------------------
    "md" {
        $md = @()
        $md += "# Jarvas v$TargetVersion - Relatorio de Validacao"
        $md += ""
        $md += "| Campo | Valor |"
        $md += "|:------|:------|"
        $md += "| Gerado em | $($Report.meta.timestamp) |"
        $md += "| BaseRef | $BaseRef |"
        $md += "| PowerShell | $($Report.meta.ps_version) |"
        $md += "| Run Tests | $([bool]$RunTests) |"
        $md += "| Fail-on-Warnings | $([bool]$FailOnWarnings) |"
        $md += ""

        $secDefs = [ordered]@{
            "estrutural" = "[DIR] Estrutura do Repositorio"
            "hygiene"    = "[CLN] Higiene do Repositorio"
            "git"        = "[GIT] Estado Git"
            "release"    = "[REL] Release e Versao"
            "tests"      = "[TST] Suite de Testes"
        }

        foreach ($sec in $secDefs.Keys) {
            $md += "---"
            $md += "## $($secDefs[$sec])"
            $md += ""
            foreach ($i in $Report.sections[$sec].items) {
                $badge = switch ($i.level) {
                    "OK"       { "[OK]" }
                    "WARNING"  { "[AVISO]" }
                    "CRITICAL" { "[CRITICO]" }
                    default    { "[INFO]" }
                }
                $md += "- $badge $($i.message)"
                if ($i.detail -and $i.detail.Trim()) {
                    $md += "  - _Detalhe: $($i.detail)_"
                }
            }
            if ($sec -eq "estrutural") {
                $p = [math]::Round(($Report.sections.estrutural.score / $Report.sections.estrutural.total) * 100)
                $md += ""
                $md += "> **Score:** $($Report.sections.estrutural.score)/$($Report.sections.estrutural.total) ($p%)"
            }
            if ($sec -eq "tests" -and $Report.sections.tests.ran) {
                $md += ""
                $md += "| Metrica | Valor |"
                $md += "|:--------|:------|"
                $md += "| Exit code | $($Report.sections.tests['pytest_exit']) |"
                $md += "| Resumo | $($Report.sections.tests['pytest_summary']) |"
                $md += "| Duracao | $($Report.sections.tests['pytest_duration']) |"
            }
            $md += ""
        }

        $statusBadge = switch ($statusLabel) {
            "ALINHADO"     { "[OK] **ALINHADO**" }
            "COM RESSALVAS"{ "[AVISO] **COM RESSALVAS**" }
            default        { "[CRITICO] **REQUER ACAO**" }
        }

        $md += "---"
        $md += "## Resumo Final"
        $md += ""
        $md += "| Metrica | Valor |"
        $md += "|:--------|:------|"
        $md += "| Avisos | $script:Warnings |"
        $md += "| Criticos | $script:Criticals |"
        $md += "| Duracao total | $($Report.summary.duration) |"
        $md += "| Exit code | $($Report.summary.exit_code) |"
        $md += "| **Status** | $statusBadge |"
        $md += ""
        $md += "---"
        $md += "_Relatorio gerado por VALIDAR_SINCRONIZACAO.ps1_"

        Set-Content -Path $ReportFile -Value $md -Encoding UTF8
    }
}

Write-Host "  Relatorio salvo em: $ReportFile" -ForegroundColor Cyan
Write-Host ""

exit $Report.summary.exit_code
