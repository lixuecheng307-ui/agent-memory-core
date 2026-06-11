# Security and Privacy

Agent Memory Core is local-first by default.

- SQLite is the default backend.
- No API key is read from environment variables.
- No API key is read from local config files.
- OpenAI-compatible embeddings require explicit host-provided keys.
- Sensitive content is rejected by the audit gate.
- Disabled and deleted memories are excluded from recall and context.
- Raw session logs should not be injected into prompts unless promoted.

Destructive operations such as disable and delete should be confirmed by the
host agent when exposed to end users.
