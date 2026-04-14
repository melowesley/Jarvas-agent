// chat.js - lógica do chat no Webview
// @ts-check

const vscode = acquireVsCodeApi();
const agentSelect = document.getElementById('agent-select');
const messagesDiv = document.getElementById('messages');
const input = document.getElementById('input');
const sendBtn = document.getElementById('send');

// Load agents on start
vscode.postMessage({ type: 'loadAgents' });

// Handle messages from extension
window.addEventListener('message', event => {
    const msg = event.data;
    if (msg.type === 'agents') {
        agentSelect.innerHTML = '';
        msg.agents.forEach(agent => {
            const option = document.createElement('option');
            option.value = agent.id;
            option.textContent = agent.name;
            agentSelect.appendChild(option);
        });
    } else if (msg.type === 'event') {
        renderEvent(msg.event);
    }
});

function setLoading(loading) {
    sendBtn.disabled = loading;
    input.disabled = loading;
    sendBtn.textContent = loading ? '...' : 'Enviar';
}

sendBtn.addEventListener('click', sendMessage);
input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

function sendMessage() {
    const text = input.value.trim();
    if (!text || sendBtn.disabled) return;

    const agentId = agentSelect.value;
    if (!agentId) return;

    // Show user message immediately
    appendMessage('user', text);
    input.value = '';
    setLoading(true);

    vscode.postMessage({ type: 'send', text, agentId });
}

function appendMessage(role, content) {
    const div = document.createElement('div');
    div.className = `message message-${role}`;
    div.textContent = content;
    messagesDiv.appendChild(div);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function renderEvent(event) {
    if (event.type === 'agent.message') {
        appendMessage('assistant', event.content);
    } else if (event.type === 'agent.tool_use') {
        const div = document.createElement('div');
        div.className = 'message message-tool';
        const details = document.createElement('details');
        const summary = document.createElement('summary');
        summary.textContent = `🔧 ${event.tool_name}`;
        const pre = document.createElement('pre');
        pre.textContent = JSON.stringify(event.tool_input, null, 2);
        details.appendChild(summary);
        details.appendChild(pre);
        div.appendChild(details);
        messagesDiv.appendChild(div);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    } else if (event.type === 'agent.tool_result') {
        const div = document.createElement('div');
        div.className = `message message-tool-result${event.is_error ? ' message-error' : ''}`;
        const details = document.createElement('details');
        const summary = document.createElement('summary');
        summary.textContent = event.is_error ? `❌ ${event.tool_name} error` : `✅ ${event.tool_name} result`;
        const pre = document.createElement('pre');
        pre.textContent = event.output;
        details.appendChild(summary);
        details.appendChild(pre);
        div.appendChild(details);
        messagesDiv.appendChild(div);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    } else if (event.type === 'session.error') {
        appendMessage('error', `⚠️ ${event.message}`);
        setLoading(false);
    } else if (event.type === 'session.status_idle') {
        setLoading(false);
    }
}
