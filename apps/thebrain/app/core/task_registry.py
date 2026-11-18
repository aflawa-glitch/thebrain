from __future__ import annotations

import asyncio
from typing import Dict, Optional

# S-01: Extracted from main.py to allow other modules (like Agent Runtime)
# to interact with active tasks without circular imports.
_active_tasks: Dict[str, asyncio.Task] = {}
_cancel_events: Dict[str, asyncio.Event] = {}

def register(trace_id: str, task: asyncio.Task, cancel_event: asyncio.Event) -> None:
    """Register a running task and its cancellation event."""
    _active_tasks[trace_id] = task
    _cancel_events[trace_id] = cancel_event

def pop(trace_id: str) -> None:
    """Clean up a finished or cancelled task."""
    _active_tasks.pop(trace_id, None)
    _cancel_events.pop(trace_id, None)

def get_task(trace_id: str) -> Optional[asyncio.Task]:
    return _active_tasks.get(trace_id)

def get_cancel_event(trace_id: str) -> Optional[asyncio.Event]:
    return _cancel_events.get(trace_id)

def cancel(trace_id: str) -> bool:
    """Trigger cancellation for a given trace_id. Returns False if not found."""
    event = _cancel_events.get(trace_id)
    task = _active_tasks.get(trace_id)
    if not event or not task:
        return False
    event.set()
    task.cancel()
    return True
