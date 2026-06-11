# Agent Integration

## Generic Python Agent

1. Create one `RagMemorySystem` per application or workspace.
2. Store durable facts with `remember()`.
3. Store raw logs with `allow_context_injection=False`.
4. Before model calls, run `build_context_with_trace()`.
5. Add the context as a separate system message.
6. Persist trace metadata with the agent run if auditing matters.

## Codex

Use Agent Memory Core as a project-local memory package. Keep repository-specific
rules outside `memory_core/` and pass project IDs explicitly.

## Claude Code

Use the same pattern: project adapter outside the package, explicit context
injection before tool/model calls, and no implicit secret loading.

## MCP

See `integrations/mcp/README.md` for the optional MCP server stub.

## Planned Adapters

- LangGraph adapter: planned
- LlamaIndex adapter: planned
- Dify / Coze / FastGPT document-level integration: planned
