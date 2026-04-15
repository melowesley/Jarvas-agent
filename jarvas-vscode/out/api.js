"use strict";
// src/api.ts - client HTTP para localhost:8000
Object.defineProperty(exports, "__esModule", { value: true });
exports.JarvasAPI = void 0;
class JarvasAPI {
    constructor() {
        this.baseUrl = 'http://localhost:8000/v1';
    }
    async getAgents() {
        const res = await fetch(`${this.baseUrl}/agents`);
        return res.json();
    }
    async createSession(agentId) {
        const res = await fetch(`${this.baseUrl}/sessions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ agent_id: agentId })
        });
        return res.json();
    }
    async sendMessage(sessionId, content) {
        const res = await fetch(`${this.baseUrl}/sessions/${sessionId}/events`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content })
        });
        return res;
    }
    async getStream(sessionId) {
        return fetch(`${this.baseUrl}/sessions/${sessionId}/stream`);
    }
}
exports.JarvasAPI = JarvasAPI;
//# sourceMappingURL=api.js.map