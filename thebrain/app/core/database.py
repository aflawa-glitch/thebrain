from __future__ import annotations
import sqlite3
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Any
from app.core.config import settings
from app.core.contracts import utc_now

def discover_database_path() -> Path:
    return settings.resolved_database_path

def preflight_database_path() -> dict[str, Any]:
    """Read-only path check."""
    path = discover_database_path()
    ancestor = path.parent
    while not ancestor.exists() and ancestor != ancestor.parent:
        ancestor = ancestor.parent
    ancestor_is_dir = ancestor.is_dir()
    mode_writable = bool(ancestor.stat().st_mode & 0o222) if ancestor.exists() else False
    can_create_parent = ancestor_is_dir and mode_writable
    parent_exists = path.parent.exists()
    return {
        "status": "ready_for_review" if can_create_parent else "blocked",
        "database_path": str(path),
        "database_exists": path.exists(),
        "database_parent_exists": parent_exists,
        "nearest_existing_parent": str(ancestor),
        "nearest_existing_parent_writable": can_create_parent,
        "note": "Read-only path check. No directory, database, migration, or backup was created.",
    }

def initialize() -> dict[str, Any]:
    path = discover_database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    
    # 1. SAFETY CHECK
    cursor = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
    if cursor.fetchone():
        cursor = con.execute("PRAGMA table_info(settings)")
        columns = [row[1] for row in cursor.fetchall()]
        if "key" not in columns or "value_json" not in columns:
            con.close()
            raise RuntimeError("schema_incompatible: existing settings table does not match expected schema. Database was not modified to avoid corruption.")

    con.execute("PRAGMA journal_mode=WAL")
    
    # 2. CREATE TABLES (Pure SQL, no Python inside)
    con.executescript("""
        CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY, title TEXT, created_at TEXT, updated_at TEXT, is_pinned INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY, conversation_id TEXT, role TEXT, content TEXT, created_at TEXT, metadata_json TEXT);
        CREATE TABLE IF NOT EXISTS uploads(id TEXT PRIMARY KEY, conversation_id TEXT, filename TEXT, media_type TEXT, size_bytes INTEGER, extracted_text TEXT, sha256 TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS audit_events(id INTEGER PRIMARY KEY AUTOINCREMENT, trace_id TEXT, conversation_id TEXT, stage TEXT, status TEXT, message TEXT, details_json TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS evidence(id TEXT PRIMARY KEY, trace_id TEXT, url TEXT, title TEXT, retrieved_at TEXT, open_status TEXT, content_status TEXT, source_domain TEXT, published_at TEXT, snippet TEXT, error TEXT, content TEXT, metadata_json TEXT);
        CREATE TABLE IF NOT EXISTS memories(id TEXT PRIMARY KEY, kind TEXT, content TEXT, source TEXT, provenance_json TEXT, created_at TEXT, supersedes_id TEXT);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value_json TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS glossary(term TEXT PRIMARY KEY, definition TEXT, language TEXT, created_at TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS projects(
            id TEXT PRIMARY KEY,
            title TEXT,
            project_type TEXT,
            brief TEXT,
            attachments TEXT,
            status TEXT DEFAULT 'queued',
            plan_json TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS project_logs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT,
            agent_name TEXT,
            message TEXT,
            created_at TEXT
        );
    """)

    # 3. SAFE MIGRATIONS (Python logic executes AFTER tables are created)
    try:
        con.execute("ALTER TABLE projects ADD COLUMN attachments TEXT")
    except Exception:
        pass # Column already exists

    con.commit()
    con.close()
    return {"status": "initialized", "database_path": str(path)}


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    path = discover_database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=10.0)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()  # Guarantees data is saved
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

def audit(trace_id: str, conversation_id: str | None, stage: str, status: str, message: str, details: dict | None = None) -> None:
    with connect() as con:
        con.execute("INSERT INTO audit_events(trace_id, conversation_id, stage, status, message, details_json, created_at) VALUES(?,?,?,?,?,?,?)",
                    (trace_id, conversation_id, stage, status, message, json.dumps(details or {}), utc_now()))

def get_setting(key: str, default: Any = None) -> Any:
    with connect() as con:
        row = con.execute("SELECT value_json FROM settings WHERE key=?", (key,)).fetchone()
    if row:
        try:
            return json.loads(row["value_json"])
        except (json.JSONDecodeError, TypeError):
            return row["value_json"]
    return default

def put_setting(key: str, value: Any) -> None:
    # FIX: Handle dictionaries by converting them to JSON strings
    if isinstance(value, (dict, list)):
        val_str = json.dumps(value)
    else:
        val_str = str(value)
        
    with connect() as con:
        con.execute("INSERT INTO settings(key,value_json,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at",
                    (key, val_str, utc_now()))
