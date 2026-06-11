from pathlib import Path
import tempfile

from memory_core import MemoryType, RagMemorySystem


system = RagMemorySystem(Path(tempfile.mkdtemp()) / "example_basic.sqlite3", default_project_id="demo")
system.remember("用户偏好：回答要短、直接。", memory_type=MemoryType.PREFERENCE)
print(system.build_context("回答风格"))
