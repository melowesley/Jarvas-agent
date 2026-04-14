import * as vscode from 'vscode';
import { ChatPanel } from './panel';

export function activate(ctx: vscode.ExtensionContext) {
    // Registrar comando
    ctx.subscriptions.push(
        vscode.commands.registerCommand('jarvas.openChat', () => {
            ChatPanel.createOrShow(ctx.extensionUri);
        })
    );

    // Botão na status bar
    const btn = vscode.window.createStatusBarItem(
        vscode.StatusBarAlignment.Right, 1000
    );
    btn.text = '$(robot) Jarvas';
    btn.tooltip = 'Open Jarvas Chat';
    btn.command = 'jarvas.openChat';
    btn.show();
    ctx.subscriptions.push(btn);
}

export function deactivate() {}