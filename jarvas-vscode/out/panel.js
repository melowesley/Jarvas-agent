"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.ChatPanel = void 0;
const vscode = __importStar(require("vscode"));
const path = __importStar(require("path"));
const cp = __importStar(require("child_process"));
let jarvasServerProcess = null;
function findJarvasExecutable() {
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
                if (fs.existsSync(c))
                    return c;
            }
        }
        catch { }
    }
    return 'jarvas'; // fallback
}
async function isServerReady() {
    try {
        const res = await fetch('http://localhost:8000/v1/agents', { signal: AbortSignal.timeout(2000) });
        return res.ok;
    }
    catch {
        return false;
    }
}
function startJarvasServer() {
    const exe = findJarvasExecutable();
    const args = ['--managed'];
    let proc;
    try {
        proc = cp.spawn(exe, args, {
            shell: false,
            detached: false,
            stdio: ['ignore', 'pipe', 'pipe'],
            env: { ...process.env },
        });
    }
    catch (err) {
        throw new Error(`Erro ao iniciar Jarvas: ${err instanceof Error ? err.message : String(err)}`);
    }
    proc.on('exit', (code, signal) => {
        jarvasServerProcess = null;
        console.error(`Jarvas server exited with code=${code} signal=${signal}`);
    });
    proc.stdout?.on('data', (chunk) => {
        const text = chunk.toString().trim();
        if (text)
            console.log(`[Jarvas stdout] ${text}`);
    });
    proc.stderr?.on('data', (chunk) => {
        const text = chunk.toString().trim();
        if (text)
            console.error(`[Jarvas stderr] ${text}`);
    });
    return proc;
}
async function ensureServerReady() {
    if (await isServerReady())
        return;
    if (!jarvasServerProcess || jarvasServerProcess.exitCode !== null) {
        jarvasServerProcess = startJarvasServer();
    }
    const maxWait = 30000; // 30s
    const pollInterval = 2000; // 2s
    let waited = 0;
    while (waited < maxWait) {
        await new Promise((resolve) => setTimeout(resolve, pollInterval));
        waited += pollInterval;
        if (await isServerReady())
            return;
        if (jarvasServerProcess?.exitCode !== null) {
            throw new Error('O processo Jarvas terminou antes de ficar pronto');
        }
    }
    throw new Error('Servidor não iniciou dentro de 30 segundos');
}
class ChatPanel {
    static createOrShow(extensionUri) {
        if (ChatPanel.currentPanel) {
            ChatPanel.currentPanel._panel.reveal();
            return;
        }
        const panel = vscode.window.createWebviewPanel('jarvasChat', 'Jarvas Chat', vscode.ViewColumn.Beside, { enableScripts: true, retainContextWhenHidden: true });
        ChatPanel.currentPanel = new ChatPanel(panel, extensionUri);
    }
    constructor(panel, extensionUri) {
        this._sessionId = null;
        this._agentId = null;
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
            if (msg.type === 'send')
                await this._handleSend(msg.text, msg.agentId);
            if (msg.type === 'loadAgents')
                await this._loadAgents();
        });
        // Limpar referência ao fechar
        this._panel.onDidDispose(() => {
            ChatPanel.currentPanel = undefined;
        });
    }
    async _loadAgents() {
        try {
            const res = await fetch('http://localhost:8000/v1/agents');
            const agents = await res.json();
            this._panel.webview.postMessage({ type: 'agents', agents });
        }
        catch (e) {
            const msg = e instanceof Error ? e.message : String(e);
            this._panel.webview.postMessage({ type: 'error', msg: 'Erro ao carregar agentes: ' + msg });
        }
    }
    async _handleSend(text, agentId) {
        // Criar sessão se não existe ou agent mudou
        if (!this._sessionId || this._agentId !== agentId) {
            try {
                const workspacePath = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? null;
                const res = await fetch('http://localhost:8000/v1/sessions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ agent_id: agentId, title: 'VSCode Chat', workspace_path: workspacePath })
                });
                const sess = await res.json();
                this._sessionId = sess.id;
                this._agentId = agentId;
            }
            catch (e) {
                console.error(e);
                return;
            }
        }
        // Enviar mensagem
        try {
            await fetch(`http://localhost:8000/v1/sessions/${this._sessionId}/events`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content: text })
            });
            // Ler SSE stream
            const stream = await fetch(`http://localhost:8000/v1/sessions/${this._sessionId}/stream`);
            const reader = stream.body.getReader();
            const decoder = new TextDecoder();
            let done = false;
            while (!done) {
                const { done: streamDone, value } = await reader.read();
                if (streamDone)
                    break;
                const lines = decoder.decode(value).split('\n');
                for (const line of lines) {
                    if (!line.startsWith('data: '))
                        continue;
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
                        }
                        catch (e) {
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
        }
        catch (e) {
            console.error(e);
        }
    }
    async _executeVSCodeTool(name, input) {
        try {
            if (name === 'vscode_open') {
                const filePath = input.path;
                const uri = path.isAbsolute(filePath)
                    ? vscode.Uri.file(filePath)
                    : vscode.Uri.joinPath(vscode.workspace.workspaceFolders[0].uri, filePath);
                await vscode.window.showTextDocument(uri, { preview: false });
                return { output: `Opened ${filePath}`, is_error: false };
            }
            if (name === 'vscode_edit') {
                const filePath = input.path;
                const uri = path.isAbsolute(filePath)
                    ? vscode.Uri.file(filePath)
                    : vscode.Uri.joinPath(vscode.workspace.workspaceFolders[0].uri, filePath);
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
        }
        catch (e) {
            const msg = e instanceof Error ? e.message : String(e);
            return { output: msg, is_error: true };
        }
    }
    _getHtml(extensionUri) {
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
exports.ChatPanel = ChatPanel;
//# sourceMappingURL=panel.js.map