from __future__ import annotations
from typing import Dict
from app.core.llm import OpenAICompatibleClient
from app.core.config import settings

_clients: Dict[str, OpenAICompatibleClient] = {}

def for_role(role: str = "primary") -> OpenAICompatibleClient:
    """
    Returns an LLM client for a specific role (e.g., 'primary', 'utility').
    Currently returns a singleton per role. 
    In Phase 1.5 (S-10), this will read from config/models.json.
    """
    if role not in _clients:
        _clients[role] = OpenAICompatibleClient()
    return _clients[role]

def clear_cache() -> None:
    """For testing purposes to reset singletons."""
    _clients.clear()
