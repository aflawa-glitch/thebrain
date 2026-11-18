import uuid
from app.core.database import connect
from app.core.contracts import utc_now
from typing import Any

def create_project(title: str, brief: str, project_type: str = "general", attachments: str = "") -> str:
    project_id = str(uuid.uuid4())
    now = utc_now()
    with connect() as con:
        con.execute(
            "INSERT INTO projects(id, title, project_type, brief, attachments, status, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?)",
            (project_id, title, project_type, brief, attachments, "queued", now, now)
        )
    return project_id

def update_project_status(project_id: str, status: str, plan_json: str = None) -> None:
    with connect() as con:
        if plan_json is not None:
            con.execute("UPDATE projects SET status=?, plan_json=?, updated_at=? WHERE id=?", 
                        (status, plan_json, utc_now(), project_id))
        else:
            con.execute("UPDATE projects SET status=?, updated_at=? WHERE id=?", 
                        (status, utc_now(), project_id))

def get_project(project_id: str) -> dict[str, Any] | None:
    with connect() as con:
        row = con.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    return dict(row) if row else None

def get_next_queued_project() -> dict[str, Any] | None:
    with connect() as con:
        row = con.execute("SELECT * FROM projects WHERE status='queued' ORDER BY created_at ASC LIMIT 1").fetchone()
    return dict(row) if row else None

def log_project_activity(project_id: str, agent_name: str, message: str) -> None:
    with connect() as con:
        con.execute(
            "INSERT INTO project_logs(project_id, agent_name, message, created_at) VALUES(?,?,?,?)",
            (project_id, agent_name, message, utc_now())
        )
