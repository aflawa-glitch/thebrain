from __future__ import annotations

from typing import Any
from copy import deepcopy
from .database import get_setting, put_setting, connect
from .contracts import utc_now

DEFAULTS: dict[str, Any] = {
    "global": {
        "language": "id-ID-slang", "persona_name": "Julian", "persona_profile": "Casual, modern Indonesian slang. Use gue/lo consistently. Be proactive, candid, evidence-led, and never pretend to know what is unverified.",
        "initiative": "balanced", "evidence_strictness": "high", "multilingual_input": True,
        "unknown_term_behavior": "ask_or_suggest_glossary", "show_process_status": True,
    },
    "modules": {
        "chat": {"enabled": True, "temperature": 0.45},
        "research": {"enabled": True, "minimum_sources": 2, "require_opened_content_for_quotes": True},
        "memory": {"enabled": True, "retrieve_project_memory": True},
        "coding": {"enabled": True},
        "file_ingestion": {"enabled": True},
        "app_builder": {"enabled": True},
        "learning": {"enabled": True, "auto_apply_policy_changes": False},
    },
    "privacy": {"save_chat_history": True, "save_uploaded_content": True, "save_research_content": True},
    "context": {"max_chars": 24000, "preserve_constraints": True, "preserve_evidence_provenance": True},
}


def get_all_settings() -> dict[str, Any]:
    saved = get_setting("application", {})
    return _merge(DEFAULTS, saved)


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    # Return an isolated settings tree; callers may edit it before sending a patch.
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def update_settings(patch: dict[str, Any]) -> dict[str, Any]:
    current = get_all_settings()
    merged = _merge(current, patch)
    # Protect invariants and reject malformed values rather than letting them degrade runtime behavior.
    merged.setdefault("global", {})["multilingual_input"] = True
    merged.setdefault("modules", {}).setdefault("learning", {})["auto_apply_policy_changes"] = False
    context_chars = merged.setdefault("context", {}).get("max_chars", 24000)
    if not isinstance(context_chars, int) or isinstance(context_chars, bool) or not 4000 <= context_chars <= 100000:
        raise ValueError("context.max_chars must be an integer between 4000 and 100000.")
    minimum_sources = merged.setdefault("modules", {}).setdefault("research", {}).get("minimum_sources", 2)
    if not isinstance(minimum_sources, int) or isinstance(minimum_sources, bool) or not 1 <= minimum_sources <= 8:
        raise ValueError("modules.research.minimum_sources must be an integer between 1 and 8.")
    temperature = merged.setdefault("modules", {}).setdefault("chat", {}).get("temperature", 0.45)
    if not isinstance(temperature, (int, float)) or isinstance(temperature, bool) or not 0 <= temperature <= 1.5:
        raise ValueError("modules.chat.temperature must be between 0 and 1.5.")
    put_setting("application", merged)
    return merged


def list_glossary() -> list[dict[str, Any]]:
    with connect() as con:
        rows = con.execute("SELECT term,definition,language,created_at,updated_at FROM glossary ORDER BY term COLLATE NOCASE").fetchall()
    return [dict(row) for row in rows]


def save_glossary(term: str, definition: str, language: str = "") -> dict[str, Any]:
    term, definition = term.strip(), definition.strip()
    if not term or not definition:
        raise ValueError("Term and definition are required.")
    if len(term) > 160 or len(definition) > 4000:
        raise ValueError("Term or definition exceeds the allowed length.")
    now = utc_now()
    with connect() as con:
        con.execute("INSERT INTO glossary(term,definition,language,created_at,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(term) DO UPDATE SET definition=excluded.definition,language=excluded.language,updated_at=excluded.updated_at",
                    (term, definition, language.strip(), now, now))
        row = con.execute("SELECT term,definition,language,created_at,updated_at FROM glossary WHERE term=?", (term,)).fetchone()
    return dict(row)


def delete_glossary(term: str) -> bool:
    with connect() as con:
        cursor = con.execute("DELETE FROM glossary WHERE term=? COLLATE NOCASE", (term.strip(),))
    return cursor.rowcount > 0


def glossary_context(limit: int = 80) -> str:
    items = list_glossary()[:limit]
    if not items:
        return ""
    return "\n".join(f"- {item['term']}: {item['definition']}" for item in items)
