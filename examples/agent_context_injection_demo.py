from pathlib import Path
import tempfile

from memory_core import MemoryType, RagMemorySystem


def build_messages(user_text: str):
    memory = RagMemorySystem(Path(tempfile.mkdtemp()) / "example_agent.sqlite3", default_project_id="agent")
    memory.remember("User preference: direct concise answers.", memory_type=MemoryType.PREFERENCE)
    traced = memory.build_context_with_trace(user_text)
    messages = [{"role": "system", "content": "You are a helpful local agent."}]
    if traced.context:
        messages.append({"role": "system", "content": traced.context})
    messages.append({"role": "user", "content": user_text})
    return messages, traced.retrieval_trace


messages, trace = build_messages("direct concise answers")
print(messages)
print(trace.selected_project_memories)
