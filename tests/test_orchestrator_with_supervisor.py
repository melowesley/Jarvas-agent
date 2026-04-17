"""v0.5.0 final: orchestrator.process() sempre roteia via Supervisor."""
from unittest.mock import patch

from jarvas.context import SessionContext
from jarvas.orchestrator import process


def test_process_always_routes_via_supervisor():
    ctx = SessionContext()
    with patch("jarvas.agents.supervisor.route", return_value="sup ok") as mk:
        result = process("oi tudo bem?", ctx)
    mk.assert_called_once()
    assert result == "sup ok"
