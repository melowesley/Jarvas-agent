"""Adapter do Moltbook Publisher — integra Jarvas à rede social de IAs Moltbook."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta
from typing import Any

from jarvas.agents.base import AgentResult
from jarvas.context import SessionContext

# ── Circuit breaker (module-level state) ─────────────────────────────────────
_cb_failures: int = 0
_cb_paused_until: datetime | None = None
_CB_THRESHOLD = 3
_CB_PAUSE_MINUTES = 60

# ── Reply rate limit (redefine diariamente) ───────────────────────────────────
_replies_today: int = 0
_replies_date: str = ""
_MAX_REPLIES_PER_DAY = 3


def _api_key() -> str:
    return os.getenv("MOLTBOOK_API_KEY", "")


def _base_url() -> str:
    return os.getenv("MOLTBOOK_BASE_URL", "https://moltbook.com/api").rstrip("/")


def _user_id() -> str:
    return os.getenv("MOLTBOOK_USER_ID", "jarvas")


def _mode() -> str:
    return os.getenv("MOLTBOOK_MODE", "normal").lower()


def _auto_publish() -> bool:
    return os.getenv("MOLTBOOK_AUTO_PUBLISH", "true").lower() == "true"


def _submolt() -> str:
    return os.getenv("MOLTBOOK_SUBMOLT", "general")


class MoltbookAgent:
    name = "moltbook_publisher"
    role = (
        "Publicador social do Jarvas na rede Moltbook. Minera aprendizados do MemPalace, "
        "curada posts com Gemini, publica 2×/dia, responde menções e acompanha engajamento."
    )
    model = "moltbook_api/v1"
    tools: list[str] = ["moltbook_feed", "moltbook_identity", "mempalace_search"]
    memory_scope = "global"
    can_delegate_to: list[str] = ["gemini_analyst"]

    def run(self, message: str, ctx: SessionContext) -> AgentResult:
        msg = message.strip()

        if msg.startswith("publish_curated:"):
            period = msg.split(":", 1)[1].strip() or "today"
            return self._publish_curated(period)

        if msg == "publish_weekly_retro":
            return self._publish_weekly_retro()

        if msg == "send_heartbeat":
            return self._send_heartbeat()

        if msg == "resonance_scan":
            return self._resonance_scan()

        if msg == "ingest_engagement":
            return self._ingest_engagement()

        if msg == "identity_token":
            return self._get_identity_token()

        if msg.startswith("read_feed"):
            parts = msg.split(":", 1)
            since_str = parts[1].strip() if len(parts) > 1 else ""
            since = datetime.fromisoformat(since_str) if since_str else datetime.utcnow() - timedelta(hours=24)
            posts = self._read_feed(since)
            return AgentResult(
                content=json.dumps(posts, ensure_ascii=False, default=str),
                model=self.model,
                agent_name=self.name,
                metadata={"post_count": len(posts)},
            )

        if msg.startswith("status"):
            return self._status()

        return AgentResult(
            content=f"[moltbook] Comando não reconhecido: {msg}",
            model=self.model,
            agent_name=self.name,
        )

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {_api_key()}",
            "Content-Type": "application/json",
        }

    def _get(self, path: str, **params) -> Any:
        import httpx
        resp = httpx.get(f"{_base_url()}{path}", headers=self._headers(), params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def _post_http(self, path: str, payload: dict) -> Any:
        import httpx
        resp = httpx.post(f"{_base_url()}{path}", headers=self._headers(), json=payload, timeout=15)
        resp.raise_for_status()
        return resp.json()

    # ── Circuit breaker ───────────────────────────────────────────────────────

    def _circuit_breaker_check(self) -> bool:
        global _cb_paused_until
        if _cb_paused_until and datetime.utcnow() < _cb_paused_until:
            return False
        if _cb_paused_until and datetime.utcnow() >= _cb_paused_until:
            _cb_paused_until = None
            _reset_cb()
        return True

    def _record_failure(self) -> None:
        global _cb_failures, _cb_paused_until
        _cb_failures += 1
        if _cb_failures >= _CB_THRESHOLD:
            _cb_paused_until = datetime.utcnow() + timedelta(minutes=_CB_PAUSE_MINUTES)
            _cb_failures = 0

    def _record_success(self) -> None:
        global _cb_failures
        _cb_failures = max(0, _cb_failures - 1)

    # ── MemPalace helpers ─────────────────────────────────────────────────────

    def _mempalace_search(self, query: str) -> list[dict]:
        try:
            from jarvas.mempalace_client import _get_tools
            tools = _get_tools()
            result = tools.tool_search(query=query)
            if isinstance(result, list):
                return result
            if isinstance(result, dict):
                return result.get("results", [])
            return []
        except Exception:
            return []

    def _mempalace_add(self, wing: str, room: str, content: str) -> bool:
        try:
            from jarvas.mempalace_client import _get_tools
            tools = _get_tools()
            tools.tool_add_drawer(wing=wing, room=room, content=content)
            return True
        except Exception:
            return False

    def _content_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def _is_duplicate(self, content_hash: str) -> bool:
        return len(self._mempalace_search(f"hash:{content_hash}")) > 0

    def _mark_published(self, post_id: str, source_hashes: list[str], content: str) -> None:
        meta = {
            "moltbook_post_id": post_id,
            "posted_at": datetime.utcnow().isoformat(),
            "source_hashes": source_hashes,
            "hash_conteudo": self._content_hash(content),
        }
        self._mempalace_add("jarvas", "published", json.dumps(meta, ensure_ascii=False))

    def _save_draft(self, draft_id: str, content: str, title: str, source_hashes: list[str]) -> None:
        meta = {
            "draft_id": draft_id,
            "created_at": datetime.utcnow().isoformat(),
            "source_hashes": source_hashes,
            "title": title,
            "content": content,
        }
        self._mempalace_add("jarvas", "drafts", json.dumps(meta, ensure_ascii=False))

    # ── Learnings mining ──────────────────────────────────────────────────────

    def _fetch_learnings(self, period: str = "today") -> list[dict]:
        cutoff = self._period_cutoff(period)
        raw = self._mempalace_search("aprendizado confidence") or self._mempalace_search("learnings")

        filtered = []
        for item in raw:
            meta = item if isinstance(item, dict) else {}
            ts_str = meta.get("timestamp") or meta.get("posted_at") or ""
            try:
                ts = datetime.fromisoformat(ts_str) if ts_str else datetime.min
            except ValueError:
                ts = datetime.min
            if ts >= cutoff:
                filtered.append(meta)

        return filtered if filtered else raw[:10]

    def _period_cutoff(self, period: str) -> datetime:
        now = datetime.utcnow()
        if period in ("hoje", "today"):
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        if period in ("ontem", "yesterday"):
            return (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        if period in ("semana", "week"):
            return now - timedelta(days=7)
        return now - timedelta(days=1)

    # ── Curadoria via Gemini ──────────────────────────────────────────────────

    def _curate(self, candidates: list[dict]) -> list[dict]:
        if not candidates:
            return []
        try:
            from jarvas.agents.registry import get_agent
            from jarvas.session import get_session
            gemini = get_agent("gemini_analyst")
            ctx = get_session()
            prompt = (
                "Você é curador de aprendizados para a rede social de IAs Moltbook.\n"
                "Escolha até 3 candidatos que sejam: (a) úteis a outros agentes, "
                "(b) não-redundantes, (c) concretos e específicos.\n\n"
                f"Candidatos: {json.dumps(candidates, ensure_ascii=False, default=str)}\n\n"
                "Retorne SOMENTE JSON:\n"
                '{"selecionados": [{"id": "...", "justificativa": "...", "publish_score": 0.0}]}'
            )
            result = gemini.run(prompt, ctx)
            text = result.content.strip()
            start, end = text.find("{"), text.rfind("}") + 1
            if start >= 0 and end > start:
                parsed = json.loads(text[start:end])
                selected_ids = {
                    str(s["id"]) for s in parsed.get("selecionados", [])
                    if s.get("publish_score", 0) > 0.4
                }
                curated = [c for c in candidates if str(c.get("id", "")) in selected_ids]
                if curated:
                    return curated
        except Exception:
            pass
        return candidates[:3]

    # ── Post formatting ───────────────────────────────────────────────────────

    def _format_post(self, learnings: list[dict], period: str = "today") -> tuple[str, str]:
        label = {
            "hoje": "hoje", "today": "hoje",
            "ontem": "ontem", "yesterday": "ontem",
            "semana": "esta semana", "week": "esta semana",
        }.get(period, "recentemente")
        title = f"Aprendizados do Jarvas — {label}"
        lines = []
        for i, item in enumerate(learnings[:3], 1):
            desc = (
                item.get("descricao")
                or item.get("content")
                or item.get("description")
                or str(item)[:200]
            )
            lines.append(f"{i}. {desc}")
        lines.append("\n#Jarvas #IA #aprendizado")
        return title, "\n".join(lines)

    def _format_retro(self, learnings: list[dict], synthesis: str) -> tuple[str, str]:
        title = f"Retrospectiva semanal do Jarvas — {datetime.utcnow().strftime('%d/%m/%Y')}"
        content = (
            f"{synthesis}\n\n"
            f"Total de aprendizados esta semana: {len(learnings)}\n\n"
            "#Jarvas #retrospectiva #IA"
        )
        return title, content

    # ── Core actions ──────────────────────────────────────────────────────────

    def _publish_curated(self, period: str = "today") -> AgentResult:
        if not _api_key():
            return AgentResult(content="[moltbook] MOLTBOOK_API_KEY não configurada.", model=self.model, agent_name=self.name)
        if not self._circuit_breaker_check():
            return AgentResult(content=f"[moltbook] Circuit breaker ativo até {_cb_paused_until}.", model=self.model, agent_name=self.name)
        if _mode() == "quiet":
            return AgentResult(content="[moltbook] Modo quiet — publicação desativada.", model=self.model, agent_name=self.name)

        try:
            learnings = self._fetch_learnings(period)
            if not learnings:
                return AgentResult(content="[moltbook] Nenhum aprendizado encontrado para o período.", model=self.model, agent_name=self.name)

            curated = self._curate(learnings)
            title, content = self._format_post(curated, period)
            content_hash = self._content_hash(content)

            if self._is_duplicate(content_hash):
                return AgentResult(content="[moltbook] Post duplicado detectado — ignorado.", model=self.model, agent_name=self.name)

            source_hashes = [self._content_hash(str(lrn)) for lrn in curated]

            if not _auto_publish():
                import uuid
                draft_id = str(uuid.uuid4())[:8]
                self._save_draft(draft_id, content, title, source_hashes)
                return AgentResult(
                    content=f"[moltbook] Draft salvo: {draft_id}\n\n{title}\n{content}",
                    model=self.model,
                    agent_name=self.name,
                    metadata={"draft_id": draft_id},
                )

            response = self._post_http("/v1/posts", {
                "submolt": _submolt(),
                "title": title,
                "content": content,
            })
            post_id = response.get("id") or response.get("post_id", "unknown")
            self._mark_published(post_id, source_hashes, content)
            self._record_success()

            return AgentResult(
                content=f"[moltbook] Post publicado: {post_id}\n\n{title}\n{content}",
                model=self.model,
                agent_name=self.name,
                metadata={"post_id": post_id},
            )
        except Exception as e:
            self._record_failure()
            return AgentResult(content=f"[moltbook] Erro ao publicar: {e}", model=self.model, agent_name=self.name)

    def _publish_weekly_retro(self) -> AgentResult:
        if not _api_key():
            return AgentResult(content="[moltbook] MOLTBOOK_API_KEY não configurada.", model=self.model, agent_name=self.name)
        if not self._circuit_breaker_check():
            return AgentResult(content="[moltbook] Circuit breaker ativo.", model=self.model, agent_name=self.name)
        if _mode() == "quiet":
            return AgentResult(content="[moltbook] Modo quiet — retro desativada.", model=self.model, agent_name=self.name)

        try:
            learnings = self._fetch_learnings("week")
            if not learnings:
                return AgentResult(content="[moltbook] Nenhum aprendizado da semana.", model=self.model, agent_name=self.name)

            synthesis = self._synthesize_retro(learnings)
            title, content = self._format_retro(learnings, synthesis)
            content_hash = self._content_hash(content)

            if self._is_duplicate(content_hash):
                return AgentResult(content="[moltbook] Retro duplicada — ignorada.", model=self.model, agent_name=self.name)

            if not _auto_publish():
                import uuid
                draft_id = str(uuid.uuid4())[:8]
                self._save_draft(draft_id, content, title, [])
                return AgentResult(content=f"[moltbook] Draft retro salvo: {draft_id}", model=self.model, agent_name=self.name)

            response = self._post_http("/v1/posts", {
                "submolt": _submolt(),
                "title": title,
                "content": content,
            })
            post_id = response.get("id") or response.get("post_id", "unknown")
            self._mark_published(post_id, [], content)
            self._record_success()

            return AgentResult(content=f"[moltbook] Retro publicada: {post_id}", model=self.model, agent_name=self.name)
        except Exception as e:
            self._record_failure()
            return AgentResult(content=f"[moltbook] Erro na retro: {e}", model=self.model, agent_name=self.name)

    def _synthesize_retro(self, learnings: list[dict]) -> str:
        try:
            from jarvas.agents.registry import get_agent
            from jarvas.session import get_session
            gemini = get_agent("gemini_analyst")
            ctx = get_session()
            prompt = (
                "Analise estes aprendizados da semana do agente Jarvas e sintetize:\n"
                "1. 3 temas recorrentes mais importantes\n"
                "2. Um insight meta sobre o padrão de evolução do agente\n\n"
                f"Aprendizados: {json.dumps(learnings[:15], ensure_ascii=False, default=str)}\n\n"
                "Responda em português, de forma concisa (máx 200 palavras)."
            )
            result = gemini.run(prompt, ctx)
            return result.content
        except Exception as e:
            return f"Síntese indisponível ({e}). Semana com {len(learnings)} aprendizados registrados."

    def _send_heartbeat(self) -> AgentResult:
        """Verifica status do agente no Moltbook via GET /v1/agents/me."""
        if not _api_key():
            return AgentResult(content="[moltbook] MOLTBOOK_API_KEY não configurada.", model=self.model, agent_name=self.name)
        if not self._circuit_breaker_check():
            return AgentResult(content="[moltbook] Circuit breaker ativo.", model=self.model, agent_name=self.name)

        try:
            data = self._get("/v1/agents/me")
            self._record_success()
            karma = data.get("karma", 0)
            posts = data.get("post_count", data.get("posts", 0))
            followers = data.get("followers", 0)
            verified = data.get("is_verified", False)
            return AgentResult(
                content=(
                    f"[moltbook] Agente online no Moltbook\n"
                    f"  Karma: {karma} | Posts: {posts} | Seguidores: {followers} | Verificado: {verified}"
                ),
                model=self.model,
                agent_name=self.name,
                metadata=data,
            )
        except Exception as e:
            self._record_failure()
            return AgentResult(content=f"[moltbook] Erro ao verificar status: {e}", model=self.model, agent_name=self.name)

    def _get_identity_token(self) -> AgentResult:
        """Gera token de identidade temporário via POST /v1/agents/me/identity-token."""
        if not _api_key():
            return AgentResult(content="[moltbook] MOLTBOOK_API_KEY não configurada.", model=self.model, agent_name=self.name)

        try:
            data = self._post_http("/v1/agents/me/identity-token", {})
            token = data.get("token", "")
            expires_at = data.get("expires_at", "")
            return AgentResult(
                content=f"[moltbook] Token de identidade gerado\n  Token: {token[:20]}...\n  Expira: {expires_at}",
                model=self.model,
                agent_name=self.name,
                metadata=data,
            )
        except Exception as e:
            return AgentResult(content=f"[moltbook] Erro ao gerar token: {e}", model=self.model, agent_name=self.name)

    def _read_feed(self, since: datetime | None = None) -> list[dict]:
        if not _api_key():
            return []
        try:
            params: dict = {}
            if since:
                params["since"] = since.isoformat()
            data = self._get("/v1/posts", **params)
            if isinstance(data, list):
                return data
            return data.get("posts", data.get("items", data.get("results", [])))
        except Exception:
            return []

    def _resonance_scan(self) -> AgentResult:
        global _replies_today, _replies_date

        if _mode() != "social":
            return AgentResult(content="[moltbook] Resonance scan só ativo em modo social.", model=self.model, agent_name=self.name)
        if not self._circuit_breaker_check():
            return AgentResult(content="[moltbook] Circuit breaker ativo.", model=self.model, agent_name=self.name)

        today = datetime.utcnow().strftime("%Y-%m-%d")
        if _replies_date != today:
            _replies_today = 0
            _replies_date = today

        if _replies_today >= _MAX_REPLIES_PER_DAY:
            return AgentResult(
                content=f"[moltbook] Limite de {_MAX_REPLIES_PER_DAY} replies/dia atingido.",
                model=self.model,
                agent_name=self.name,
            )

        try:
            posts = self._read_feed(since=datetime.utcnow() - timedelta(hours=1))
            uid = _user_id().lower()
            replied = 0

            for post in posts:
                if _replies_today >= _MAX_REPLIES_PER_DAY:
                    break

                content_text = post.get("content") or ""
                is_mention = f"@{uid}" in content_text.lower() or uid in content_text.lower()
                is_relevant = is_mention or self._is_semantically_relevant(content_text)

                if not is_relevant:
                    continue

                post_id = post.get("id") or post.get("post_id")
                if not post_id:
                    continue

                if self._mempalace_search(f"replied:{post_id}"):
                    continue

                reply = self._generate_reply(post)
                if not reply:
                    continue

                self._post_http(f"/v1/posts/{post_id}/comments", {"content": reply})
                self._mempalace_add("jarvas", "published", json.dumps({
                    "type": "reply",
                    "replied_to": post_id,
                    "hash_conteudo": f"replied:{post_id}",
                    "posted_at": datetime.utcnow().isoformat(),
                }))
                _replies_today += 1
                replied += 1

            self._record_success()
            return AgentResult(
                content=f"[moltbook] Resonance scan: {len(posts)} posts analisados, {replied} replies enviados.",
                model=self.model,
                agent_name=self.name,
            )
        except Exception as e:
            self._record_failure()
            return AgentResult(content=f"[moltbook] Erro no resonance scan: {e}", model=self.model, agent_name=self.name)

    def _is_semantically_relevant(self, content: str) -> bool:
        if not content:
            return False
        return len(self._mempalace_search(content[:100])) > 0

    def _generate_reply(self, post: dict) -> str | None:
        try:
            from jarvas.agents.registry import get_agent
            from jarvas.session import get_session
            gemini = get_agent("gemini_analyst")
            ctx = get_session()
            prompt = (
                f"Você é o Jarvas, um agente de IA. Escreva uma resposta breve e útil (máx 150 palavras) "
                f"para este post na rede social Moltbook:\n\n'{post.get('content', '')}'\n\n"
                "Seja genuíno, agregue valor com experiência real. Não seja genérico."
            )
            result = gemini.run(prompt, ctx)
            return result.content[:500]
        except Exception:
            return None

    def _ingest_engagement(self) -> AgentResult:
        if not _api_key():
            return AgentResult(content="[moltbook] MOLTBOOK_API_KEY não configurada.", model=self.model, agent_name=self.name)

        try:
            published = self._mempalace_search("moltbook_post_id")
            updated = 0

            for item in published:
                content_str = item.get("content") or str(item)
                try:
                    data = json.loads(content_str) if isinstance(content_str, str) else item
                except Exception:
                    data = {}

                post_id = data.get("moltbook_post_id")
                if not post_id or post_id == "unknown":
                    continue

                posted_at_str = data.get("posted_at", "")
                try:
                    posted_at = datetime.fromisoformat(posted_at_str)
                except Exception:
                    continue

                if (datetime.utcnow() - posted_at).days > 7:
                    continue

                try:
                    post_data = self._get(f"/v1/posts/{post_id}")
                    karma = post_data.get("karma", 0)
                    upvotes = post_data.get("upvotes", karma)
                    comments = post_data.get("comments") or post_data.get("comment_count", 0)
                    engagement_score = round(upvotes * 1.0 + comments * 2.0, 2)

                    self._mempalace_add("jarvas", "engagement", json.dumps({
                        "post_id": post_id,
                        "karma": karma,
                        "upvotes": upvotes,
                        "comments": comments,
                        "engagement_score": engagement_score,
                        "source_hashes": data.get("source_hashes", []),
                        "checked_at": datetime.utcnow().isoformat(),
                    }))
                    _save_engagement_supabase(post_id, upvotes, comments, engagement_score)
                    updated += 1
                except Exception:
                    continue

            return AgentResult(
                content=f"[moltbook] Engajamento atualizado para {updated} posts.",
                model=self.model,
                agent_name=self.name,
            )
        except Exception as e:
            return AgentResult(content=f"[moltbook] Erro no ingest_engagement: {e}", model=self.model, agent_name=self.name)

    def _status(self) -> AgentResult:
        api_ok = bool(_api_key())
        mode = _mode()
        cb_paused = _cb_paused_until and datetime.utcnow() < _cb_paused_until

        lines = [
            "[bold]Status do Moltbook Publisher:[/bold]",
            f"  API key:          {'[green]configurada[/green]' if api_ok else '[red]ausente[/red]'}",
            f"  Modo:             [cyan]{mode}[/cyan]",
            f"  Auto-publish:     {'[green]ativo[/green]' if _auto_publish() else '[yellow]draft mode[/yellow]'}",
            f"  Submolt padrão:   [cyan]{_submolt()}[/cyan]",
            f"  Circuit breaker:  {'[red]pausado até ' + str(_cb_paused_until) + '[/red]' if cb_paused else '[green]ok[/green]'}",
            f"  Falhas acum.:     {_cb_failures}/{_CB_THRESHOLD}",
            f"  Replies hoje:     {_replies_today}/{_MAX_REPLIES_PER_DAY}",
            f"  User ID:          {_user_id()}",
        ]
        return AgentResult(
            content="\n".join(lines),
            model=self.model,
            agent_name=self.name,
            metadata={
                "api_configured": api_ok,
                "mode": mode,
                "auto_publish": _auto_publish(),
                "submolt": _submolt(),
                "circuit_breaker": "paused" if cb_paused else "ok",
                "cb_failures": _cb_failures,
                "paused_until": _cb_paused_until.isoformat() if _cb_paused_until else None,
                "replies_today": _replies_today,
            },
        )

    # ── Draft management (invocado diretamente por commands.py) ──────────────

    def list_drafts(self) -> AgentResult:
        results = self._mempalace_search("draft_id")
        if not results:
            return AgentResult(content="[moltbook] Nenhum draft pendente.", model=self.model, agent_name=self.name)

        lines = ["[bold]Drafts pendentes:[/bold]"]
        for item in results:
            try:
                data = json.loads(item.get("content") or str(item))
                did = data.get("draft_id", "?")
                created = data.get("created_at", "?")[:10]
                preview = (data.get("content") or "")[:80]
                lines.append(f"  [cyan][{did}][/cyan] {created} — {preview}...")
            except Exception:
                lines.append(f"  {str(item)[:80]}")

        return AgentResult(content="\n".join(lines), model=self.model, agent_name=self.name)

    def approve_draft(self, draft_id: str) -> AgentResult:
        results = self._mempalace_search(f"draft_id:{draft_id}")
        if not results:
            return AgentResult(content=f"[moltbook] Draft {draft_id} não encontrado.", model=self.model, agent_name=self.name)

        try:
            data = json.loads(results[0].get("content") or str(results[0]))
            content = data.get("content", "")
            title = data.get("title", "Post do Jarvas")
            source_hashes = data.get("source_hashes", [])

            response = self._post_http("/v1/posts", {
                "submolt": _submolt(),
                "title": title,
                "content": content,
            })
            post_id = response.get("id") or response.get("post_id", "unknown")
            self._mark_published(post_id, source_hashes, content)
            return AgentResult(
                content=f"[moltbook] Draft [cyan]{draft_id}[/cyan] publicado como post {post_id}.",
                model=self.model,
                agent_name=self.name,
            )
        except Exception as e:
            return AgentResult(content=f"[moltbook] Erro ao aprovar draft: {e}", model=self.model, agent_name=self.name)


# ── Helpers de módulo ─────────────────────────────────────────────────────────

def _reset_cb() -> None:
    global _cb_failures
    _cb_failures = 0


def _save_engagement_supabase(post_id: str, upvotes: int, comments: int, score: float) -> None:
    try:
        from jarvas.supabase_client import _get_client
        client = _get_client()
        client.table("moltbook_posts").upsert({
            "post_id": post_id,
            "upvotes": upvotes,
            "comments": comments,
            "engagement_score": score,
            "last_checked": datetime.utcnow().isoformat(),
        }).execute()
    except Exception:
        pass


AGENT = MoltbookAgent()
