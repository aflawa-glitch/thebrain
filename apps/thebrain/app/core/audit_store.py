from __future__ import annotations
import json
from typing import Any
from app.core.database import connect

def list_events(trace_id: str) -> list[dict[str, Any]]:
    """Fetch all audit events for a trace, with parsed details."""
    with connect() as con:
        rows = con.execute(
            "SELECT id, conversation_id, stage, status, message, details_json, created_at FROM audit_events WHERE trace_id=? ORDER BY id",
            (trace_id,)
        ).fetchall()
    return [{**dict(row), "details": json.loads(row["details_json"])} for row in rows]

def list_events_for_stream(trace_id: str) -> list[dict[str, Any]]:
    """Streaming variant (omits conversation_id for UI compatibility)."""
    with connect() as con:
        rows = con.execute(
            "SELECT id, stage, status, message, details_json, created_at FROM audit_events WHERE trace_id=? ORDER BY id",
            (trace_id,)
        ).fetchall()
    result = []
    for row in rows:
        payload = dict(row)
        payload["details"] = json.loads(payload.pop("details_json"))
        result.append(payload)
    return result

def list_evidence(trace_id: str) -> list[dict[str, Any]]:
    """Fetch evidence ledger entries for a trace."""
    with connect() as con:
        rows = con.execute(
            "SELECT id, url, title, retrieved_at, open_status, content_status, source_domain, published_at, snippet, error FROM evidence WHERE trace_id=? ORDER BY retrieved_at",
            (trace_id,)
        ).fetchall()
    return [dict(row) for row in rows]
