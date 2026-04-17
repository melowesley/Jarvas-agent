"""Shim de compatibilidade — SessionContext agora é Session em session.py."""
from jarvas.session import Session as SessionContext, get_session, reset_session

__all__ = ["SessionContext", "get_session", "reset_session"]
