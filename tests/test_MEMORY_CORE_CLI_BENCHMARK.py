import json
import tempfile
from pathlib import Path

from benchmarks.run_memory_benchmark import run_benchmark
from memory_core.cli import main


def test_cli_init_remember_search_context_benchmark_smoke(capsys):
    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "memory.sqlite3")

        assert main(["--db", db, "init"]) == 0
        assert main(["--db", db, "remember", "--project", "agent", "--text", "用户喜欢极简 UI。", "--type", "preference"]) == 0
        assert main(["--db", db, "search", "--project", "agent", "--query", "用户喜欢什么界面"]) == 0
        assert main(["--db", db, "context", "--project", "agent", "--query", "用户喜欢什么界面", "--trace"]) == 0

        output = capsys.readouterr().out
        assert "极简" in output
        assert "included" in output


def test_benchmark_writes_json_and_report():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "benchmark_results.json"
        report = Path(tmp) / "benchmark_report.md"
        result = run_benchmark(Path("benchmarks/memory_recall_cases.json"), out, report)

        assert out.exists()
        assert report.exists()
        assert json.loads(out.read_text(encoding="utf-8"))["cases"] >= 1
        assert "Recall@K" in report.read_text(encoding="utf-8")
        assert result["metrics"]["Deleted Recall Rate"] == 0
