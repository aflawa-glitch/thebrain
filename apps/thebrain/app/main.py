from __future__ import annotations

import asyncio
from app.core.project_worker import run_worker_loop
import hashlib
import io
import json
import mimetypes
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pypdf import PdfReader

from app.core.config import settings
from app.core.contracts import RequestContext, utc_now
from app.core import task_registry
from app.core.database import audit, connect, initialize
from app.core.audit_store import list_events, list_events_for_stream, list_evidence
from app.core.ingest import extract
from app.core.chat_store import create_conversation, save_message, get_history
from app.core.database import preflight_database_path
from app.core.llm_factory import for_role
from app.core.memory import add_memory
from app.core.orchestrator import registry, run_request
from app.core.settings_service import get_all_settings, update_settings, list_glossary, save_glossary, delete_glossary

@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        initialize()
        _app.state.startup_blocker = None
    except RuntimeError as exc:
        _app.state.startup_blocker = str(exc)
    
    # Start the background project worker
    worker_task = asyncio.create_task(run_worker_loop())
    
    yield
    
    # Shutdown worker
    worker_task.cancel()
    
    # Shutdown worker
    worker_task.cancel()


app = FastAPI(title=settings.app_name, version="0.1.0", description="Fresh modular implementation of TheBrain / Julian", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


@app.middleware("http")
async def block_incompatible_database(request, call_next):
    blocker = getattr(app.state, "startup_blocker", None)
    if blocker and request.url.path not in {"/", "/api/health"} and not request.url.path.startswith("/static/"):
        return JSONResponse(status_code=503, content={"status": "blocked", "stage": "runtime_preflight", "error_category": "database_schema_incompatible", "detail": blocker, "impact": "Request execution is disabled to avoid modifying an incompatible database.", "next_step": "Back up the database and review schema migration compatibility before retrying."})
    return await call_next(request)


_ephemeral_uploads: dict[str, list[dict[str, str]]] = {}


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=100000)
    conversation_id: str | None = None
    mode: str = "auto"



class GlossaryRequest(BaseModel):
    term: str = Field(min_length=1, max_length=160)
    definition: str = Field(min_length=1, max_length=4000)
    language: str = Field(default="", max_length=40)


class MemoryRequest(BaseModel):
    kind: str = "project"
    content: str = Field(min_length=1, max_length=12000)
    source: str = "user"
    provenance: dict[str, Any] = Field(default_factory=dict)





@app.get("/", response_class=HTMLResponse)
def home() -> FileResponse:
    return FileResponse(Path(__file__).parent / "templates" / "index.html")


@app.get("/api/health")
async def health() -> dict[str, Any]:
    blocker = getattr(app.state, "startup_blocker", None)
    if blocker:
        return {"status": "blocked", "app": settings.app_name, "version": app.version,
                "database": {"status": "incompatible", "error_category": "schema_incompatible", "detail": blocker},
                "model": {"status": "not_checked", "reason": "database preflight blocked runtime"},
                "web_search_enabled": settings.web_search_enabled, "timestamp": utc_now()}
    try:
        db = initialize()
    except RuntimeError as exc:
        app.state.startup_blocker = str(exc)
        return {"status": "blocked", "app": settings.app_name, "version": app.version,
                "database": {"status": "incompatible", "error_category": "schema_incompatible", "detail": str(exc)},
                "model": {"status": "not_checked", "reason": "database preflight blocked runtime"},
                "web_search_enabled": settings.web_search_enabled, "timestamp": utc_now()}
    model = await for_role('primary').health()
    # Do not report a fully healthy runtime merely because FastAPI and SQLite respond.
    # The configured model is required for Phase 1 chat/reasoning capability parity.
    runtime_status = "ok" if model.get("status") == "reachable" else "degraded"
    return {"status": runtime_status, "app": settings.app_name, "version": app.version, "database": db, "model": model,
            "readiness": {"backend": "ready", "database": db.get("status", "unknown"),
                          "model": model.get("status", "unknown"),
                          "phase1_ready": runtime_status == "ok"},
            "web_search_enabled": settings.web_search_enabled, "timestamp": utc_now()}


