import tempfile
from pathlib import Path

from integrations.mcp.memory_mcp_server import create_server


def test_minimal_mcp_stub_tools_work_without_optional_dependency():
    with tempfile.TemporaryDirectory() as tmp:
        server = create_server(Path(tmp) / "mcp.sqlite3", project_id="agent")
        created = server.remember("MCP stub stores local memory.", memory_type="project")

        assert created["memory_id"]
        assert server.search_memory("local memory")
        assert "MCP stub" in server.build_context("local memory")["context"]
        assert server.update_memory(created["memory_id"], "MCP stub updates memory.")["updated"]
        assert server.disable_memory(created["memory_id"])["disabled"]
        assert not server.search_memory("updates memory")
