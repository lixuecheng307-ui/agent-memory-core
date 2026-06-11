from pathlib import Path
import tempfile

from memory_core import MemoryType, RagMemorySystem


system = RagMemorySystem(Path(tempfile.mkdtemp()) / "example_conflict.sqlite3", default_project_id="agent")
old = system.remember("用户喜欢复杂花哨的 UI。", memory_type=MemoryType.PREFERENCE)
new = system.remember("用户喜欢极简克制的 UI。", memory_type=MemoryType.PREFERENCE, replace_conflicts=True)
print({"old": old.memory_id, "new": new.memory_id, "new_supersedes": new.supersedes_memory_id})
print(system.build_context("用户喜欢什么 UI"))
