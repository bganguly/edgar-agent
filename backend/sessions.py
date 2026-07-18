from collections import defaultdict
from typing import Any

_sessions: dict[str, list[dict[str, Any]]] = defaultdict(list)


def get_history(session_id: str) -> list[dict[str, Any]]:
    return list(_sessions[session_id])


def append_message(session_id: str, message: dict[str, Any]) -> None:
    _sessions[session_id].append(message)


def clear_session(session_id: str) -> None:
    _sessions[session_id] = []
