from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from memory_core import MemoryType, RagMemorySystem


DEFAULT_DB = Path(".agent_memory_core") / "memory.sqlite3"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="memory-core", description="Agent Memory Core CLI")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite database path")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("init")

    remember = sub.add_parser("remember")
    remember.add_argument("--project", default="default")
    remember.add_argument("--text", required=True)
    remember.add_argument("--type", default=MemoryType.LONG_TERM.value)
    remember.add_argument("--global-memory", action="store_true")
    remember.add_argument("--no-context", action="store_true")

    search = sub.add_parser("search")
    search.add_argument("--project", default="default")
    search.add_argument("--query", required=True)
    search.add_argument("--limit", type=int, default=5)

    context = sub.add_parser("context")
    context.add_argument("--project", default="default")
    context.add_argument("--query", required=True)
    context.add_argument("--limit", type=int, default=5)
    context.add_argument("--trace", action="store_true")

    list_cmd = sub.add_parser("list")
    list_cmd.add_argument("--project", default="default")
    list_cmd.add_argument("--limit", type=int, default=20)

    update = sub.add_parser("update")
    update.add_argument("--id", required=True)
    update.add_argument("--text", required=True)

    disable = sub.add_parser("disable")
    disable.add_argument("--id", required=True)

    delete = sub.add_parser("delete")
    delete.add_argument("--id", required=True)
    delete.add_argument("--hard", action="store_true")

    benchmark = sub.add_parser("benchmark")
    benchmark.add_argument("--cases", default="benchmarks/memory_recall_cases.json")
    benchmark.add_argument("--out", default="benchmark_results.json")
    benchmark.add_argument("--report", default="benchmark_report.md")

    sub.add_parser("demo-web")
    return parser


def system_from_args(args) -> RagMemorySystem:
    return RagMemorySystem(Path(args.db), default_project_id="default")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.command:
        build_parser().print_help()
        return 0
    if args.command == "benchmark":
        from benchmarks.run_memory_benchmark import run_benchmark

        result = run_benchmark(Path(args.cases), Path(args.out), Path(args.report))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "demo-web":
        try:
            import streamlit  # noqa: F401
        except Exception:
            print("Streamlit is optional. Install with: pip install -e .[web]")
            print("Then run: streamlit run examples/web_demo/app.py")
            return 0
        print("Run: streamlit run examples/web_demo/app.py")
        return 0

    system = system_from_args(args)
    if args.command == "init":
        Path(args.db).parent.mkdir(parents=True, exist_ok=True)
        system.list_memories()
        print(f"initialized {Path(args.db)}")
        return 0
    if args.command == "remember":
        scope = "global" if args.global_memory else "project"
        project_id = "global" if args.global_memory else args.project
        record = system.remember(
            args.text,
            project_id=project_id,
            memory_type=args.type,
            scope=scope,
            allow_context_injection=not args.no_context,
        )
        print(json.dumps({"memory_id": record.memory_id if record else None}, ensure_ascii=False))
        return 0
    if args.command == "search":
        rows = system.recall(args.query, project_id=args.project, limit=args.limit)
        print(json.dumps([_result_to_dict(item) for item in rows], ensure_ascii=False, indent=2))
        return 0
    if args.command == "context":
        if args.trace:
            traced = system.build_context_with_trace(args.query, project_id=args.project, limit=args.limit)
            print(json.dumps(_trace_to_dict(traced), ensure_ascii=False, indent=2))
        else:
            print(system.build_context(args.query, project_id=args.project, limit=args.limit))
        return 0
    if args.command == "list":
        rows = system.list_memories(project_id=args.project, limit=args.limit)
        print(json.dumps([_memory_to_dict(item) for item in rows], ensure_ascii=False, indent=2))
        return 0
    if args.command == "update":
        record = system.update(args.id, content=args.text)
        print(json.dumps({"updated": bool(record)}, ensure_ascii=False))
        return 0
    if args.command == "disable":
        print(json.dumps({"disabled": system.disable(args.id)}, ensure_ascii=False))
        return 0
    if args.command == "delete":
        print(json.dumps({"deleted": system.delete(args.id, hard=args.hard)}, ensure_ascii=False))
        return 0
    return 2


def _memory_to_dict(memory) -> dict:
    return {
        "memory_id": memory.memory_id,
        "project_id": memory.project_id,
        "scope": memory.scope,
        "memory_type": memory.memory_type.value,
        "status": memory.status.value,
        "content": memory.content,
    }


def _result_to_dict(result) -> dict:
    data = _memory_to_dict(result.memory)
    data["score"] = result.score
    return data


def _trace_to_dict(traced) -> dict:
    return {
        "context": traced.context,
        "included": [item.__dict__ for item in traced.retrieval_trace.included_memories],
        "excluded": [item.__dict__ for item in traced.retrieval_trace.excluded_memories],
        "selected_global_memories": traced.retrieval_trace.selected_global_memories,
        "selected_project_memories": traced.retrieval_trace.selected_project_memories,
    }


if __name__ == "__main__":
    sys.exit(main())
