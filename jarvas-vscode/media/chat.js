// chat.js - lógica do chat no Webview

/* global acquireVsCodeApi */
const vscode = acquireVsCodeApi();

const agentSelect = /** @type {HTMLSelectElement} */ (document.getElementById('agent-select'));
const messagesDiv = /** @type {HTMLElement} */ (document.getElementById('messages'));
const input = /** @type {HTMLTextAreaElement} */ (document.getElementById('input'));
const sendBtn = /** @type {HTMLButtonElement} */ (document.getElementById('send'));
const statusBar = /** @type {HTMLElement} */ (document.getElementById('status-bar'));

let connected = false;

// ── Conexão ──────────────────────────────────────────────────────────

function tryConnect() {
    statusBar.textContent = '⏳ Conectando ao servidor...';
    statusBar.className = 'status-connecting';
    vscode.postMessage({ type: 'loadAgents' });
}

function setConnected(agents) {
    connected = true;
    agentSelect.innerHTML = '';
    agents.forEach(agent => {
        const option = document.createElement('option');
        option.value = agent.id;
        option.textContent = agent.name;
        agentSelect.appendChild(option);
    });
    statusBar.textContent = `✅ Conectado — ${agents.length} agente(s)`;
    statusBar.className = 'status-ok';
    input.disabled = false;
    sendBtn.disabled = false;
    input.focus();
}

function setDisconnected(msg) {
    connected = false;
    input.disabled = true;
    sendBtn.disabled = true;
    statusBar.innerHTML = `⚠️ ${msg} &nbsp;<button id="retry-btn">Tentar novamente</button>`;
    statusBar.className = 'status-error';
    document.getElementById('retry-btn').addEventListener('click', tryConnect);
}

// Tenta conectar ao abrir
tryConnect();

// Timeout de 15s para mostrar erro se não conectar (servidor pode demorar para iniciar)
let connectTimer = setTimeout(() => {
    if (!connected) {
        setDisconnected('Servidor não iniciou. Tente abrir um terminal e executar: jarvas --managed');
    }
}, 15000);

// ── Mensagens da extensão ────────────────────────────────────────────

window.addEventListener('message', event => {
    const msg = event.data;

    if (msg.type === 'agents') {
        clearTimeout(connectTimer);
        if (!msg.agents || msg.agents.length === 0) {
            setDisconnected('Nenhum agente encontrado no servidor.');
        } else {
            setConnected(msg.agents);
        }
    } else if (msg.type === 'status') {
        clearTimeout(connectTimer);
        statusBar.textContent = msg.msg;
        statusBar.className = 'status-connecting';
    } else if (msg.type === 'error') {
        clearTimeout(connectTimer);
        setDisconnected(msg.msg || msg.message || 'Erro desconhecido');
    } else if (msg.type === 'event') {
        renderEvent(msg.event);
    }
});

// ── Envio ────────────────────────────────────────────────────────────

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
    if (!text || sendBtn.disabled || !connected) return;

    const agentId = agentSelect.value;
    if (!agentId) return;

    appendMessage('user', text);
    input.value = '';
    setLoading(true);

    vscode.postMessage({ type: 'send', text, agentId });
}

// ── Renderização ─────────────────────────────────────────────────────

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
        summary.textContent = event.is_error ? `❌ ${event.tool_name}` : `✅ ${event.tool_name}`;
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
