# Agent Memory Core Contributor Instructions

`memory_core/` must remain business-agnostic.

- Do not import host application modules from `memory_core/`.
- Do not read API keys from environment variables or local config files.
- Keep ChromaDB, MCP, and web demo dependencies optional.
- Preserve the SQLite offline path.
- Add tests or runnable demos for new core behavior.
- Disabled and deleted memories must never appear in recall or context.
- Raw logs must not enter prompt context unless explicitly promoted.
