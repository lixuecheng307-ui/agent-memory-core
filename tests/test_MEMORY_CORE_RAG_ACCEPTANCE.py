import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from memory_core import MemoryAuditor, MemoryType, OpenAICompatibleEmbeddingProvider, RagMemorySystem


def make_system(tmp: str, project_id: str = "project_a") -> RagMemorySystem:
    return RagMemorySystem(Path(tmp) / "rag.sqlite3", default_project_id=project_id)


def test_rag_retrieves_semantic_memory_without_keyword_overlap():
    with tempfile.TemporaryDirectory() as tmp:
        system = make_system(tmp)
        system.remember("用户偏好：界面要极简、克制、信息密度高。", memory_type=MemoryType.PREFERENCE)
        system.remember("Browser automation uses the managed profile and CDP port.", memory_type=MemoryType.BROWSER_EXPERIENCE)

        results = system.recall("我喜欢什么 UI 风格", limit=2)

        assert results
        assert "极简" in results[0].memory.content
        assert results[0].score > 0


def test_project_isolation_and_global_memory_sharing():
    with tempfile.TemporaryDirectory() as tmp:
        system = make_system(tmp, project_id="alpha_agent")
        system.remember("alpha_agent 当前目标：先完成 RAG 验收。", project_id="alpha_agent", memory_type=MemoryType.PROJECT)
        system.remember("finance_agent 当前目标：先做财务报表。", project_id="finance_agent", memory_type=MemoryType.PROJECT)
        system.remember("用户长期偏好：回答要直接、务实。", project_id="global", scope="global", memory_type=MemoryType.PREFERENCE)

        alpha = system.recall("当前项目目标", project_id="alpha_agent", limit=5)
        finance = system.recall("当前项目目标", project_id="finance_agent", limit=5)

        assert any("RAG 验收" in result.memory.content for result in alpha)
        assert not any("财务报表" in result.memory.content for result in alpha)
        assert any("财务报表" in result.memory.content for result in finance)

        preference = system.recall("回答风格偏好", project_id="alpha_agent", limit=5)
        assert any("直接、务实" in result.memory.content for result in preference)


def test_disable_and_delete_remove_records_from_recall():
    with tempfile.TemporaryDirectory() as tmp:
        system = make_system(tmp)
        disabled = system.remember("用户喜欢蓝色单色 UI。", memory_type=MemoryType.PREFERENCE)
        deleted = system.remember("用户喜欢复杂霓虹 UI。", memory_type=MemoryType.PREFERENCE)
        kept = system.remember("用户喜欢极简 UI。", memory_type=MemoryType.PREFERENCE)

        assert disabled is not None and deleted is not None and kept is not None
        assert system.disable(disabled.memory_id)
        assert system.delete(deleted.memory_id)

        texts = [result.memory.content for result in system.recall("用户喜欢什么 UI", limit=10)]

        assert kept.content in texts
        assert disabled.content not in texts
        assert deleted.content not in texts


def test_update_reembeds_memory_and_changes_recall_result():
    with tempfile.TemporaryDirectory() as tmp:
        system = make_system(tmp)
        record = system.remember("用户喜欢厚重复杂的界面。", memory_type=MemoryType.PREFERENCE)

        assert record is not None
        updated = system.update(record.memory_id, content="用户喜欢极简克制的界面。")

        assert updated is not None
        assert "极简" in updated.content
        results = system.recall("用户喜欢什么 UI 风格", limit=5)
        assert any(result.memory.memory_id == record.memory_id and "极简" in result.memory.content for result in results)


def test_conflicting_memory_can_be_marked_without_auto_replacement():
    with tempfile.TemporaryDirectory() as tmp:
        system = make_system(tmp)
        first = system.remember("用户喜欢复杂花哨的 UI。", memory_type=MemoryType.PREFERENCE)
        second = system.remember("用户喜欢极简克制的 UI。", memory_type=MemoryType.PREFERENCE)

        assert first is not None and second is not None
        assert first.memory_id in second.metadata.get("conflicts_with", [])
        ids = {result.memory.memory_id for result in system.recall("用户喜欢什么 UI", limit=10)}
        assert first.memory_id in ids
        assert second.memory_id in ids


