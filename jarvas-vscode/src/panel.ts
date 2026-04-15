import * as vscode from 'vscode';
import * as path from 'path';
import * as cp from 'child_process';

let jarvasServerProcess: cp.ChildProcess | null = null;

function findJarvasExecutable(): string {
    // Tenta achar o jarvas no PATH ou em locais comuns do Python no Windows
    const candidates = [
        'jarvas',
        'C:\\Users\\Computador\\AppData\\Local\\Programs\\Python\\Python313\\Scripts\\jarvas.exe',
        process.env.LOCALAPPDATA + '\\Programs\\Python\\Python312\\Scripts\\jarvas.exe',
        process.env.LOCALAPPDATA + '\\Programs\\Python\\Python311\\Scripts\\jarvas.exe',
        (process.env.USERPROFILE ?? '') + '\\AppData\\Local\\Programs\\Python\\Python313\\Scripts\\jarvas.exe',
        (process.env.USERPROFILE ?? '') + '\\.local\\bin\\jarvas',
    ];
    for (const c of candidates) {
        try {
            if (c !== 'jarvas') {
                const fs = require('fs');
                if (fs.existsSync(c)) return c;
            }
        } catch {}
    }
    return 'jarvas'; // fallback
}

async function isServerReady(): Promise<boolean> {
    try {
        const res = await fetch('http://localhost:8000/v1/agents', { signal: AbortSignal.timeout(2000) });
        return res.ok;
    } catch {
        return false;
    }
}

function startJarvasServer(): cp.ChildProcess {
    const exe = findJarvasExecutable();
    const args = ['--managed'];

    let proc: cp.ChildProcess;
    try {
        proc = cp.spawn(exe, args, {
            shell: false,
            detached: false,
            stdio: ['ignore', 'pipe', 'pipe'],
            env: { ...process.env },
        });
    } catch (err: unknown) {
        throw new Error(`Erro ao iniciar Jarvas: ${err instanceof Error ? err.message : String(err)}`);
    }

    proc.on('exit', (code, signal) => {
        jarvasServerProcess = null;
        console.error(`Jarvas server exited with code=${code} signal=${signal}`);
    });

    proc.stdout?.on('data', (chunk) => {
        const text = chunk.toString().trim();
        if (text) console.log(`[Jarvas stdout] ${text}`);
    });

    proc.stderr?.on('data', (chunk) => {
        const text = chunk.toString().trim();
        if (text) console.error(`[Jarvas stderr] ${text}`);
    });

    return proc;
}

async function ensureServerReady(): Promise<void> {
    if (await isServerReady()) return;

    if (!jarvasServerProcess || jarvasServerProcess.exitCode !== null) {
        jarvasServerProcess = startJarvasServer();
    }

    const maxWait = 30000; // 30s
    const pollInterval = 2000; // 2s
    let waited = 0;

    while (waited < maxWait) {
        await new Promise((resolve) => setTimeout(resolve, pollInterval));
        waited += pollInterval;
        if (await isServerReady()) return;

        if (jarvasServerProcess?.exitCode !== null) {
            throw new Error('O processo Jarvas terminou antes de ficar pronto');
        }
    }

    throw new Error('Servidor não iniciou dentro de 30 segundos');
}

export class ChatPanel {
    static currentPanel: ChatPanel | undefined;
    private readonly _panel: vscode.WebviewPanel;
    private _sessionId: string | null = null;
    private _agentId: string | null = null;

    static createOrShow(extensionUri: vscode.Uri) {
        if (ChatPanel.currentPanel) {
            ChatPanel.currentPanel._panel.reveal();
            return;
        }
        const panel = vscode.window.createWebviewPanel(
            'jarvasChat', 'Jarvas Chat',
            vscode.ViewColumn.Beside,
            { enableScripts: true, retainContextWhenHidden: true }
        );
        ChatPanel.currentPanel = new ChatPanel(panel, extensionUri);
    }

    constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri) {
        this._panel = panel;
        this._panel.webview.html = this._getHtml(extensionUri);
        
        this._panel.webview.postMessage({ type: 'status', msg: '⏳ Iniciando servidor Jarvas...' });
        ensureServerReady().then(() => {
            this._loadAgents();
        }).catch((err) => {
            this._panel.webview.postMessage({ type: 'error', msg: 'Falha ao iniciar servidor Jarvas: ' + err.message });
        });
        
        // Mensagens do Webview → extensão
        this._panel.webview.onDidReceiveMessage(async (msg) => {
            if (msg.type === 'send') await this._handleSend(msg.text, msg.agentId);
            if (msg.type === 'loadAgents') await this._loadAgents();
        });

        // Limpar referência ao fechar
        this._panel.onDidDispose(() => {
            ChatPanel.currentPanel = undefined;
        });
    }

    private async _loadAgents(): Promise<void> {
        try {
            const res = await fetch('http://localhost:8000/v1/agents');
            const agents = await res.json();
            this._panel.webview.postMessage({ type: 'agents', agents });
        } catch (e) {
            const msg = e instanceof Error ? e.message : String(e);
            this._panel.webview.postMessage({ type: 'error', msg: 'Erro ao carregar agentes: ' + msg });
        }
    }

    private async _handleSend(text: string, agentId: string) {
        // Criar sessão se não existe ou agent mudou
        if (!this._sessionId || this._agentId !== agentId) {
            try {
                const workspacePath = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? null;
                const res = await fetch('http://localhost:8000/v1/sessions', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ agent_id: agentId, title: 'VSCode Chat', workspace_path: workspacePath })
                });
                const sess = await res.json();
                this._sessionId = sess.id;
                this._agentId = agentId;
            } catch (e) {
                console.error(e);
                return;
            }
        }

        // Enviar mensagem
        try {
            await fetch(`http://localhost:8000/v1/sessions/${this._sessionId}/events`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ content: text })
            });

            // Ler SSE stream
            const stream = await fetch(`http://localhost:8000/v1/sessions/${this._sessionId}/stream`);
            const reader = stream.body!.getReader();
            const decoder = new TextDecoder();
            let done = false;
            while (!done) {
                const { done: streamDone, value } = await reader.read();
                if (streamDone) break;
                const lines = decoder.decode(value).split('\n');
                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    const event = JSON.parse(line.slice(6));

                    // Executar ferramentas VSCode-native inline (não encaminhar ao Webview ainda)
                    if (event.type === 'agent.tool_use' && event.awaiting_callback) {
                        const result = await this._executeVSCodeTool(event.tool_name, event.tool_input);
                        try {
                            await fetch(`http://localhost:8000/v1/sessions/${this._sessionId}/tool_result`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                    tool_call_id: event.tool_call_id,
                                    output: result.output,
                                    is_error: result.is_error,
                                }),
                            });
                        } catch (e) {
                            console.error('Failed to post tool_result:', e);
                        }
                    }

                    this._panel.webview.postMessage({ type: 'event', event });
                    if (event.type === 'session.status_idle' || event.type === 'session.error') {
                        done = true;
                        break;
                    }
                }
            }
            reader.cancel();
        } catch (e) {
            console.error(e);
        }
    }

    private async _executeVSCodeTool(
        name: string,
        input: Record<string, string>
    ): Promise<{ output: string; is_error: boolean }> {
        try {
            if (name === 'vscode_open') {
                const filePath = input.path;
                const uri = path.isAbsolute(filePath)
                    ? vscode.Uri.file(filePath)
                    : vscode.Uri.joinPath(vscode.workspace.workspaceFolders![0].uri, filePath);
                await vscode.window.showTextDocument(uri, { preview: false });
                return { output: `Opened ${filePath}`, is_error: false };
            }

            if (name === 'vscode_edit') {
                const filePath = input.path;
                const uri = path.isAbsolute(filePath)
                    ? vscode.Uri.file(filePath)
                    : vscode.Uri.joinPath(vscode.workspace.workspaceFolders![0].uri, filePath);
                const doc = await vscode.workspace.openTextDocument(uri);
                const text = doc.getText();
                const idx = text.indexOf(input.old_text);
                if (idx === -1) {
                    return { output: `Text not found in ${filePath}`, is_error: true };
                }
                const edit = new vscode.WorkspaceEdit();
                const start = doc.positionAt(idx);
                const end = doc.positionAt(idx + input.old_text.length);
                edit.replace(uri, new vscode.Range(start, end), input.new_text);
                await vscode.workspace.applyEdit(edit);
                return { output: `Edited ${filePath}`, is_error: false };
            }

            if (name === 'vscode_terminal') {
                const term = vscode.window.createTerminal('Jarvas');
                term.show(true);
                term.sendText(input.command);
                return { output: `Command sent to terminal: ${input.command}`, is_error: false };
            }

            if (name === 'vscode_list') {
                const pattern = input.pattern || '**/*';
                const files = await vscode.workspace.findFiles(pattern, '**/node_modules/**', 200);
                const paths = files.map(f => f.fsPath).join('\n');
                return { output: paths || '(no files found)', is_error: false };
            }

            return { output: `Unknown vscode tool: ${name}`, is_error: true };
        } catch (e: unknown) {
            const msg = e instanceof Error ? e.message : String(e);
            return { output: msg, is_error: true };
        }
    }

    private _getHtml(extensionUri: vscode.Uri): string {
        const scriptUri = this._panel.webview.asWebviewUri(vscode.Uri.joinPath(extensionUri, 'media', 'chat.js'));
        const styleUri = this._panel.webview.asWebviewUri(vscode.Uri.joinPath(extensionUri, 'media', 'chat.css'));

        return `<!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Jarvas Chat</title>
            <link href="${styleUri}" rel="stylesheet">
        </head>
        <body>
            <div id="app">
                <header>
                    <span>Jarvas Chat</span>
                    <select id="agent-select"></select>
                </header>
                <div id="status-bar" class="status-connecting">⏳ Conectando...</div>
                <div id="messages"></div>
                <footer>
                    <textarea id="input" placeholder="Mensagem..." disabled></textarea>
                    <button id="send" disabled>Enviar</button>
                </footer>
            </div>
            <script src="${scriptUri}"></script>
        </body>
        </html>`;
    }
}