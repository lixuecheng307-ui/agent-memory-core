from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

from memory_core.models import MemoryRecord, MemoryStatus, MemoryType, memory_status_from_value, memory_type_from_value
from memory_core.vector_store import cosine_similarity


class ChromaVectorStore:
    """Optional ChromaDB vector-store backend.

    The import is lazy so `memory_core` remains extractable and testable without
    ChromaDB installed. Deployments that want ChromaDB pass
    `store_backend="chroma"` to `RagMemorySystem`.
    """

    def __init__(self, persist_path: str | Path, collection_name: str = "memory_core"):
        self.persist_path = Path(persist_path)
        self.persist_path.mkdir(parents=True, exist_ok=True)
        try:
            import chromadb
        except Exception as exc:
            raise RuntimeError("ChromaDB backend requested but chromadb is not installed") from exc
        self._client = chromadb.PersistentClient(path=str(self.persist_path))
        self._collection = self._client.get_or_create_collection(name=collection_name)

    def upsert(self, record: MemoryRecord, vector: list[float]) -> MemoryRecord:
        if not record.vector_id:
            record.vector_id = record.memory_id
        record.updated_at = datetime.now()
        self._collection.upsert(
            ids=[record.memory_id],
            embeddings=[[float(item) for item in vector]],
            documents=[record.content],
            metadatas=[self._metadata(record)],
        )
        return record

    def get(self, memory_id: str) -> MemoryRecord | None:
        result = self._collection.get(ids=[memory_id], include=["documents", "metadatas"])
        ids = result.get("ids") or []
        if not ids:
            return None
        return self._record_from_chroma(ids[0], result["documents"][0], result["metadatas"][0])

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
        result = self._collection.get(include=["documents", "metadatas"])
        records = [
            self._record_from_chroma(memory_id, document, metadata)
            for memory_id, document, metadata in zip(result.get("ids") or [], result.get("documents") or [], result.get("metadatas") or [])
        ]
        if project_id:
            records = [
                record
                for record in records
                if record.project_id == project_id or (include_global and record.scope == "global")
            ]
        records.sort(key=lambda record: record.created_at, reverse=True)
        return records[: max(0, int(limit))]

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
        allowed_types = {memory_type_from_value(item).value for item in (memory_types or [])}
        result = self._collection.query(
            query_embeddings=[[float(item) for item in vector]],
            n_results=max(1, int(limit) * 6),
            include=["documents", "metadatas", "embeddings"],
        )
        rows: list[tuple[MemoryRecord, float]] = []
        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        embeddings = (result.get("embeddings") or [[]])[0]
        now = datetime.now()
        for memory_id, document, metadata, embedding in zip(ids, documents, metadatas, embeddings):
            record = self._record_from_chroma(memory_id, document, metadata)
            if record.project_id != project_id and not (include_global and record.scope == "global"):
                continue
            if allowed_types and record.memory_type.value not in allowed_types:
                continue
            if not include_disabled and not record.is_active(now):
                continue
            if allow_context_only and not record.allow_context_injection:
                continue
            if not record.allow_vector:
                continue
            rows.append((record, cosine_similarity(vector, [float(item) for item in embedding])))
        rows.sort(key=lambda item: (item[1], item[0].importance, item[0].created_at), reverse=True)
        return rows[: max(0, int(limit))]

    def disable(self, memory_id: str) -> bool:
        return self._set_status(memory_id, MemoryStatus.DISABLED)

    def delete(self, memory_id: str, hard: bool = False) -> bool:
        if hard:
            existing = self.get(memory_id)
            if existing is None:
                return False
            self._collection.delete(ids=[memory_id])
            return True
        return self._set_status(memory_id, MemoryStatus.DELETED)

    def _set_status(self, memory_id: str, status: MemoryStatus) -> bool:
        record = self.get(memory_id)
        if record is None:
            return False
        record.status = status
        existing = self._collection.get(ids=[memory_id], include=["embeddings"])
        embeddings = existing.get("embeddings") or []
        if not embeddings:
            return False
        self.upsert(record, [float(item) for item in embeddings[0]])
        return True

    def _metadata(self, record: MemoryRecord) -> dict:
        return {
            "vector_id": record.vector_id,
            "project_id": record.project_id,
            "scope": record.scope,
            "memory_type": record.memory_type.value,
            "status": record.status.value,
            "sensitivity": record.sensitivity,
            "tags": json.dumps(record.tags, ensure_ascii=False),
            "source": record.source,
            "allow_vector": int(record.allow_vector),
            "allow_context_injection": int(record.allow_context_injection),
            "importance": float(record.importance),
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
            "expires_at": record.expires_at.isoformat() if record.expires_at else "",
            "metadata_json": json.dumps(record.metadata, ensure_ascii=False, sort_keys=True),
        }

    def _record_from_chroma(self, memory_id: str, document: str, metadata: dict) -> MemoryRecord:
        expires = str(metadata.get("expires_at") or "")
        return MemoryRecord(
            memory_id=memory_id,
            vector_id=str(metadata.get("vector_id") or memory_id),
            project_id=str(metadata.get("project_id") or "default"),
            scope=str(metadata.get("scope") or "project"),
            memory_type=memory_type_from_value(metadata.get("memory_type")),
            status=memory_status_from_value(metadata.get("status")),
            sensitivity=str(metadata.get("sensitivity") or "normal"),
            content=str(document or ""),
            tags=json.loads(str(metadata.get("tags") or "[]")),
            source=str(metadata.get("source") or ""),
            allow_vector=bool(int(metadata.get("allow_vector") or 0)),
            allow_context_injection=bool(int(metadata.get("allow_context_injection") or 0)),
            importance=float(metadata.get("importance") or 0.5),
            created_at=datetime.fromisoformat(str(metadata.get("created_at"))),
            updated_at=datetime.fromisoformat(str(metadata.get("updated_at"))),
            expires_at=datetime.fromisoformat(expires) if expires else None,
            metadata=json.loads(str(metadata.get("metadata_json") or "{}")),
        )