@app.get("/api/capabilities")
def capabilities() -> dict[str, Any]:
    return {"capabilities": registry.list(), "count": len(registry.names())}


@app.get("/api/conversations")
def conversations() -> dict[str, Any]:
    with connect() as con:
        rows = con.execute("SELECT id,title,created_at,updated_at,is_pinned FROM conversations ORDER BY is_pinned DESC, updated_at DESC LIMIT 100").fetchall()
    return {"conversations": [dict(r) for r in rows]}



@app.post("/api/conversations")
def new_conversation() -> dict[str, Any]:
    conversation_id = create_conversation(None)
    return {"conversation_id": conversation_id, "messages": []}


@app.get("/api/conversations/{conversation_id}")
def conversation(conversation_id: str) -> dict[str, Any]:
    with connect() as con:
        row = con.execute("SELECT id,title,created_at,updated_at FROM conversations WHERE id=?", (conversation_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Conversation not found.")
    return {"conversation": dict(row), "messages": get_history(conversation_id)}


async def _execute_chat(req: ChatRequest, context: RequestContext) -> dict[str, Any]:
    file_context = ""
    with connect() as con:
        rows = con.execute("SELECT filename,extracted_text,sha256 FROM uploads WHERE conversation_id=? ORDER BY created_at DESC LIMIT 5", (context.conversation_id,)).fetchall()
    persisted_context = [f"FILE: {r['filename']} (SHA-256 {r['sha256']})\n{r['extracted_text'][:12000]}" + ("\n[This request received only the first 12,000 characters of the extracted file. Do not assume the rest was read.]" if len(r['extracted_text']) > 12000 else "") for r in rows]
    ephemeral_context = [f"FILE: {r['filename']} (SHA-256 {r['sha256']})\n{r['extracted_text'][:12000]}" + ("\n[This request received only the first 12,000 characters of the extracted file. Do not assume the rest was read.]" if len(r['extracted_text']) > 12000 else "") for r in _ephemeral_uploads.get(context.conversation_id, [])]
    file_context = "\n\n".join(persisted_context + ephemeral_context)
    settings_blob = get_all_settings()
    with connect() as con:
        history_rows = con.execute("SELECT role,content FROM messages WHERE conversation_id=? ORDER BY created_at DESC LIMIT 12", (context.conversation_id,)).fetchall()
    context.settings["history"] = [{"role": row["role"], "content": row["content"][:6000]} for row in reversed(history_rows)][:-1]
    context.settings["save_chat_history"] = bool(settings_blob.get("privacy", {}).get("save_chat_history", True))
    # Include ephemeral uploads too; otherwise privacy-preserving uploads reach the prompt but are routed as general chat.
    has_files = bool(rows) or bool(_ephemeral_uploads.get(context.conversation_id))
    try:
        result = await run_request(req.message, context, has_files=has_files, file_context=file_context, requested_mode=req.mode)
        if context.settings["save_chat_history"]:
            save_message(context.conversation_id, "assistant", result["answer"], {"trace_id": result["trace_id"], "status": result["status"], "route": result["route"], "evidence": result["evidence"], "verification": result.get("verification"), "warnings": result.get("warnings"), "research_metadata": result.get("research_metadata")})
        return result
    finally:
        # Privacy-preserving upload content must be discarded even when the task fails or is cancelled.
        _ephemeral_uploads.pop(context.conversation_id, None)



class ConversationUpdate(BaseModel):
    title: str | None = None
    is_pinned: bool | None = None

@app.put("/api/conversations/{conversation_id}")
def update_conversation(conversation_id: str, req: ConversationUpdate) -> dict[str, Any]:
    with connect() as con:
        if req.title is not None:
            con.execute("UPDATE conversations SET title=? WHERE id=?", (req.title[:100], conversation_id))
        if req.is_pinned is not None:
            con.execute("UPDATE conversations SET is_pinned=? WHERE id=?", (1 if req.is_pinned else 0, conversation_id))
    return {"status": "ok"}

@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: str) -> dict[str, Any]:
    with connect() as con:
        con.execute("DELETE FROM messages WHERE conversation_id=?", (conversation_id,))
        con.execute("DELETE FROM conversations WHERE id=?", (conversation_id,))
    return {"status": "deleted"}


class ProjectRequest(BaseModel):
    title: str
    brief: str
    attachments: str = "[]"


import io
import zipfile



class ChatToProjectRequest(BaseModel):
    conversation_id: str
    title: str

@app.post("/api/projects/from-chat")
def create_project_from_chat(req: ChatToProjectRequest) -> dict[str, Any]:
    from app.core.database import connect
    from app.core.contracts import utc_now
    import uuid
    
    project_id = str(uuid.uuid4())
    
    with connect() as con:
        # Get the last 10 messages from the chat to use as the brief
        rows = con.execute("SELECT role, content FROM messages WHERE conversation_id=? ORDER BY created_at DESC LIMIT 10", (req.conversation_id,)).fetchall()
        chat_history = "\n".join([f"{r['role']}: {r['content']}" for r in reversed(rows)])
        brief = f"Build the app discussed in this chat history:\n\n{chat_history}"
        
        con.execute("INSERT INTO projects(id, title, project_type, brief, attachments, status, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?)",
                    (project_id, req.title, "software", brief, "[]", "queued", utc_now(), utc_now()))
    
    return {"status": "queued", "project_id": project_id}

@app.post("/api/projects")
def create_new_project(req: ProjectRequest) -> dict[str, Any]:
    from app.core.project_manager import create_project
    project_id = create_project(req.title, req.brief, "general", req.attachments)
    return {"status": "queued", "project_id": project_id}

@app.get("/api/projects")
def list_projects() -> dict[str, Any]:
    with connect() as con:
        rows = con.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
        projects = []
        for r in rows:
            p = dict(r)
            logs = con.execute("SELECT * FROM project_logs WHERE project_id=? ORDER BY created_at ASC", (p["id"],)).fetchall()
            p["logs"] = [dict(l) for l in logs]
            projects.append(p)
    return {"projects": projects}

@app.get("/api/projects/{project_id}/logs")
def get_project_logs(project_id: str) -> dict[str, Any]:
    with connect() as con:
        rows = con.execute("SELECT * FROM project_logs WHERE project_id=? ORDER BY created_at ASC", (project_id,)).fetchall()
    return {"logs": [dict(r) for r in rows]}


@app.put("/api/projects/{project_id}/approve")
def approve_project(project_id: str) -> dict[str, Any]:
    from app.core.project_manager import update_project_status, log_project_activity
    update_project_status(project_id, "building")
    log_project_activity(project_id, "Julian", "Project approved! Starting the build phase.")
    return {"status": "building"}

@app.put("/api/projects/{project_id}")
def update_project(project_id: str, req: dict) -> dict[str, Any]:
    from app.core.project_manager import update_project_status
    if "title" in req:
        with connect() as con:
            con.execute("UPDATE projects SET title=? WHERE id=?", (req["title"], project_id))
    if "status" in req:
        update_project_status(project_id, req["status"])
    return {"status": "ok"}

@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str) -> dict[str, Any]:
    with connect() as con:
        con.execute("DELETE FROM projects WHERE id=?", (project_id,))
        con.execute("DELETE FROM project_logs WHERE project_id=?", (project_id,))
    return {"status": "deleted"}


