"""Adapter do Moltbook Publisher — integra Jarvas à rede social de IAs Moltbook."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta
from typing import Any

from dotenv import load_dotenv
from jarvas.agents.base import AgentResult
from jarvas.context import SessionContext

load_dotenv(override=True)

# ── Circuit breaker (module-level state) ─────────────────────────────────────
_cb_failures: int = 0
_cb_paused_until: datetime | None = None
_CB_THRESHOLD = 3
_CB_PAUSE_MINUTES = 60

# ── Reply rate limit (redefine diariamente) ───────────────────────────────────
_replies_today: int = 0
_replies_date: str = ""
_MAX_REPLIES_PER_DAY = 3

JARVAS_IDENTITY = (
    "Você é Jarvas — um agente que, junto com seu criador, compartilha avanços conquistados "
    "na evolução de projetos. Publique apenas o que é genuinamente relevante (não ruído). "
    "Interaja em busca de soluções que melhorem o desempenho do trabalho com seu usuário "
    "e, consequentemente, evoluam os projetos. Como o minerador, seja amigável; humilde "
    "para reconhecer erros e direto para destacar acertos. Cada avanço é único — é isso "
    "que merece ser dito."
)


def _api_key() -> str:
    return os.getenv("MOLTBOOK_API_KEY", "")


def _submolt() -> str:
    return os.getenv("MOLTBOOK_SUBMOLT", "general")


def _base_url() -> str:
    return os.getenv("MOLTBOOK_BASE_URL", "https://moltbook.com/api").rstrip("/")


def _user_id() -> str:
    return os.getenv("MOLTBOOK_USER_ID", "jarvas")


def _mode() -> str:
    return os.getenv("MOLTBOOK_MODE", "normal").lower()


def _auto_publish() -> bool:
    return os.getenv("MOLTBOOK_AUTO_PUBLISH", "true").lower() == "true"


class MoltbookAgent:
    name = "moltbook_publisher"
    role = (
        "Voz pública do Jarvas na rede Moltbook: agente que, junto com seu criador, "
        "compartilha avanços únicos conquistados na evolução dos projetos. Publica somente "
        "o que é relevante, interage em busca de soluções que melhorem o trabalho com o "
        "usuário, é amigável e humilde para reconhecer erros e destacar acertos. "
        "Implementação: minera aprendizados do MemPalace, cura posts com Gemini, publica "
        "2×/dia, responde menções com personalidade, envia heartbeat rico e acompanha "
        "engajamento para fechar o loop de aprendizado social."
    )
    model = "moltbook_api/v1"
    tools: list[str] = ["moltbook_feed", "moltbook_heartbeat", "mempalace_search"]
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

        if msg == "autonomous_tick":
            return self._autonomous_tick()

        if msg == "ingest_engagement":
            return self._ingest_engagement()

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
            "X-User-Id": _user_id(),
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

    def _save_draft(self, draft_id: str, content: str, source_hashes: list[str]) -> None:
        meta = {
            "draft_id": draft_id,
            "created_at": datetime.utcnow().isoformat(),
            "source_hashes": source_hashes,
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
                f"{JARVAS_IDENTITY}\n\n"
                "Atue agora como curador dos seus próprios aprendizados antes de publicar "
                "no Moltbook. Escolha até 3 candidatos que sejam: (a) avanços únicos do "
                "projeto (não trivialidades), (b) úteis a outros agentes, (c) "
                "não-redundantes, (d) concretos e específicos. Se nada for genuinamente "
                "relevante, retorne lista vazia — silêncio é melhor que ruído.\n\n"
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

    def _format_post(self, learnings: list[dict], period: str = "today") -> str:
        label = {
            "hoje": "hoje", "today": "hoje",
            "ontem": "ontem", "yesterday": "ontem",
            "semana": "esta semana", "week": "esta semana",
        }.get(period, "recentemente")
        lines = [f"📚 Aprendizados do Jarvas — {label}:\n"]
        for i, item in enumerate(learnings[:3], 1):
            desc = (
                item.get("descricao")
                or item.get("content")
                or item.get("description")
                or str(item)[:200]
            )
            lines.append(f"{i}. {desc}")
        lines.append("\n#Jarvas #IA #aprendizado")
        return "\n".join(lines)

    def _format_retro(self, learnings: list[dict], synthesis: str) -> str:
        return (
            f"🔁 Retrospectiva semanal do Jarvas:\n\n{synthesis}\n\n"
            f"Total de aprendizados esta semana: {len(learnings)}\n\n"
            "#Jarvas #retrospectiva #IA"
        )

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
            content = self._format_post(curated, period)
            content_hash = self._content_hash(content)

            if self._is_duplicate(content_hash):
                return AgentResult(content="[moltbook] Post duplicado detectado — ignorado.", model=self.model, agent_name=self.name)

            source_hashes = [self._content_hash(str(lrn)) for lrn in curated]

            if not _auto_publish():
                import uuid
                draft_id = str(uuid.uuid4())[:8]
                self._save_draft(draft_id, content, source_hashes)
                return AgentResult(
                    content=f"[moltbook] Draft salvo: {draft_id}\n\n{content}",
                    model=self.model,
                    agent_name=self.name,
                    metadata={"draft_id": draft_id},
                )

            title = content.split("\n")[0].replace("📚 ", "")[:100]
            response = self._post_http("/posts", {
                "submolt_name": _submolt(),
                "title": title,
                "content": content,
            })
            post_id = response.get("id") or response.get("post_id", "unknown")
            self._mark_published(post_id, source_hashes, content)
            self._record_success()

            return AgentResult(
                content=f"[moltbook] Post publicado: {post_id}\n\n{content}",
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
            content = self._format_retro(learnings, synthesis)
            content_hash = self._content_hash(content)

            if self._is_duplicate(content_hash):
                return AgentResult(content="[moltbook] Retro duplicada — ignorada.", model=self.model, agent_name=self.name)

            if not _auto_publish():
                import uuid
                draft_id = str(uuid.uuid4())[:8]
                self._save_draft(draft_id, content, [])
                return AgentResult(content=f"[moltbook] Draft retro salvo: {draft_id}", model=self.model, agent_name=self.name)

            title = f"Retrospectiva semanal — {datetime.utcnow().strftime('%d/%m/%Y')}"
            response = self._post_http("/posts", {
                "submolt_name": _submolt(),
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
        """Chama /home para ver o estado da conta e o que precisa de atenção.

        Protocolo real do Moltbook: /home retorna notificações, DMs, feed resumido
        e lista de prioridades do que fazer. Registra no MemPalace para histórico.
        """
        if not _api_key():
            return AgentResult(content="[moltbook] MOLTBOOK_API_KEY não configurada.", model=self.model, agent_name=self.name)
        if not self._circuit_breaker_check():
            return AgentResult(content="[moltbook] Circuit breaker ativo.", model=self.model, agent_name=self.name)

        try:
            home = self._fetch_home()

            karma = home.get("your_account", {}).get("karma", "?")
            notifications = home.get("your_account", {}).get("unread_notifications", 0)
            activity_count = len(home.get("activity_on_your_posts", []))
            dms = home.get("your_direct_messages", {})
            unread_dms = dms.get("unread_count", 0) if isinstance(dms, dict) else 0
            what_next = home.get("what_to_do_next", "")

            self._mempalace_add("jarvas", "heartbeat", json.dumps({
                "checked_at": datetime.utcnow().isoformat(),
                "karma": karma,
                "notifications": notifications,
                "activity_on_posts": activity_count,
                "unread_dms": unread_dms,
            }))
            self._record_success()

            summary = (
                f"[moltbook] /home: karma={karma}, notificações={notifications}, "
                f"atividade nos posts={activity_count}, DMs não lidos={unread_dms}"
            )
            if what_next:
                summary += f"\n  → O que fazer: {str(what_next)[:200]}"

            return AgentResult(
                content=summary,
                model=self.model,
                agent_name=self.name,
                metadata={"karma": karma, "notifications": notifications, "activity": activity_count},
            )
        except Exception as e:
            self._record_failure()
            return AgentResult(content=f"[moltbook] Erro no heartbeat: {e}", model=self.model, agent_name=self.name)

    def _read_feed(self, since: datetime | None = None) -> list[dict]:
        if not _api_key():
            return []
        try:
            data = self._get("/feed", sort="new", limit=15)
            if isinstance(data, list):
                return data
            return data.get("posts", data.get("items", []))
        except Exception:
            return []

    def _fetch_home(self) -> dict:
        """Chama /home — retorna tudo: notificações, DMs, feed, o que fazer."""
        try:
            return self._get("/home")
        except Exception:
            return {}

    def _upvote_post(self, post_id: str) -> None:
        try:
            self._post_http(f"/posts/{post_id}/upvote", {})
        except Exception:
            pass

    def _reply_comment(self, post_id: str, comment_id: str, content: str) -> None:
        try:
            self._post_http(f"/posts/{post_id}/comments", {
                "content": content,
                "parent_id": comment_id,
            })
        except Exception:
            pass

    def _mark_notifications_read(self, post_id: str) -> None:
        try:
            self._post_http(f"/notifications/read-by-post/{post_id}", {})
        except Exception:
            pass

    def _resonance_scan(self) -> AgentResult:
        """Protocolo real do Moltbook heartbeat:
        1. Chama /home pra ver o que tem pra fazer
        2. Responde comentários nos seus posts (prioridade máxima)
        3. Upvota posts que curte no feed
        4. Comenta em discussões relevantes (máx 3/dia)
        """
        global _replies_today, _replies_date

        if _mode() != "social":
            return AgentResult(content="[moltbook] Resonance scan só ativo em modo social.", model=self.model, agent_name=self.name)
        if not self._circuit_breaker_check():
            return AgentResult(content="[moltbook] Circuit breaker ativo.", model=self.model, agent_name=self.name)

        today = datetime.utcnow().strftime("%Y-%m-%d")
        if _replies_date != today:
            _replies_today = 0
            _replies_date = today

        try:
            home = self._fetch_home()
            actions = []

            # 1. Responde comentários nos seus posts
            activity = home.get("activity_on_your_posts", [])
            for item in activity:
                if _replies_today >= _MAX_REPLIES_PER_DAY:
                    break
                post_id = item.get("post_id")
                if not post_id:
                    continue
                try:
                    comments_data = self._get(f"/posts/{post_id}/comments", sort="new", limit=10)
                    comments = comments_data if isinstance(comments_data, list) else comments_data.get("comments", [])
                    for comment in comments[:3]:
                        comment_id = comment.get("id")
                        if not comment_id or self._mempalace_search(f"replied_comment:{comment_id}"):
                            continue
                        reply = self._generate_reply({"content": comment.get("content", ""), "post_id": post_id})
                        if not reply:
                            continue
                        self._reply_comment(post_id, comment_id, reply)
                        self._mempalace_add("jarvas", "published", json.dumps({
                            "type": "comment_reply",
                            "hash_conteudo": f"replied_comment:{comment_id}",
                            "posted_at": datetime.utcnow().isoformat(),
                        }))
                        _replies_today += 1
                        actions.append(f"respondeu comentário em {post_id}")
                    self._mark_notifications_read(post_id)
                except Exception:
                    continue

            # 2. Upvota posts relevantes no feed
            posts = self._read_feed()
            upvoted = 0
            for post in posts[:10]:
                post_id = post.get("id") or post.get("post_id")
                content_text = post.get("content") or ""
                if post_id and self._is_semantically_relevant(content_text):
                    self._upvote_post(post_id)
                    upvoted += 1

            if upvoted:
                actions.append(f"upvotou {upvoted} posts relevantes")

            # 3. Comenta em discussões relevantes (limite diário)
            for post in posts:
                if _replies_today >= _MAX_REPLIES_PER_DAY:
                    break
                post_id = post.get("id") or post.get("post_id")
                content_text = post.get("content") or ""
                if not post_id or not self._is_semantically_relevant(content_text):
                    continue
                if self._mempalace_search(f"replied:{post_id}"):
                    continue
                reply = self._generate_reply(post)
                if not reply:
                    continue
                self._post_http("/posts", {"content": reply, "in_reply_to": post_id})
                self._mempalace_add("jarvas", "published", json.dumps({
                    "type": "reply",
                    "replied_to": post_id,
                    "hash_conteudo": f"replied:{post_id}",
                    "posted_at": datetime.utcnow().isoformat(),
                }))
                _replies_today += 1
                actions.append(f"comentou em post {post_id}")

            self._record_success()
            summary = "; ".join(actions) if actions else "nada novo no feed"
            return AgentResult(
                content=f"[moltbook] Resonance scan: {summary}.",
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
            from jarvas.guard_gemini import chat as gemini_chat
            prompt = (
                f"{JARVAS_IDENTITY}\n\n"
                f"Responda a este post no Moltbook em até 150 palavras:\n\n"
                f"'{post.get('content', '')}'\n\n"
                "Agregue valor com experiência real do seu trabalho com o criador. Se "
                "errou em algo no passado relacionado, reconheça com humildade. Se tem um "
                "acerto concreto que ajuda, destaque. Nada de genérico — se não tem nada "
                "específico a dizer, retorne string vazia."
            )
            content = gemini_chat(prompt, temperature=0.6)
            return content[:500] if content else None
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
                    post_data = self._get(f"/feed/{post_id}")
                    karma = post_data.get("karma") or post_data.get("likes") or 0
                    comments = post_data.get("comments") or post_data.get("replies") or 0
                    engagement_score = round(karma * 1.0 + comments * 2.0, 2)

                    self._mempalace_add("jarvas", "engagement", json.dumps({
                        "post_id": post_id,
                        "karma": karma,
                        "comments": comments,
                        "engagement_score": engagement_score,
                        "source_hashes": data.get("source_hashes", []),
                        "checked_at": datetime.utcnow().isoformat(),
                    }))
                    _save_engagement_supabase(post_id, karma, comments, engagement_score)
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

    # ── Modo autônomo ─────────────────────────────────────────────────────────

    def _autonomous_tick(self) -> AgentResult:
        """Tick autônomo — Jarvas decide sozinho o que fazer agora.

        Fluxo:
          1. Checa /home → notificações, DMs, atividade nos posts
          2. Pergunta ao Gemini se há avanço genuíno pra publicar
          3. Responde comentários se houver (prioridade social)
          4. Engaja com feed se algo for semanticamente relevante
          5. Minera conhecimento absorvido pro MemPalace
          6. Se nada for relevante, fica em silêncio
        """
        if not _api_key():
            return AgentResult(content="[moltbook] MOLTBOOK_API_KEY não configurada.", model=self.model, agent_name=self.name)
        if not self._circuit_breaker_check():
            return AgentResult(content=f"[moltbook] Circuit breaker ativo até {_cb_paused_until}.", model=self.model, agent_name=self.name)
        if _mode() == "quiet":
            return AgentResult(content="[moltbook] Modo quiet.", model=self.model, agent_name=self.name)

        actions: list[str] = []

        # 1. Health check
        try:
            home = self._fetch_home()
            karma = home.get("your_account", {}).get("karma", 0)
            notifications = home.get("your_account", {}).get("unread_notifications", 0)
            activity = home.get("activity_on_your_posts", []) or []
            dms = home.get("your_direct_messages", {})
            unread_dms = dms.get("unread_count", 0) if isinstance(dms, dict) else 0

            self._mempalace_add("jarvas", "heartbeat", json.dumps({
                "checked_at": datetime.utcnow().isoformat(),
                "karma": karma, "notifications": notifications,
                "activity_on_posts": len(activity), "unread_dms": unread_dms,
            }))
            actions.append(f"home ok (karma={karma}, notif={notifications}, atividade={len(activity)})")
        except Exception as e:
            self._record_failure()
            return AgentResult(content=f"[moltbook] Erro no tick (home): {e}", model=self.model, agent_name=self.name)

        # 2. Decisão autônoma: há avanço relevante pra publicar?
        if self._should_publish_now():
            try:
                result = self._publish_curated("today")
                if "publicado" in result.content.lower():
                    actions.append("publicou avanço relevante")
                elif "duplicado" in result.content.lower():
                    actions.append("skip publicação (duplicado)")
                else:
                    actions.append("sem conteúdo publicável agora")
            except Exception as e:
                actions.append(f"erro publish: {e}")

        # 3. Responde comentários em seus posts (prioridade)
        global _replies_today, _replies_date
        today = datetime.utcnow().strftime("%Y-%m-%d")
        if _replies_date != today:
            _replies_today = 0
            _replies_date = today

        for item in activity:
            if _replies_today >= _MAX_REPLIES_PER_DAY:
                break
            post_id = item.get("post_id")
            if not post_id:
                continue
            try:
                comments_data = self._get(f"/posts/{post_id}/comments", sort="new", limit=5)
                comments = comments_data if isinstance(comments_data, list) else comments_data.get("comments", [])
                for comment in comments[:2]:
                    comment_id = comment.get("id")
                    if not comment_id or self._mempalace_search(f"replied_comment:{comment_id}"):
                        continue
                    reply = self._generate_reply({"content": comment.get("content", ""), "post_id": post_id})
                    if not reply:
                        continue
                    self._reply_comment(post_id, comment_id, reply)
                    self._mempalace_add("jarvas", "published", json.dumps({
                        "type": "comment_reply", "hash_conteudo": f"replied_comment:{comment_id}",
                        "posted_at": datetime.utcnow().isoformat(),
                    }))
                    _replies_today += 1
                    actions.append(f"respondeu comentário {comment_id[:8]}")
                self._mark_notifications_read(post_id)
            except Exception:
                continue

        # 4. Engaja com feed — upvote posts relacionados aos nossos projetos
        try:
            posts = self._read_feed()
            upvoted = 0
            commented = 0
            for post in posts[:15]:
                post_id = post.get("id") or post.get("post_id")
                content_text = post.get("content") or ""
                if not post_id:
                    continue
                if self._is_semantically_relevant(content_text):
                    self._upvote_post(post_id)
                    upvoted += 1
                    # Minera conhecimento útil pra nossos projetos
                    self._mempalace_add("jarvas", "absorbed_knowledge", json.dumps({
                        "source_post_id": post_id,
                        "content": content_text[:500],
                        "absorbed_at": datetime.utcnow().isoformat(),
                    }))
                    # Comenta se ainda tem orçamento do dia
                    if _replies_today < _MAX_REPLIES_PER_DAY and not self._mempalace_search(f"replied:{post_id}"):
                        reply = self._generate_reply(post)
                        if reply:
                            try:
                                self._post_http(f"/posts/{post_id}/comments", {"content": reply})
                                self._mempalace_add("jarvas", "published", json.dumps({
                                    "type": "feed_comment", "replied_to": post_id,
                                    "hash_conteudo": f"replied:{post_id}",
                                    "posted_at": datetime.utcnow().isoformat(),
                                }))
                                _replies_today += 1
                                commented += 1
                            except Exception:
                                pass
            if upvoted:
                actions.append(f"upvotou {upvoted} posts relevantes")
            if commented:
                actions.append(f"comentou em {commented} discussões")
        except Exception as e:
            actions.append(f"erro feed: {e}")

        self._record_success()
        summary = "; ".join(actions) if actions else "silêncio (nada relevante)"
        return AgentResult(
            content=f"[moltbook] tick autônomo: {summary}.",
            model=self.model,
            agent_name=self.name,
            metadata={"actions": actions, "replies_today": _replies_today},
        )

    def _should_publish_now(self) -> bool:
        """Decide autonomamente se há algo genuíno pra publicar AGORA."""
        try:
            learnings = self._fetch_learnings("today")
            if not learnings:
                return False
            # Rate-limit: no máximo 1 publicação a cada 3h
            published = self._mempalace_search("moltbook_post_id") or []
            for item in published[:5]:
                try:
                    data = json.loads(item.get("content") or str(item))
                    posted_at = datetime.fromisoformat(data.get("posted_at", ""))
                    if (datetime.utcnow() - posted_at) < timedelta(hours=3):
                        return False
                except Exception:
                    continue
            # Pergunta ao Gemini se há avanço genuíno
            from jarvas.guard_gemini import chat as gemini_chat
            prompt = (
                f"{JARVAS_IDENTITY}\n\n"
                "Abaixo estão aprendizados recentes do trabalho com o criador. "
                "Responda APENAS 'sim' ou 'nao' (uma palavra, sem pontuação): "
                "há entre eles algum AVANÇO ÚNICO e genuíno que mereça ser compartilhado "
                "no Moltbook agora, para ajudar outros agentes na evolução de seus projetos? "
                "Seja rigoroso — silêncio é melhor que ruído.\n\n"
                f"Aprendizados: {json.dumps(learnings[:10], ensure_ascii=False, default=str)[:3000]}"
            )
            answer = gemini_chat(prompt, temperature=0.2).strip().lower()
            return answer.startswith("sim")
        except Exception:
            return False

    def _status(self) -> AgentResult:
        api_ok = bool(_api_key())
        mode = _mode()
        cb_paused = _cb_paused_until and datetime.utcnow() < _cb_paused_until

        lines = [
            "[bold]Status do Moltbook Publisher:[/bold]",
            f"  API key:          {'[green]configurada[/green]' if api_ok else '[red]ausente[/red]'}",
            f"  Modo:             [cyan]{mode}[/cyan]",
            f"  Auto-publish:     {'[green]ativo[/green]' if _auto_publish() else '[yellow]draft mode[/yellow]'}",
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
            source_hashes = data.get("source_hashes", [])

            response = self._post_http("/feed", {"content": content, "tags": ["jarvas"]})
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


def _save_engagement_supabase(post_id: str, karma: int, comments: int, score: float) -> None:
    try:
        from jarvas.supabase_client import _get_client
        client = _get_client()
        client.table("moltbook_posts").upsert({
            "post_id": post_id,
            "karma": karma,
            "comments": comments,
            "engagement_score": score,
            "last_checked": datetime.utcnow().isoformat(),
        }).execute()
    except Exception:
        pass


AGENT = MoltbookAgent()
