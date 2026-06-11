from pathlib import Path
import tempfile

from memory_core import MemoryType, RagMemorySystem


system = RagMemorySystem(Path(tempfile.mkdtemp()) / "example_project_isolation.sqlite3", default_project_id="alpha_agent")
system.remember("alpha_agent 项目：先完成 RAG。", project_id="alpha_agent", memory_type=MemoryType.PROJECT)
system.remember("job_agent 项目：先完成简历解析。", project_id="job_agent", memory_type=MemoryType.PROJECT)
system.remember("全局偏好：回答直接。", project_id="global", scope="global", memory_type=MemoryType.PREFERENCE)
print(system.build_context("当前项目目标", project_id="alpha_agent"))
print(system.build_context("当前项目目标", project_id="job_agent"))
