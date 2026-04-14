import * as vscode from 'vscode';
import * as path from 'path';

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

    private async _loadAgents() {
        try {
            const res = await fetch('http://localhost:8000/v1/agents');
            const agents = await res.json();
            this._panel.webview.postMessage({ type: 'agents', agents });
        } catch (e) {
            console.error(e);
        }
    }

    private async _handleSend(text: string, agentId: string) {
        // Criar sessão se não existe ou agent mudou
        if (!this._sessionId || this._agentId !== agentId) {
            try {
                const res = await fetch('http://localhost:8000/v1/sessions', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ agent_id: agentId, title: 'VSCode Chat' })
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
                <div id="messages"></div>
                <footer>
                    <textarea id="input" placeholder="Mensagem..."></textarea>
                    <button id="send">Enviar</button>
                </footer>
            </div>
            <script src="${scriptUri}"></script>
        </body>
        </html>`;
    }
}