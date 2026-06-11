from __future__ import annotations

from pathlib import Path

from memory_core.auditor import MemoryAuditor
from memory_core.embeddings import DeterministicEmbeddingProvider
from memory_core.models import (
    ContextBuildTrace,
    GraphEntity,
    GraphRelation,
    MemoryEvent,
    MemoryRecord,
    MemoryType,
    MemoryVersion,
    RecallResult,
    RetrievalTrace,
    memory_type_from_value,
)
from memory_core.vector_store import LocalVectorStore


class RagMemorySystem:
    """Reusable memory + RAG subsystem.

    The class has no host-application-specific dependency. Callers provide project_id and
    choose whether a memory is project-scoped or global.
    """

    def __init__(
        self,
        store_path: str | Path,
        embedding_provider: DeterministicEmbeddingProvider | None = None,
        auditor: MemoryAuditor | None = None,
        vector_store: LocalVectorStore | None = None,
        default_project_id: str = "default",
        store_backend: str = "sqlite",
        collection_name: str = "memory_core",
    ):
        self.default_project_id = default_project_id
        self.embedding_provider = embedding_provider or DeterministicEmbeddingProvider()
        self.auditor = auditor or MemoryAuditor()
        self.vector_store = vector_store or self._build_store(store_path, store_backend, collection_name)

    def _build_store(self, store_path: str | Path, backend: str, collection_name: str):
        if str(backend or "sqlite").lower() == "chroma":
            from memory_core.chroma_store import ChromaVectorStore

            return ChromaVectorStore(store_path, collection_name=collection_name)
        return LocalVectorStore(store_path)

    def remember(
        self,
        content: str,
        project_id: str | None = None,
        memory_type: MemoryType | str | None = None,
        scope: str = "project",
        source: str = "",
        importance: float = 0.5,
        metadata: dict | None = None,
        bypass_audit: bool = False,
        replace_conflicts: bool = False,
        allow_vector: bool | None = None,
        allow_context_injection: bool | None = None,
    ) -> MemoryRecord | None:
        pid = project_id or self.default_project_id
        decision = self.auditor.audit(content, project_id=pid, memory_type=memory_type, scope=scope, source=source)
        if not decision.should_remember and not bypass_audit:
            return None
        resolved_type = memory_type_from_value(memory_type, decision.memory_type)
        base_metadata = {**(metadata or {}), "audit_reason": decision.reason}
        record = MemoryRecord(
            content=str(content or ""),
            project_id=pid,
            memory_type=resolved_type,
            scope=scope,
            sensitivity=decision.sensitivity,
            tags=decision.tags,
            source=source,
            allow_vector=decision.allow_vector if allow_vector is None else bool(allow_vector),
            allow_context_injection=decision.allow_context_injection
            if allow_context_injection is None
            else bool(allow_context_injection),
            importance=float(importance),
            expires_at=decision.expires_at,
            metadata=base_metadata,
        )
        vector = self.embedding_provider.embed(record.content)
        conflicts = self.find_conflicts(record, vector=vector)
        if conflicts:
            record.metadata["conflicts_with"] = [item.memory_id for item in conflicts]
            if replace_conflicts:
                record.supersedes_memory_id = conflicts[0].memory_id
                for item in conflicts:
                    self.disable(item.memory_id)
                    linked = self.vector_store.update(item.memory_id, superseded_by_memory_id=record.memory_id)
                    if linked is not None:
                        self.vector_store.upsert(linked, self.embedding_provider.embed(linked.content))
                record.metadata["replaces"] = [item.memory_id for item in conflicts]
        saved = self.vector_store.upsert(record, vector)
        self._event(saved.memory_id, "remember", {"memory_type": saved.memory_type.value, "project_id": saved.project_id})
        self._version(saved, "remember")
        return saved

    def recall(
        self,
        query: str,
        project_id: str | None = None,
        memory_types: list[MemoryType | str] | None = None,
        include_global: bool = True,
        limit: int = 5,
        context_only: bool = False,
    ) -> list[RecallResult]:
        vector = self.embedding_provider.embed(query)
        rows = self.vector_store.query(
            vector,
            project_id=project_id or self.default_project_id,
            memory_types=memory_types,
            include_global=include_global,
            limit=limit,
            allow_context_only=context_only,
        )
        return [RecallResult(memory=record, score=score) for record, score in rows]

    def retrieve_with_trace(
        self,
        query: str,
        project_id: str | None = None,
        memory_types: list[MemoryType | str] | None = None,
        include_global: bool = True,
        limit: int = 5,
        context_only: bool = False,
    ) -> tuple[list[RecallResult], RetrievalTrace]:
        pid = project_id or self.default_project_id
        vector = self.embedding_provider.embed(query)
        if not hasattr(self.vector_store, "trace_query"):
            results = self.recall(query, project_id=pid, memory_types=memory_types, include_global=include_global, limit=limit, context_only=context_only)
            trace = RetrievalTrace(query=query, project_id=pid)
            trace.included_memories = []
            return results, trace
        rows, excluded = self.vector_store.trace_query(
            vector,
            project_id=pid,
            memory_types=memory_types,
            include_global=include_global,
            limit=limit,
            context_only=context_only,
        )
        results = [RecallResult(memory=record, score=score) for record, score in rows]
        trace = RetrievalTrace(query=query, project_id=pid, excluded_memories=excluded)
        for record, score in rows:
            item = self.vector_store._trace_item(record, "included", score)
            trace.included_memories.append(item)
            if record.scope == "global":
                trace.selected_global_memories.append(record.memory_id)
            else:
                trace.selected_project_memories.append(record.memory_id)
        return results, trace

    def build_context(
        self,
        query: str,
        project_id: str | None = None,
        memory_types: list[MemoryType | str] | None = None,
        limit: int = 5,
    ) -> str:
        results = self.recall(query, project_id=project_id, memory_types=memory_types, limit=limit, context_only=True)
        if not results:
            return ""
        lines = ["Relevant memory:"]
        for index, result in enumerate(results, 1):
            memory = result.memory
            lines.append(
                f"{index}. [{memory.memory_type.value} score={result.score:.3f} project={memory.project_id}] {memory.content}"
            )
        return "\n".join(lines)

    def build_context_with_trace(
        self,
        query: str,
        project_id: str | None = None,
        memory_types: list[MemoryType | str] | None = None,
        limit: int = 5,
    ) -> ContextBuildTrace:
        results, trace = self.retrieve_with_trace(
            query,
            project_id=project_id,
            memory_types=memory_types,
            limit=limit,
            context_only=True,
        )
        if not results:
            return ContextBuildTrace(context="", retrieval_trace=trace)
        lines = ["Relevant memory:"]
        for index, result in enumerate(results, 1):
            memory = result.memory
            lines.append(
                f"{index}. [{memory.memory_type.value} score={result.score:.3f} project={memory.project_id}] {memory.content}"
            )
        return ContextBuildTrace(context="\n".join(lines), retrieval_trace=trace)

    def disable(self, memory_id: str) -> bool:
        ok = self.vector_store.disable(memory_id)
        if ok:
            self._event(memory_id, "disable", {})
        return ok

    def delete(self, memory_id: str, hard: bool = False) -> bool:
        ok = self.vector_store.delete(memory_id, hard=hard)
        if ok:
            self._event(memory_id, "delete_hard" if hard else "delete", {})
        return ok

    def update(self, memory_id: str, **changes) -> MemoryRecord | None:
        before = self.vector_store.get(memory_id)
        record = self.vector_store.update(memory_id, **changes)
        if record is None:
            return None
        vector = self.embedding_provider.embed(record.content)
        saved = self.vector_store.upsert(record, vector)
        if before is not None:
            self._version(before, "before_update")
        self._event(memory_id, "update", {"changed_fields": sorted(changes.keys())})
        self._version(saved, "after_update")
        return saved

    def find_conflicts(self, record: MemoryRecord, vector: list[float] | None = None, limit: int = 8) -> list[MemoryRecord]:
        query_vector = vector or self.embedding_provider.embed(record.content)
        candidates = self.vector_store.query(
            query_vector,
            project_id=record.project_id,
            memory_types=[record.memory_type],
            include_global=record.scope == "global",
            limit=limit,
            allow_context_only=False,
        )
        conflicts: list[MemoryRecord] = []
        for candidate, score in candidates:
            if candidate.memory_id == record.memory_id or score < 0.15:
                continue
            if self._records_conflict(record, candidate):
                conflicts.append(candidate)
        return conflicts

    def _records_conflict(self, new_record: MemoryRecord, old_record: MemoryRecord) -> bool:
        if new_record.memory_type != old_record.memory_type:
            return False
        if new_record.project_id != old_record.project_id and old_record.scope != "global":
            return False
        new_text = new_record.content.lower()
        old_text = old_record.content.lower()
        positive = ("喜欢", "偏好", "prefer", "love", "want")
        negative = ("讨厌", "不喜欢", "不要", "避免", "hate", "avoid")
        new_positive = any(item in new_text for item in positive)
        old_positive = any(item in old_text for item in positive)
        new_negative = any(item in new_text for item in negative)
        old_negative = any(item in old_text for item in negative)
        if (new_positive and old_negative) or (new_negative and old_positive):
            return bool(set(new_record.tags) & set(old_record.tags)) or new_record.memory_type is MemoryType.PREFERENCE
        contrast_pairs = (
            ("极简", "复杂"),
            ("简洁", "复杂"),
            ("克制", "花哨"),
            ("自动打包", "不能打包"),
            ("可以打包", "不能打包"),
        )
        for left, right in contrast_pairs:
            if (left in new_text and right in old_text) or (right in new_text and left in old_text):
                return True
        return False

    def get(self, memory_id: str) -> MemoryRecord | None:
        return self.vector_store.get(memory_id)

    def list_memories(self, project_id: str | None = None, include_global: bool = True, limit: int = 100) -> list[MemoryRecord]:
        return self.vector_store.list_records(project_id=project_id or self.default_project_id, include_global=include_global, limit=limit)

    def get_memory_history(self, memory_id: str) -> list[MemoryVersion]:
        return self.vector_store.get_memory_history(memory_id)

    def list_events(self, memory_id: str | None = None, limit: int = 100) -> list[MemoryEvent]:
        return self.vector_store.list_events(memory_id=memory_id, limit=limit)

    def add_entity(self, name: str, entity_type: str = "generic", project_id: str | None = None, metadata: dict | None = None) -> GraphEntity:
        entity = GraphEntity(name=name, entity_type=entity_type, project_id=project_id or self.default_project_id, metadata=metadata or {})
        return self.vector_store.add_entity(entity)

    def add_relation(
        self,
        source_entity_id: str,
        target_entity_id: str,
        relation_type: str = "related_to",
        project_id: str | None = None,
        source_memory_id: str = "",
        confidence: float = 1.0,
        metadata: dict | None = None,
    ) -> GraphRelation:
        relation = GraphRelation(
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            relation_type=relation_type,
            project_id=project_id or self.default_project_id,
            source_memory_id=source_memory_id,
            confidence=confidence,
            metadata=metadata or {},
        )
        return self.vector_store.add_relation(relation)

    def list_entities(self, project_id: str | None = None) -> list[GraphEntity]:
        return self.vector_store.list_entities(project_id or self.default_project_id)

    def search_by_entity(self, entity_name: str, project_id: str | None = None) -> list[GraphRelation]:
        pid = project_id or self.default_project_id
        entities = [entity for entity in self.list_entities(pid) if entity.name == entity_name]
        entity_ids = {entity.entity_id for entity in entities}
        return [
            relation
            for relation in self.vector_store.list_relations(pid)
            if relation.source_entity_id in entity_ids or relation.target_entity_id in entity_ids
        ]

    def build_entity_context(self, entity_name: str, project_id: str | None = None) -> str:
        relations = self.search_by_entity(entity_name, project_id=project_id)
        if not relations:
            return ""
        entities = {entity.entity_id: entity for entity in self.list_entities(project_id or self.default_project_id)}
        lines = [f"Entity context for {entity_name}:"]
        for relation in relations:
            source = entities.get(relation.source_entity_id)
            target = entities.get(relation.target_entity_id)
            lines.append(
                f"- {source.name if source else relation.source_entity_id} {relation.relation_type} "
                f"{target.name if target else relation.target_entity_id} confidence={relation.confidence:.2f}"
            )
        return "\n".join(lines)

    def _event(self, memory_id: str, event_type: str, details: dict) -> None:
        if hasattr(self.vector_store, "add_event"):
            self.vector_store.add_event(MemoryEvent(memory_id=memory_id, event_type=event_type, details=details))

    def _version(self, record: MemoryRecord, reason: str) -> None:
        if hasattr(self.vector_store, "add_version"):
            self.vector_store.add_version(
                MemoryVersion(memory_id=record.memory_id, content=record.content, metadata=record.metadata, reason=reason)
            )
