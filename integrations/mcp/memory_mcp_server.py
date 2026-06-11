from __future__ import annotations

from pathlib import Path

from memory_core import RagMemorySystem


class MemoryMcpServer:
    """Minimal local MCP-like tool wrapper.

    This intentionally avoids importing the optional MCP package so default tests
    remain dependency-free. Hosts can adapt these methods to real MCP tools.
    """

    def __init__(self, db_path: str | Path = ".agent_memory_core/mcp_memory.sqlite3", project_id: str = "default"):
        self.system = RagMemorySystem(Path(db_path), default_project_id=project_id)
        self.project_id = project_id

    def remember(self, content: str, memory_type: str = "long_term", project_id: str | None = None) -> dict:
        record = self.system.remember(content, memory_type=memory_type, project_id=project_id or self.project_id)
        return {"memory_id": record.memory_id if record else None}

    def search_memory(self, query: str, project_id: str | None = None, limit: int = 5) -> list[dict]:
        return [
            {"memory_id": item.memory.memory_id, "content": item.memory.content, "score": item.score}
            for item in self.system.recall(query, project_id=project_id or self.project_id, limit=limit)
        ]

    def build_context(self, query: str, project_id: str | None = None) -> dict:
        traced = self.system.build_context_with_trace(query, project_id=project_id or self.project_id)
        return {
            "context": traced.context,
            "included": [item.__dict__ for item in traced.retrieval_trace.included_memories],
            "excluded": [item.__dict__ for item in traced.retrieval_trace.excluded_memories],
        }

    def list_memories(self, project_id: str | None = None) -> list[dict]:
        return [
            {"memory_id": item.memory_id, "content": item.content, "status": item.status.value}
            for item in self.system.list_memories(project_id=project_id or self.project_id)
        ]

    def update_memory(self, memory_id: str, content: str) -> dict:
        return {"updated": bool(self.system.update(memory_id, content=content))}

    def disable_memory(self, memory_id: str) -> dict:
        return {"disabled": self.system.disable(memory_id)}

    def delete_memory(self, memory_id: str) -> dict:
        return {"deleted": self.system.delete(memory_id)}

    def run_benchmark(self) -> dict:
        from benchmarks.run_memory_benchmark import run_benchmark

        return run_benchmark(
            Path("benchmarks/memory_recall_cases.json"),
            Path("benchmark_results.json"),
            Path("benchmark_report.md"),
        )


def create_server(db_path: str | Path = ".agent_memory_core/mcp_memory.sqlite3", project_id: str = "default") -> MemoryMcpServer:
    return MemoryMcpServer(db_path=db_path, project_id=project_id)
