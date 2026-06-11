from pathlib import Path
import tempfile

from memory_core import MemoryType, RagMemorySystem


system = RagMemorySystem(Path(tempfile.mkdtemp()) / "example_history.sqlite3", default_project_id="agent")
record = system.remember("用户喜欢复杂 UI。", memory_type=MemoryType.PREFERENCE)
system.update(record.memory_id, content="用户喜欢极简 UI。")
system.disable(record.memory_id)
print([event.event_type for event in system.list_events(record.memory_id)])
print([(version.reason, version.content) for version in system.get_memory_history(record.memory_id)])
