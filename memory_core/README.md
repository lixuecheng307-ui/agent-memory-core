# memory_core

Reusable local memory and RAG subsystem.

It is intentionally independent from host application modules. Another project
can copy this directory and instantiate `RagMemorySystem` with its own
`project_id`.

Current guarantees:

- project-scoped and global memories
- 13 memory types for human-like memory organization
- audit gate for sensitive content, short-lived emotion, and inferred type
- local numeric embeddings with cosine vector retrieval
- SQLite vector store for portable offline use
- optional ChromaDB vector store through `store_backend="chroma"`
- OpenAI-compatible embedding provider for real embedding APIs
- conflict marking and optional replacement for contradictory memories
- update flow that regenerates vectors after edits
- deletion and disable filters that remove records from recall
- context building for dialogue injection

Host integration:

- copy `memory_core/` into another project and instantiate `RagMemorySystem`
- provide a project-specific `project_id` for isolation
- call `remember()` for durable facts/preferences/tasks
- call `build_context()` before model calls to inject only audited memories
- use `allow_context_injection=False` for raw logs that should be searchable later
  only after explicit promotion

Production systems can replace `DeterministicEmbeddingProvider` with a model or
API-backed embedding provider and keep the same `RagMemorySystem` interface.

The included `OpenAICompatibleEmbeddingProvider` expects the host application to
pass an API key explicitly. It does not read environment variables or local
config files on its own.
