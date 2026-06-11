from pathlib import Path
import tempfile

from memory_core import MemoryType, RagMemorySystem


system = RagMemorySystem(Path(tempfile.mkdtemp()) / "example_context.sqlite3", default_project_id="agent")
system.remember("偏好：回答要短。", memory_type=MemoryType.PREFERENCE)
system.remember("原始日志：用户说 hello。", memory_type=MemoryType.RAW_SESSION_LOG, allow_context_injection=False)
trace = system.build_context_with_trace("回答风格")
print(trace.context)
print([item.reason for item in trace.retrieval_trace.excluded_memories])
