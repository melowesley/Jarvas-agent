// src/api.ts - client HTTP para localhost:8000

export class JarvasAPI {
    private baseUrl = 'http://localhost:8000/v1';

    async getAgents() {
        const res = await fetch(`${this.baseUrl}/agents`);
        return res.json();
    }

    async createSession(agentId: string) {
        const res = await fetch(`${this.baseUrl}/sessions`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ agent_id: agentId })
        });
        return res.json();
    }

    async sendMessage(sessionId: string, content: string) {
        const res = await fetch(`${this.baseUrl}/sessions/${sessionId}/events`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ content })
        });
        return res;
    }

    async getStream(sessionId: string) {
        return fetch(`${this.baseUrl}/sessions/${sessionId}/stream`);
    }
}