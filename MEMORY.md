# Agent Memory Core Memory Policy

This file documents the open-source package memory policy.

- Store durable project facts and user preferences deliberately.
- Store raw logs with `allow_context_injection=False`.
- Use `build_context_with_trace()` when prompt auditing matters.
- Disable or delete records to remove them from recall and context.
