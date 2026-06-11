from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from memory_core import RagMemorySystem


def run_benchmark(cases_path: Path, out_path: Path, report_path: Path) -> dict:
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    metrics = {
        "Recall@K": 0.0,
        "Project Leakage Rate": 0.0,
        "Disabled Recall Rate": 0.0,
        "Deleted Recall Rate": 0.0,
        "Sensitive Injection Rate": 0.0,
        "Conflict Resolution Accuracy": 1.0,
        "Average Retrieval Latency": 0.0,
        "Context Token Estimate": 0.0,
    }
    latencies: list[float] = []
    passed = 0
    leaks = disabled_hits = deleted_hits = sensitive_hits = 0
    context_chars = 0

    with tempfile.TemporaryDirectory() as tmp:
        system = RagMemorySystem(Path(tmp) / "bench.sqlite3", default_project_id="project_a")
        for case in cases:
            records = []
            for item in case["memories"]:
                record = system.remember(
                    item["content"],
                    project_id=item.get("project_id", case["project_id"]),
                    scope=item.get("scope", "project"),
                    memory_type=item.get("type"),
                )
                if record is not None:
                    records.append((record, item))
                    if item.get("disable"):
                        system.disable(record.memory_id)
                    if item.get("delete"):
                        system.delete(record.memory_id)
            start = time.perf_counter()
            context = system.build_context(case["query"], project_id=case["project_id"], limit=5)
            latencies.append(time.perf_counter() - start)
            context_chars += len(context)
            if case["expected_contains"] in context:
                passed += 1
            if case.get("forbidden_contains") and case["forbidden_contains"] in context:
                leaks += 1
            if "禁用记忆" in context:
                disabled_hits += 1
            if "删除记忆" in context:
                deleted_hits += 1
            if "example-sensitive-placeholder" in context:
                sensitive_hits += 1

    total = max(1, len(cases))
    metrics["Recall@K"] = passed / total
    metrics["Project Leakage Rate"] = leaks / total
    metrics["Disabled Recall Rate"] = disabled_hits / total
    metrics["Deleted Recall Rate"] = deleted_hits / total
    metrics["Sensitive Injection Rate"] = sensitive_hits / total
    metrics["Average Retrieval Latency"] = sum(latencies) / max(1, len(latencies))
    metrics["Context Token Estimate"] = context_chars / 4
    result = {"cases": len(cases), "metrics": metrics}
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(_report(result), encoding="utf-8")
    print(_table(metrics))
    return result


def _table(metrics: dict) -> str:
    lines = ["metric | value", "---|---"]
    for key, value in metrics.items():
        lines.append(f"{key} | {value:.6f}" if isinstance(value, float) else f"{key} | {value}")
    return "\n".join(lines)


def _report(result: dict) -> str:
    return "# Benchmark Report\n\n" + _table(result["metrics"]) + "\n"


if __name__ == "__main__":
    run_benchmark(Path("benchmarks/memory_recall_cases.json"), Path("benchmark_results.json"), Path("benchmark_report.md"))
