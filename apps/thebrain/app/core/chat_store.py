from __future__ import annotations
import uuid
import json
from typing import Any
from app.core.database import connect
from app.core.contracts import utc_now

def create_conversation(conversation_id: str | None, title: str = "New chat") -> str:
    conversation_id = conversation_id or str(uuid.uuid4())
    now = utc_now()
    with connect() as con:
        row = con.execute("SELECT id FROM conversations WHERE id=?", (conversation_id,)).fetchone()
        if not row:
            con.execute("INSERT INTO conversations(id,title,created_at,updated_at) VALUES(?,?,?,?)", (conversation_id, title[:100] or "New chat", now, now))
    return conversation_id

def save_message(conversation_id: str, role: str, content: str, metadata: dict[str, Any] | None = None) -> str:
    message_id = str(uuid.uuid4())
    now = utc_now()
    with connect() as con:
        con.execute("INSERT INTO messages(id,conversation_id,role,content,created_at,metadata_json) VALUES(?,?,?,?,?,?)",
                    (message_id, conversation_id, role, content, now, json.dumps(metadata or {}, ensure_ascii=False)))
        con.execute("UPDATE conversations SET updated_at=?, title=CASE WHEN title='New chat' AND ?='user' THEN substr(?,1,70) ELSE title END WHERE id=?",
                    (now, role, content, conversation_id))
    return message_id

def get_history(conversation_id: str) -> list[dict[str, Any]]:
    with connect() as con:
        rows = con.execute("SELECT id,role,content,created_at,metadata_json FROM messages WHERE conversation_id=? ORDER BY created_at", (conversation_id,)).fetchall()
    return [{"id": r["id"], "role": r["role"], "content": r["content"], "created_at": r["created_at"], "metadata": json.loads(r["metadata_json"])} for r in rows]
