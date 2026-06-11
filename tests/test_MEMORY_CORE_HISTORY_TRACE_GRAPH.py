import tempfile
from pathlib import Path

from memory_core import MemoryType, RagMemorySystem


def make_system(tmp: str) -> RagMemorySystem:
    return RagMemorySystem(Path(tmp) / "memory.sqlite3", default_project_id="project_a")


def test_update_disable_delete_create_events_and_versions():
    with tempfile.TemporaryDirectory() as tmp:
        system = make_system(tmp)
        record = system.remember("用户喜欢复杂 UI。", memory_type=MemoryType.PREFERENCE)

        updated = system.update(record.memory_id, content="用户喜欢极简 UI。")
        assert updated is not None
        assert system.disable(record.memory_id)
        assert system.delete(record.memory_id)

        events = [event.event_type for event in system.list_events(record.memory_id)]
        assert "remember" in events
        assert "update" in events
        assert "disable" in events
        assert "delete" in events
        history = system.get_memory_history(record.memory_id)
        assert any(version.reason == "before_update" and "复杂" in version.content for version in history)
        assert any(version.reason == "after_update" and "极简" in version.content for version in history)


def test_conflict_replacement_links_old_and_new_memory_and_context_uses_current():
    with tempfile.TemporaryDirectory() as tmp:
        system = make_system(tmp)
        old = system.remember("用户喜欢复杂花哨的 UI。", memory_type=MemoryType.PREFERENCE)
        new = system.remember("用户喜欢极简克制的 UI。", memory_type=MemoryType.PREFERENCE, replace_conflicts=True)

        old_after = system.get(old.memory_id)
        assert new.supersedes_memory_id == old.memory_id
        assert old_after.superseded_by_memory_id == new.memory_id
        context = system.build_context("用户喜欢什么 UI")
        assert "极简" in context
        assert "复杂花哨" not in context


def test_retrieval_trace_records_exclusion_reasons_and_global_selection():
    with tempfile.TemporaryDirectory() as tmp:
        system = make_system(tmp)
        disabled = system.remember("项目偏好：使用蓝色 UI。", memory_type=MemoryType.PREFERENCE)
        deleted = system.remember("项目偏好：使用红色 UI。", memory_type=MemoryType.PREFERENCE)
        raw = system.remember(
            "原始日志：用户随口说 hello。",
            memory_type=MemoryType.RAW_SESSION_LOG,
            allow_context_injection=False,
        )
        system.remember("全局偏好：回答要短。", project_id="global", scope="global", memory_type=MemoryType.PREFERENCE)
        system.remember("其他项目偏好：回答要长。", project_id="other_project", memory_type=MemoryType.PREFERENCE)

        system.disable(disabled.memory_id)
        system.delete(deleted.memory_id)

        _results, trace = system.retrieve_with_trace("回答风格和 UI 偏好", context_only=True)
        excluded = {item.memory_id: item.reason for item in trace.excluded_memories}

        assert excluded[disabled.memory_id] == "disabled"
        assert excluded[deleted.memory_id] == "deleted"
        assert excluded[raw.memory_id] == "allow_context_injection_false"
        assert any(item.reason == "project_mismatch" for item in trace.excluded_memories)
        assert trace.selected_global_memories


def test_lightweight_graph_memory_manual_entities_and_relations():
    with tempfile.TemporaryDirectory() as tmp:
        system = make_system(tmp)
        memory = system.remember("Agent Memory Core 支持项目隔离。", memory_type=MemoryType.PROJECT)
        agent = system.add_entity("Agent Memory Core", entity_type="project")
        isolation = system.add_entity("project isolation", entity_type="capability")

        relation = system.add_relation(
            agent.entity_id,
            isolation.entity_id,
            relation_type="supports",
            source_memory_id=memory.memory_id,
            confidence=0.95,
        )

        assert relation in system.search_by_entity("Agent Memory Core")
        context = system.build_entity_context("Agent Memory Core")
        assert "supports" in context
        assert "project isolation" in context
