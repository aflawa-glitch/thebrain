from __future__ import annotations

import json
import uuid
from typing import Any
from .database import connect
from .contracts import utc_now


def add_memory(kind: str, content: str, source: str = "user", provenance: dict[str, Any] | None = None, supersedes_id: str | None = None) -> dict[str, Any]:
    if kind not in {"session", "project", "preference", "episodic", "sourced_knowledge", "correction"}:
        raise ValueError("Unsupported memory kind.")
    item = {"id": str(uuid.uuid4()), "kind": kind, "content": content.strip(), "source": source,
            "provenance_json": json.dumps(provenance or {}, ensure_ascii=False), "created_at": utc_now(), "supersedes_id": supersedes_id}
    if not item["content"]:
        raise ValueError("Memory content is required.")
    with connect() as con:
        con.execute("INSERT INTO memories(id,kind,content,source,provenance_json,created_at,supersedes_id) VALUES(?,?,?,?,?,?,?)",
                    (item["id"], item["kind"], item["content"], item["source"], item["provenance_json"], item["created_at"], item["supersedes_id"]))
    return {**item, "provenance": provenance or {}}


def retrieve_memories(query: str, limit: int = 6, kinds: list[str] | None = None) -> list[dict[str, Any]]:
    terms = [part.lower() for part in query.split() if len(part) > 2][:8]
    if not terms:
        return []
    clauses = " OR ".join("lower(content) LIKE ?" for _ in terms)
    params: list[Any] = [f"%{term}%" for term in terms]
    where = f"({clauses})"
    if kinds:
        where += " AND kind IN (" + ",".join("?" for _ in kinds) + ")"
        params.extend(kinds)
    params.append(max(1, min(limit, 20)))
    with connect() as con:
        rows = con.execute(f"SELECT id,kind,content,source,provenance_json,created_at,supersedes_id FROM memories WHERE {where} ORDER BY created_at DESC LIMIT ?", params).fetchall()
    out = []
    for row in rows:
        item = dict(row)
        item["provenance"] = json.loads(item.pop("provenance_json"))
        out.append(item)
    return out
