# Optional MCP Integration

`memory_mcp_server.py` is a minimal local stub that exposes tool functions for
host agents. It does not read secrets, run shell commands, or require network
access.

Destructive tools:

- `disable_memory`
- `delete_memory`

Host agents should ask users for confirmation before exposing those tools.

The full MCP package is optional. This stub can be imported and tested without
installing MCP dependencies.
