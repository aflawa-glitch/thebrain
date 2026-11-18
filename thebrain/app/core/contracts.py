from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunStatus(str, Enum):
    ACCEPTED = "accepted"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class StageEvent:
    stage: str
    status: str
    message: str
    timestamp: str = field(default_factory=utc_now)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceItem:
    evidence_id: str
    url: str
    title: str
    retrieved_at: str
    open_status: str
    content_status: str
    snippet: str = ""
    content: str = ""
    published_at: str | None = None
    source_domain: str = ""
    error: str | None = None


@dataclass
class CapabilityResult:
    capability: str
    status: str
    content: str
    data: dict[str, Any] = field(default_factory=dict)
    evidence: list[EvidenceItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class RequestContext:
    conversation_id: str
    user_id: str = "local-user"
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    request_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=utc_now)
    cancel_event: Any = None
    settings: dict[str, Any] = field(default_factory=dict)


@dataclass
class CapabilitySpec:
    name: str
    description: str
    input_schema: dict[str, str]
    output_schema: dict[str, str]
    permissions: tuple[str, ...] = ()
    side_effects: tuple[str, ...] = ()
    timeout_seconds: float = 60.0
    supports_cancellation: bool = True
    verification: str = "result_schema"
    handler: Callable[..., Awaitable[CapabilityResult]] | None = None

    def public_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "permissions": list(self.permissions),
            "side_effects": list(self.side_effects),
            "timeout_seconds": self.timeout_seconds,
            "supports_cancellation": self.supports_cancellation,
            "verification": self.verification,
        }
