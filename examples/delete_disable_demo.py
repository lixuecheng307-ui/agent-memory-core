from pathlib import Path
import tempfile

from memory_core import MemoryType, RagMemorySystem


system = RagMemorySystem(Path(tempfile.mkdtemp()) / "example_delete_disable.sqlite3", default_project_id="agent")
disabled = system.remember("用户喜欢蓝色 UI。", memory_type=MemoryType.PREFERENCE)
deleted = system.remember("用户喜欢红色 UI。", memory_type=MemoryType.PREFERENCE)
kept = system.remember("用户喜欢极简 UI。", memory_type=MemoryType.PREFERENCE)
system.disable(disabled.memory_id)
system.delete(deleted.memory_id)
print([result.memory.content for result in system.recall("用户喜欢什么 UI", limit=10)])
assert kept.content in [result.memory.content for result in system.recall("用户喜欢什么 UI", limit=10)]