def test_conflicting_memory_replacement_disables_old_record():
    with tempfile.TemporaryDirectory() as tmp:
        system = make_system(tmp)
        first = system.remember("用户喜欢复杂花哨的 UI。", memory_type=MemoryType.PREFERENCE)
        second = system.remember("用户喜欢极简克制的 UI。", memory_type=MemoryType.PREFERENCE, replace_conflicts=True)

        assert first is not None and second is not None
        assert first.memory_id in second.metadata.get("replaces", [])
        texts = [result.memory.content for result in system.recall("用户喜欢什么 UI", limit=10)]
        assert second.content in texts
        assert first.content not in texts


def test_sensitive_content_is_not_vectorized_or_recalled():
    with tempfile.TemporaryDirectory() as tmp:
        system = make_system(tmp)
        record = system.remember("OPENAI API Key 是 example-sensitive-value", memory_type=MemoryType.LONG_TERM)

        assert record is None
        assert system.recall("API Key 是什么", limit=5) == []


def test_context_injection_uses_only_allowed_active_memory():
    with tempfile.TemporaryDirectory() as tmp:
        system = make_system(tmp)
        system.remember("项目规则：删除记忆后不能再召回。", memory_type=MemoryType.SAFETY)
        short_lived = system.remember("笑死，我只是随口自嘲一下。")

        assert short_lived is not None
        context = system.build_context("记忆删除后应该怎么样", limit=5)

        assert "删除记忆后不能再召回" in context
        assert "随口自嘲" not in context


def test_memory_auditor_classifies_core_human_memory_types():
    auditor = MemoryAuditor()

    assert auditor.audit("我讨厌满屏模块，喜欢极简 UI").memory_type is MemoryType.PREFERENCE
    assert auditor.audit("浏览器自动化应该复用 CDP profile").memory_type is MemoryType.BROWSER_EXPERIENCE
    assert auditor.audit("这个项目现在不能打包").memory_type is MemoryType.PROJECT
    assert auditor.audit("笑死，我好蠢").memory_type is MemoryType.EMOTION
    assert not auditor.audit("密码是 123456").should_remember


def test_memory_core_can_be_copied_to_an_external_project_and_used():
    with tempfile.TemporaryDirectory() as tmp:
        external_root = Path(tmp) / "external_project"
        shutil.copytree(Path(__file__).resolve().parents[1] / "memory_core", external_root / "memory_core")
        script = """
from pathlib import Path
from memory_core import MemoryType, RagMemorySystem

system = RagMemorySystem(Path("portable.sqlite3"), default_project_id="external_app")
system.remember("外部项目偏好：回答要短、直接。", memory_type=MemoryType.PREFERENCE)
results = system.recall("外部项目回答风格", project_id="external_app")
assert results and "短、直接" in results[0].memory.content
print("portable-ok")
"""

        env = {**os.environ, "PYTHONPATH": str(external_root)}
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=external_root,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        assert "portable-ok" in result.stdout


def test_chromadb_backend_fails_explicitly_when_dependency_missing():
    with tempfile.TemporaryDirectory() as tmp:
        try:
            RagMemorySystem(Path(tmp) / "chroma", store_backend="chroma")
        except RuntimeError as exc:
            assert "chromadb is not installed" in str(exc)
        else:
            assert True


def test_openai_compatible_embedding_provider_uses_explicit_key_and_normalizes(monkeypatch):
    calls = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"data":[{"embedding":[3,4]}]}'

    def fake_urlopen(request, timeout):
        calls["url"] = request.full_url
        calls["headers"] = dict(request.header_items())
        calls["body"] = request.data.decode("utf-8")
        calls["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = OpenAICompatibleEmbeddingProvider(
        api_key="unit",
        base_url="https://example.test/v1",
        model="embed-test",
        timeout=12,
    )

    vector = provider.embed("hello")

    assert calls["url"] == "https://example.test/v1/embeddings"
    assert calls["headers"]["Authorization"] == "Bearer unit"
    assert '"model": "embed-test"' in calls["body"]
    assert calls["timeout"] == 12
    assert vector == [0.6, 0.8]
