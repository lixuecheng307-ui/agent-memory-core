from pathlib import Path
import tempfile

from memory_core import MemoryType, RagMemorySystem


system = RagMemorySystem(Path(tempfile.mkdtemp()) / "example_graph.sqlite3", default_project_id="agent")
memory = system.remember("Agent Memory Core supports project isolation.", memory_type=MemoryType.PROJECT)
agent = system.add_entity("Agent Memory Core", entity_type="project")
isolation = system.add_entity("project isolation", entity_type="capability")
system.add_relation(agent.entity_id, isolation.entity_id, relation_type="supports", source_memory_id=memory.memory_id)
print(system.build_entity_context("Agent Memory Core"))