@app.put("/api/projects/{project_id}/revise")
def revise_project(project_id: str, req: dict) -> dict[str, Any]:
    from app.core.project_manager import update_project_status, log_project_activity
    feedback = req.get("feedback", "")
    attachments = req.get("attachments", "")
    update_project_status(project_id, "queued")
    log_project_activity(project_id, "User", f"Revision requested: {feedback}")
    with connect() as con:
        con.execute("UPDATE projects SET brief = brief || '\nRevision feedback: ' || ?, attachments = attachments || '\n' || ?, plan_json = NULL WHERE id=?", (feedback, attachments, project_id))
    return {"status": "queued"}


@app.get("/api/projects/{project_id}/download")
def download_project(project_id: str):
    import os
    from fastapi.responses import FileResponse
    zip_path = os.path.expanduser(f"~/Downloads/TheBrain_Julian_Handover_Package/source/workspace/projects/{project_id}.zip")
    if not os.path.exists(zip_path):
        raise HTTPException(404, "Project zip not found.")
    return FileResponse(zip_path, media_type="application/zip", filename=f"project_{project_id}.zip")


@app.get("/api/office/history")
def office_history() -> dict[str, Any]:
    from app.core.database import connect
    with connect() as con:
        rows = con.execute("""
            SELECT l.project_id, l.agent_name, l.message, l.created_at, p.title as project_title
            FROM project_logs l
            LEFT JOIN projects p ON l.project_id = p.id
            ORDER BY l.created_at DESC LIMIT 100
        """).fetchall()
    return {"history": [dict(r) for r in rows]}

