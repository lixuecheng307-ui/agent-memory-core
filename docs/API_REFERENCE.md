# API Reference

## RagMemorySystem

`RagMemorySystem(store_path, default_project_id="default", store_backend="sqlite")`

Core methods:

- `remember(content, project_id=None, memory_type=None, scope="project", ...)`
- `recall(query, project_id=None, limit=5, context_only=False)`
- `build_context(query, project_id=None, limit=5)`
- `retrieve_with_trace(query, project_id=None, context_only=False)`
- `build_context_with_trace(query, project_id=None)`
- `update(memory_id, **changes)`
- `disable(memory_id)`
- `delete(memory_id, hard=False)`
- `get(memory_id)`
- `list_memories(project_id=None)`
- `get_memory_history(memory_id)`
- `list_events(memory_id=None)`
- `add_entity(name, entity_type="generic")`
- `add_relation(source_entity_id, target_entity_id, relation_type="related_to")`
- `search_by_entity(entity_name)`
- `build_entity_context(entity_name)`

## Memory Types

`MemoryType` includes raw session log, rolling summary, state, project,
long-term, preference, temporary, emotion, task, skill, browser experience,
safety, and event.

## Embeddings

`DeterministicEmbeddingProvider` is local and deterministic. Use
`OpenAICompatibleEmbeddingProvider(api_key=..., base_url=..., model=...)` only
when the host application explicitly passes a key.
