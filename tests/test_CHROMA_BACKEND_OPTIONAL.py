import importlib.util
import tempfile
from pathlib import Path

import pytest

from memory_core import MemoryType, RagMemorySystem


pytestmark = pytest.mark.skipif(importlib.util.find_spec("chromadb") is None, reason="chromadb optional dependency not installed")


def test_chromadb_backend_remember_search_disable_delete():
    with tempfile.TemporaryDirectory() as tmp:
        system = RagMemorySystem(Path(tmp) / "chroma", default_project_id="agent", store_backend="chroma")
        record = system.remember("ChromaDB 后端是可选能力。", memory_type=MemoryType.PROJECT)

        assert record is not None
        assert any("可选能力" in result.memory.content for result in system.recall("ChromaDB 后端是什么"))
        assert system.disable(record.memory_id)
        assert not any(result.memory.memory_id == record.memory_id for result in system.recall("ChromaDB 后端是什么"))

        deleted = system.remember("ChromaDB 删除后不能召回。", memory_type=MemoryType.PROJECT)
        assert system.delete(deleted.memory_id)
        assert not any(result.memory.memory_id == deleted.memory_id for result in system.recall("删除后能否召回"))