@app.get("/api/office/stream")
async def office_stream(trace_id: str = "*") -> StreamingResponse:
    from app.core.event_bus import subscribe
    async def event_generator():
        yield f"data: {json.dumps({'stage': 'system', 'status': 'connected', 'message': 'Live stream connected.'})}\n\n"
        try:
            async for event in subscribe(trace_id):
                payload = {
                    "stage": event.stage,
                    "status": event.status,
                    "message": event.message,
                    "timestamp": event.timestamp,
                    "details": event.details
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            pass
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


class SettingsUpdate(BaseModel):
    persona_prompt: str | None = None
    temperature: float | None = None
    router_keywords: str | None = None
    user_name: str | None = None
    agent_name: str | None = None
    executor_prompt: str | None = None
    planner_prompt: str | None = None
    julian_reply_prompt: str | None = None
    reviewer_prompt: str | None = None
    qc_prompt: str | None = None

class SettingsUpdate(BaseModel):
    persona_prompt: str | None = None
    temperature: float | None = None
    router_keywords: str | None = None
    user_name: str | None = None
    agent_name: str | None = None
    planner_prompt: str | None = None
    julian_reply_prompt: str | None = None

@app.get("/api/settings")
def get_settings() -> dict[str, Any]:
    from app.core.database import connect
    with connect() as con:
        rows = con.execute("SELECT key, value_json FROM settings").fetchall()
        db = {r["key"]: r["value_json"] for r in rows}
        
    return {
        "persona_prompt": db.get("persona_prompt", "You are Julian, a highly capable AI software architect."),
        "temperature": float(db.get("temperature", 0.4)),
        "router_keywords": db.get("router_keywords", "{}"),
        "user_name": db.get("user_name", "Sir"),
        "agent_name": db.get("agent_name", "Julian"),
        "planner_prompt": db.get("planner_prompt", ""),
        "julian_reply_prompt": db.get("julian_reply_prompt", "")
    }

@app.post("/api/settings")
def update_settings(req: SettingsUpdate) -> dict[str, Any]:
    from app.core.database import connect
    from app.core.contracts import utc_now
    with connect() as con:
        if req.persona_prompt is not None:
            con.execute("INSERT OR REPLACE INTO settings(key, value_json, updated_at) VALUES('persona_prompt', ?, ?)", (req.persona_prompt, utc_now()))
        if req.temperature is not None:
            con.execute("INSERT OR REPLACE INTO settings(key, value_json, updated_at) VALUES('temperature', ?, ?)", (str(req.temperature), utc_now()))
        if req.router_keywords is not None:
            con.execute("INSERT OR REPLACE INTO settings(key, value_json, updated_at) VALUES('router_keywords', ?, ?)", (req.router_keywords, utc_now()))
        if req.user_name is not None:
            con.execute("INSERT OR REPLACE INTO settings(key, value_json, updated_at) VALUES('user_name', ?, ?)", (req.user_name, utc_now()))
        if req.agent_name is not None:
            con.execute("INSERT OR REPLACE INTO settings(key, value_json, updated_at) VALUES('agent_name', ?, ?)", (req.agent_name, utc_now()))
        if req.planner_prompt is not None:
            con.execute("INSERT OR REPLACE INTO settings(key, value_json, updated_at) VALUES('planner_prompt', ?, ?)", (req.planner_prompt, utc_now()))
        if req.julian_reply_prompt is not None:
            con.execute("INSERT OR REPLACE INTO settings(key, value_json, updated_at) VALUES('julian_reply_prompt', ?, ?)", (req.julian_reply_prompt, utc_now()))
    return {"status": "ok"}

@app.post("/api/chat")
async def chat(req: ChatRequest) -> dict[str, Any]:
    settings_blob = get_all_settings()
    if not settings_blob.get("modules", {}).get("chat", {}).get("enabled", True):
        raise HTTPException(403, "Chat module is disabled in settings.")
    conversation_id = create_conversation(req.conversation_id, req.message)
    if settings_blob.get("privacy", {}).get("save_chat_history", True):
        save_message(conversation_id, "user", req.message)
    context = RequestContext(conversation_id=conversation_id)
    cancel_event = asyncio.Event()
    context.cancel_event = cancel_event
    task = asyncio.create_task(_execute_chat(req, context))
    task_registry.register(context.trace_id, task, cancel_event)
    try:
        result = await asyncio.wait_for(task, timeout=settings.request_timeout_seconds)
        return result
    except asyncio.TimeoutError:
        cancel_event.set()
        task.cancel()
        audit(context.trace_id, conversation_id, "request", "failed", "Overall request timed out.", {"error_category": "request_timeout"})
        raise HTTPException(504, "Request timed out. Check the audit trace for the failed stage.")
    except asyncio.CancelledError:
        cancel_event.set()
        raise
    finally:
        task_registry.pop(context.trace_id)


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    settings_blob = get_all_settings()
    if not settings_blob.get("modules", {}).get("chat", {}).get("enabled", True):
        raise HTTPException(403, "Chat module is disabled in settings.")
    conversation_id = create_conversation(req.conversation_id, req.message)
    if settings_blob.get("privacy", {}).get("save_chat_history", True):
        save_message(conversation_id, "user", req.message)
    context = RequestContext(conversation_id=conversation_id)
    cancel_event = asyncio.Event()
    context.cancel_event = cancel_event
    context.settings["stream_queue"] = asyncio.Queue()
    task = asyncio.create_task(_execute_chat(req, context))
    task_registry.register(context.trace_id, task, cancel_event)

    async def events() -> AsyncIterator[str]:
        sent_ids: set[int] = set()
        try:
            yield f"event: meta\ndata: {json.dumps({'trace_id': context.trace_id, 'conversation_id': conversation_id})}\n\n"
            while not task.done():
                while not context.settings["stream_queue"].empty():
                    chunk = context.settings["stream_queue"].get_nowait()
                    yield f"event: token\ndata: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
                rows = list_events_for_stream(context.trace_id)
                for payload in rows:
                    if payload["id"] not in sent_ids:
                        sent_ids.add(payload["id"])
                        yield f"event: status\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.25)
            result = await task
            while not context.settings["stream_queue"].empty():
                chunk = context.settings["stream_queue"].get_nowait()
                yield f"event: token\ndata: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
            rows = list_events_for_stream(context.trace_id)
            for payload in rows:
                if payload["id"] not in sent_ids:
                    yield f"event: status\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            yield f"event: result\ndata: {json.dumps(result, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            cancel_event.set()
            task.cancel()
            yield f"event: cancelled\ndata: {json.dumps({'trace_id': context.trace_id, 'status': 'cancelled'})}\n\n"
            raise
        except Exception as exc:
            yield f"event: error\ndata: {json.dumps({'trace_id': context.trace_id, 'error_category': type(exc).__name__, 'message': 'Stream failed; inspect audit log.'})}\n\n"
        finally:
            task_registry.pop(context.trace_id)

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/tasks/{trace_id}/cancel")
async def cancel_task(trace_id: str) -> dict[str, Any]:
    if not task_registry.cancel(trace_id):
        raise HTTPException(404, "No active task found for this trace.")
    return {"trace_id": trace_id, "status": "cancellation_requested"}




@app.get("/api/glossary")
def glossary_get() -> dict[str, Any]:
    return {"terms": list_glossary()}


@app.post("/api/glossary")
def glossary_post(req: GlossaryRequest) -> dict[str, Any]:
    try:
        return {"term": save_glossary(req.term, req.definition, req.language)}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.delete("/api/glossary/{term}")
def glossary_delete(term: str) -> dict[str, Any]:
    if not delete_glossary(term):
        raise HTTPException(404, "Glossary term not found.")
    return {"deleted": True, "term": term}


@app.post("/api/memories")
def memory_post(req: MemoryRequest) -> dict[str, Any]:
    try:
        return {"memory": add_memory(req.kind, req.content, req.source, req.provenance)}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/uploads")
async def upload_file(conversation_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
    settings_blob = get_all_settings()
    if not settings_blob.get("modules", {}).get("file_ingestion", {}).get("enabled", True):
        raise HTTPException(403, "File ingestion module is disabled in settings.")
    conversation_id = create_conversation(conversation_id)
    raw = await file.read(settings.max_upload_bytes + 1)
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(413, f"File exceeds {settings.max_upload_bytes} byte limit.")
    filename = Path(file.filename or "upload.txt").name
    media_type = file.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    sha = hashlib.sha256(raw).hexdigest()
    if media_type.startswith("text/") or filename.lower().endswith((".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml", ".toml", ".csv", ".xml", ".html", ".css", ".sql", ".sh", ".log")):
        extracted = raw.decode("utf-8", errors="replace")
    elif media_type == "application/pdf" or filename.lower().endswith(".pdf"):
        try:
            reader = PdfReader(io.BytesIO(raw), strict=True)
            if reader.is_encrypted:
                raise HTTPException(415, "Encrypted PDFs are not supported. Upload an unlocked PDF or text export.")
            if len(reader.pages) > 500:
                raise HTTPException(413, "PDF exceeds the 500-page extraction limit.")
            chunks: list[str] = []
            total_chars = 0
            for page_number, page in enumerate(reader.pages, start=1):
                if total_chars >= 1_000_000:
                    chunks.append("[PDF extraction truncated after 1,000,000 characters.]")
                    break
                page_text = (page.extract_text() or "").strip()
                if page_text:
                    chunk = f"[PDF page {page_number}]\n{page_text}"
                    remaining = 1_000_000 - total_chars
                    chunks.append(chunk[:remaining])
                    total_chars += min(len(chunk), remaining)
            extracted = "\n\n".join(chunks)
            if not extracted.strip():
                raise HTTPException(415, "This PDF contains no extractable text. Scanned PDFs require OCR, which is not enabled.")
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(415, f"PDF could not be parsed ({type(exc).__name__}).") from exc
    else:
        raise HTTPException(415, f"Unsupported file type for text extraction: {media_type}")
    stored_text = extracted[:1000000]
    if len(extracted) > 1000000:
        stored_text += "\n[Extracted text storage truncated after 1,000,000 characters.]"
    if settings_blob.get("privacy", {}).get("save_uploaded_content", True):
        upload_id = str(uuid.uuid4())
        with connect() as con:
            con.execute("INSERT INTO uploads(id,conversation_id,filename,media_type,size_bytes,extracted_text,sha256,created_at) VALUES(?,?,?,?,?,?,?,?)",
                        (upload_id, conversation_id, filename, media_type, len(raw), stored_text, sha, utc_now()))
    else:
        upload_id = "not-persisted"
        _ephemeral_uploads.setdefault(conversation_id, []).append({"filename": filename, "extracted_text": stored_text, "sha256": sha})
    return {"upload_id": upload_id, "conversation_id": conversation_id, "filename": filename, "media_type": media_type, "size_bytes": len(raw), "sha256": sha, "extracted_chars": len(extracted), "content_truncated": len(extracted) > 1000000, "persisted": upload_id != "not-persisted", "extracted_text": stored_text}


@app.get("/api/audit/{trace_id}")
def audit_trace(trace_id: str) -> dict[str, Any]:
    return {"trace_id": trace_id, "events": list_events(trace_id)}


@app.get("/api/evidence/{trace_id}")
def evidence_trace(trace_id: str) -> dict[str, Any]:
    return {"trace_id": trace_id, "evidence": list_evidence(trace_id)}


@app.post("/api/admin/preflight")
def update_preflight() -> dict[str, Any]:
    """Read-only safety preflight; intentionally does not apply updates or assume an external runtime path."""
    result = preflight_database_path()
    result.update({"database_parent_writable": result["nearest_existing_parent_writable"], "backup_created": False, "rollback_tested": False,
                   "note": result["note"] + " No update, migration, backup, or rollback was executed."})
    return result
