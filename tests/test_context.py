import uuid
from jarvas.context import SessionContext


def test_session_context_defaults():
    ctx = SessionContext()
    assert isinstance(ctx.session_id, str)
    assert len(ctx.session_id) == 36  # UUID format
    assert ctx.project_path is None
    assert ctx.historico == []
    assert ctx.last_pipeline_result is None
    assert ctx.last_debate_result is None


def test_session_context_custom_id():
    sid = str(uuid.uuid4())
    ctx = SessionContext(session_id=sid)
    assert ctx.session_id == sid


def test_session_context_project_path():
    ctx = SessionContext(project_path="C:/projetos/ocr")
    assert ctx.project_path == "C:/projetos/ocr"


def test_session_context_historico_isolation():
    ctx1 = SessionContext()
    ctx2 = SessionContext()
    ctx1.historico.append({"role": "user", "content": "oi"})
    assert ctx2.historico == []
