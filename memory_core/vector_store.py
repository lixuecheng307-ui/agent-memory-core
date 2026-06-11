from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable

from memory_core.models import (
    GraphEntity,
    GraphRelation,
    MemoryEvent,
    MemoryRecord,
    MemoryStatus,
    MemoryType,
    MemoryVersion,
    TraceItem,
    memory_status_from_value,
    memory_type_from_value,
)


class LocalVectorStore:
    """Portable SQLite vector store with events, versions, trace, and graph tables."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def upsert(self, record: MemoryRecord, vector: list[float]) -> MemoryRecord:
        if not record.vector_id:
            record.vector_id = record.memory_id
        record.updated_at = datetime.now()
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO memories (
                    memory_id, vector_id, project_id, scope, memory_type, status,
                    sensitivity, content, tags, source, allow_vector,
                    allow_context_injection, importance, created_at, updated_at,
                    expires_at, valid_from, valid_until, supersedes_memory_id,
                    superseded_by_memory_id, metadata, vector
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._to_row(record, vector),
            )
            conn.commit()
        finally:
            conn.close()
        return record

    def get(self, memory_id: str) -> MemoryRecord | None:
        rows = self._fetch("SELECT * FROM memories WHERE memory_id = ?", (memory_id,))
        return self._from_row(rows[0]) if rows else None

    def update(self, memory_id: str, **changes) -> MemoryRecord | None:
        record = self.get(memory_id)
        if record is None:
            return None
        for key in (
            "content",
            "project_id",
            "scope",
            "sensitivity",
            "tags",
            "source",
            "allow_vector",
            "allow_context_injection",
            "importance",
            "expires_at",
            "valid_from",
            "valid_until",
            "supersedes_memory_id",
            "superseded_by_memory_id",
            "metadata",
        ):
            if key in changes:
                setattr(record, key, changes[key])
        if "memory_type" in changes:
            record.memory_type = memory_type_from_value(changes["memory_type"], record.memory_type)
        if "status" in changes:
            record.status = memory_status_from_value(changes["status"], record.status)
        return record

    def list_records(self, project_id: str | None = None, include_global: bool = True, limit: int = 100) -> list[MemoryRecord]:
        sql = "SELECT * FROM memories"
        params: list[object] = []
        if project_id:
            if include_global:
                sql += " WHERE (project_id = ? OR scope = 'global')"
                params.append(project_id)
            else:
                sql += " WHERE project_id = ?"
                params.append(project_id)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(0, int(limit)))
        return [self._from_row(row) for row in self._fetch(sql, tuple(params))]

    def query(
        self,
        vector: list[float],
        project_id: str = "default",
        memory_types: Iterable[MemoryType | str] | None = None,
        include_global: bool = True,
        limit: int = 5,
        include_disabled: bool = False,
        allow_context_only: bool = False,
    ) -> list[tuple[MemoryRecord, float]]:
        included, _excluded = self.trace_query(
            vector,
            project_id=project_id,
            memory_types=memory_types,
            include_global=include_global,
            limit=limit,
            context_only=allow_context_only,
            include_disabled=include_disabled,
        )
        return included

    def trace_query(
        self,
        vector: list[float],
        project_id: str = "default",
        memory_types: Iterable[MemoryType | str] | None = None,
        include_global: bool = True,
        limit: int = 5,
        context_only: bool = False,
        include_disabled: bool = False,
    ) -> tuple[list[tuple[MemoryRecord, float]], list[TraceItem]]:
        allowed_types = {memory_type_from_value(item).value for item in (memory_types or [])}
        rows = self._fetch("SELECT * FROM memories", ())
        now = datetime.now()
        included: list[tuple[MemoryRecord, float]] = []
        excluded: list[TraceItem] = []
        for row in rows:
            record = self._from_row(row)
            score = cosine_similarity(vector, json.loads(row["vector"] or "[]"))
            reason = self._exclusion_reason(
                record,
                score=score,
                now=now,
                project_id=project_id,
                include_global=include_global,
                allowed_types=allowed_types,
                context_only=context_only,
                include_disabled=include_disabled,
            )
            if reason:
                excluded.append(self._trace_item(record, reason, score))
            else:
                included.append((record, score))
        included.sort(key=lambda item: (item[1], item[0].importance, item[0].created_at), reverse=True)
        return included[: max(0, int(limit))], excluded

    def disable(self, memory_id: str) -> bool:
        return self._set_status(memory_id, MemoryStatus.DISABLED)

    def delete(self, memory_id: str, hard: bool = False) -> bool:
        if hard:
            conn = self._connect()
            try:
                cur = conn.execute("DELETE FROM memories WHERE memory_id = ?", (memory_id,))
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()
        return self._set_status(memory_id, MemoryStatus.DELETED)

    def add_event(self, event: MemoryEvent) -> MemoryEvent:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO memory_events (event_id, memory_id, event_type, created_at, details) VALUES (?, ?, ?, ?, ?)",
                (
                    event.event_id,
                    event.memory_id,
                    event.event_type,
                    event.created_at.isoformat(),
                    json.dumps(event.details, ensure_ascii=False, sort_keys=True),
                ),
            )
            conn.commit()
            return event
        finally:
            conn.close()

    def list_events(self, memory_id: str | None = None, limit: int = 100) -> list[MemoryEvent]:
        sql = "SELECT * FROM memory_events"
        params: list[object] = []
        if memory_id:
            sql += " WHERE memory_id = ?"
            params.append(memory_id)
        sql += " ORDER BY created_at ASC LIMIT ?"
        params.append(max(0, int(limit)))
        return [self._event_from_row(row) for row in self._fetch(sql, tuple(params))]

    def add_version(self, version: MemoryVersion) -> MemoryVersion:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO memory_versions (version_id, memory_id, content, metadata, created_at, reason) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    version.version_id,
                    version.memory_id,
                    version.content,
                    json.dumps(version.metadata, ensure_ascii=False, sort_keys=True),
                    version.created_at.isoformat(),
                    version.reason,
                ),
            )
            conn.commit()
            return version
        finally:
            conn.close()

    def get_memory_history(self, memory_id: str) -> list[MemoryVersion]:
        rows = self._fetch("SELECT * FROM memory_versions WHERE memory_id = ? ORDER BY created_at ASC", (memory_id,))
        return [self._version_from_row(row) for row in rows]

    def add_entity(self, entity: GraphEntity) -> GraphEntity:
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO graph_entities (entity_id, name, entity_type, project_id, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    entity.entity_id,
                    entity.name,
                    entity.entity_type,
                    entity.project_id,
                    json.dumps(entity.metadata, ensure_ascii=False, sort_keys=True),
                    entity.created_at.isoformat(),
                ),
            )
            conn.commit()
            return entity
        finally:
            conn.close()

    def add_relation(self, relation: GraphRelation) -> GraphRelation:
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO graph_relations (
                    relation_id, source_entity_id, target_entity_id, relation_type,
                    project_id, source_memory_id, confidence, metadata, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    relation.relation_id,
                    relation.source_entity_id,
                    relation.target_entity_id,
                    relation.relation_type,
                    relation.project_id,
                    relation.source_memory_id,
                    float(relation.confidence),
                    json.dumps(relation.metadata, ensure_ascii=False, sort_keys=True),
                    relation.created_at.isoformat(),
                ),
            )
            conn.commit()
            return relation
        finally:
            conn.close()

    def list_entities(self, project_id: str = "default") -> list[GraphEntity]:
        rows = self._fetch("SELECT * FROM graph_entities WHERE project_id = ? ORDER BY created_at ASC", (project_id,))
        return [self._entity_from_row(row) for row in rows]

    def list_relations(self, project_id: str = "default") -> list[GraphRelation]:
        rows = self._fetch("SELECT * FROM graph_relations WHERE project_id = ? ORDER BY created_at ASC", (project_id,))
        return [self._relation_from_row(row) for row in rows]

    def _set_status(self, memory_id: str, status: MemoryStatus) -> bool:
        conn = self._connect()
        try:
            cur = conn.execute(
                "UPDATE memories SET status = ?, updated_at = ? WHERE memory_id = ?",
                (status.value, datetime.now().isoformat(), memory_id),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def _init_db(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    memory_id TEXT PRIMARY KEY,
                    vector_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    sensitivity TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    source TEXT NOT NULL,
                    allow_vector INTEGER NOT NULL,
                    allow_context_injection INTEGER NOT NULL,
                    importance REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT,
                    valid_from TEXT,
                    valid_until TEXT,
                    supersedes_memory_id TEXT NOT NULL DEFAULT '',
                    superseded_by_memory_id TEXT NOT NULL DEFAULT '',
                    metadata TEXT NOT NULL,
                    vector TEXT NOT NULL
                )
                """
            )
            self._ensure_columns(conn)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_events (
                    event_id TEXT PRIMARY KEY,
                    memory_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    details TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_versions (
                    version_id TEXT PRIMARY KEY,
                    memory_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    reason TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS graph_entities (
                    entity_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS graph_relations (
                    relation_id TEXT PRIMARY KEY,
                    source_entity_id TEXT NOT NULL,
                    target_entity_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    source_memory_id TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_project ON memories(project_id, status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_type ON memories(memory_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_memory ON memory_events(memory_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_versions_memory ON memory_versions(memory_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_graph_entity_project ON graph_entities(project_id, name)")
            conn.commit()
        finally:
            conn.close()

    def _ensure_columns(self, conn) -> None:
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(memories)").fetchall()}
        additions = {
            "valid_from": "TEXT",
            "valid_until": "TEXT",
            "supersedes_memory_id": "TEXT NOT NULL DEFAULT ''",
            "superseded_by_memory_id": "TEXT NOT NULL DEFAULT ''",
        }
        for name, ddl in additions.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE memories ADD COLUMN {name} {ddl}")

    def _connect(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _fetch(self, sql: str, params: tuple[object, ...]) -> list[sqlite3.Row]:
        conn = self._connect()
        try:
            return list(conn.execute(sql, params).fetchall())
        finally:
            conn.close()

    def _to_row(self, record: MemoryRecord, vector: list[float]):
        return (
            record.memory_id,
            record.vector_id,
            record.project_id,
            record.scope,
            record.memory_type.value,
            record.status.value,
            record.sensitivity,
            record.content,
            json.dumps(record.tags, ensure_ascii=False),
            record.source,
            1 if record.allow_vector else 0,
            1 if record.allow_context_injection else 0,
            float(record.importance),
            record.created_at.isoformat(),
            record.updated_at.isoformat(),
            record.expires_at.isoformat() if record.expires_at else None,
            record.valid_from.isoformat() if record.valid_from else None,
            record.valid_until.isoformat() if record.valid_until else None,
            record.supersedes_memory_id,
            record.superseded_by_memory_id,
            json.dumps(record.metadata, ensure_ascii=False, sort_keys=True),
            json.dumps([float(item) for item in vector]),
        )

    def _from_row(self, row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            memory_id=row["memory_id"],
            vector_id=row["vector_id"],
            project_id=row["project_id"],
            scope=row["scope"],
            memory_type=memory_type_from_value(row["memory_type"]),
            status=memory_status_from_value(row["status"]),
            sensitivity=row["sensitivity"],
            content=row["content"],
            tags=json.loads(row["tags"] or "[]"),
            source=row["source"],
            allow_vector=bool(row["allow_vector"]),
            allow_context_injection=bool(row["allow_context_injection"]),
            importance=float(row["importance"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
            valid_from=datetime.fromisoformat(row["valid_from"]) if "valid_from" in row.keys() and row["valid_from"] else None,
            valid_until=datetime.fromisoformat(row["valid_until"]) if "valid_until" in row.keys() and row["valid_until"] else None,
            supersedes_memory_id=row["supersedes_memory_id"] if "supersedes_memory_id" in row.keys() else "",
            superseded_by_memory_id=row["superseded_by_memory_id"] if "superseded_by_memory_id" in row.keys() else "",
            metadata=json.loads(row["metadata"] or "{}"),
        )

    def _event_from_row(self, row: sqlite3.Row) -> MemoryEvent:
        return MemoryEvent(
            event_id=row["event_id"],
            memory_id=row["memory_id"],
            event_type=row["event_type"],
            created_at=datetime.fromisoformat(row["created_at"]),
            details=json.loads(row["details"] or "{}"),
        )

    def _version_from_row(self, row: sqlite3.Row) -> MemoryVersion:
        return MemoryVersion(
            version_id=row["version_id"],
            memory_id=row["memory_id"],
            content=row["content"],
            metadata=json.loads(row["metadata"] or "{}"),
            created_at=datetime.fromisoformat(row["created_at"]),
            reason=row["reason"],
        )

    def _entity_from_row(self, row: sqlite3.Row) -> GraphEntity:
        return GraphEntity(
            entity_id=row["entity_id"],
            name=row["name"],
            entity_type=row["entity_type"],
            project_id=row["project_id"],
            metadata=json.loads(row["metadata"] or "{}"),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def _relation_from_row(self, row: sqlite3.Row) -> GraphRelation:
        return GraphRelation(
            relation_id=row["relation_id"],
            source_entity_id=row["source_entity_id"],
            target_entity_id=row["target_entity_id"],
            relation_type=row["relation_type"],
            project_id=row["project_id"],
            source_memory_id=row["source_memory_id"],
            confidence=float(row["confidence"]),
            metadata=json.loads(row["metadata"] or "{}"),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def _exclusion_reason(
        self,
        record: MemoryRecord,
        *,
        score: float,
        now: datetime,
        project_id: str,
        include_global: bool,
        allowed_types: set[str],
        context_only: bool,
        include_disabled: bool,
    ) -> str:
        if record.project_id != project_id and not (include_global and record.scope == "global"):
            return "project_mismatch"
        if allowed_types and record.memory_type.value not in allowed_types:
            return "memory_type_mismatch"
        if not include_disabled and record.status is MemoryStatus.DISABLED:
            return "disabled"
        if not include_disabled and record.status is MemoryStatus.DELETED:
            return "deleted"
        if record.expires_at is not None and record.expires_at <= now:
            return "expired"
        if record.valid_from is not None and record.valid_from > now:
            return "not_yet_valid"
        if record.valid_until is not None and record.valid_until <= now:
            return "valid_until_elapsed"
        if context_only and not record.allow_context_injection:
            return "allow_context_injection_false"
        if not record.allow_vector:
            return "allow_vector_false"
        if record.sensitivity == "sensitive":
            return "sensitive"
        if score <= 0:
            return "zero_similarity"
        return ""

    def _trace_item(self, record: MemoryRecord, reason: str, score: float) -> TraceItem:
        return TraceItem(
            memory_id=record.memory_id,
            reason=reason,
            content=record.content,
            score=score,
            project_id=record.project_id,
            memory_type=record.memory_type.value,
        )


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)
