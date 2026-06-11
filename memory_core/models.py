from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class MemoryType(Enum):
    RAW_SESSION_LOG = "raw_session_log"
    ROLLING_SUMMARY = "rolling_summary"
    STATE = "state"
    PROJECT = "project"
    LONG_TERM = "long_term"
    PREFERENCE = "preference"
    TEMPORARY = "temporary"
    EMOTION = "emotion"
    TASK = "task"
    SKILL = "skill"
    BROWSER_EXPERIENCE = "browser_experience"
    SAFETY = "safety"
    EVENT = "event"


class MemoryStatus(Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    DELETED = "deleted"


@dataclass
class AuditDecision:
    should_remember: bool
    memory_type: MemoryType
    sensitivity: str = "normal"
    allow_vector: bool = True
    allow_context_injection: bool = True
    requires_user_confirmation: bool = False
    expires_at: datetime | None = None
    reason: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class MemoryRecord:
    content: str
    project_id: str = "default"
    memory_type: MemoryType = MemoryType.LONG_TERM
    memory_id: str = field(default_factory=lambda: f"mem_{uuid4().hex}")
    scope: str = "project"
    status: MemoryStatus = MemoryStatus.ACTIVE
    sensitivity: str = "normal"
    tags: list[str] = field(default_factory=list)
    source: str = ""
    allow_vector: bool = True
    allow_context_injection: bool = True
    importance: float = 0.5
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    supersedes_memory_id: str = ""
    superseded_by_memory_id: str = ""
    vector_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_active(self, now: datetime | None = None) -> bool:
        if self.status is not MemoryStatus.ACTIVE:
            return False
        current = now or datetime.now()
        if self.expires_at is not None and self.expires_at <= current:
            return False
        if self.valid_from is not None and self.valid_from > current:
            return False
        if self.valid_until is not None and self.valid_until <= current:
            return False
        return True


@dataclass
class RecallResult:
    memory: MemoryRecord
    score: float
    reason: str = "vector_similarity"


@dataclass
class MemoryEvent:
    event_id: str = field(default_factory=lambda: f"evt_{uuid4().hex}")
    memory_id: str = ""
    event_type: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryVersion:
    version_id: str = field(default_factory=lambda: f"ver_{uuid4().hex}")
    memory_id: str = ""
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    reason: str = ""


@dataclass
class GraphEntity:
    entity_id: str = field(default_factory=lambda: f"ent_{uuid4().hex}")
    name: str = ""
    entity_type: str = "generic"
    project_id: str = "default"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class GraphRelation:
    relation_id: str = field(default_factory=lambda: f"rel_{uuid4().hex}")
    source_entity_id: str = ""
    target_entity_id: str = ""
    relation_type: str = "related_to"
    project_id: str = "default"
    source_memory_id: str = ""
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class TraceItem:
    memory_id: str
    reason: str
    content: str = ""
    score: float = 0.0
    project_id: str = ""
    memory_type: str = ""


@dataclass
class RetrievalTrace:
    query: str
    project_id: str
    included_memories: list[TraceItem] = field(default_factory=list)
    excluded_memories: list[TraceItem] = field(default_factory=list)
    selected_global_memories: list[str] = field(default_factory=list)
    selected_project_memories: list[str] = field(default_factory=list)


@dataclass
class ContextBuildTrace:
    context: str
    retrieval_trace: RetrievalTrace


def memory_type_from_value(value: str | MemoryType | None, default: MemoryType = MemoryType.LONG_TERM) -> MemoryType:
    if isinstance(value, MemoryType):
        return value
    text = str(value or "").strip().lower()
    if not text:
        return default
    for item in MemoryType:
        if item.value == text or item.name.lower() == text:
            return item
    return default


def memory_status_from_value(value: str | MemoryStatus | None, default: MemoryStatus = MemoryStatus.ACTIVE) -> MemoryStatus:
    if isinstance(value, MemoryStatus):
        return value
    text = str(value or "").strip().lower()
    if not text:
        return default
    for item in MemoryStatus:
        if item.value == text or item.name.lower() == text:
            return item
    return default
