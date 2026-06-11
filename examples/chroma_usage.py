from pathlib import Path
import tempfile

from memory_core import MemoryType, RagMemorySystem


try:
    system = RagMemorySystem(Path(tempfile.mkdtemp()) / "example_chroma", default_project_id="agent", store_backend="chroma")
except RuntimeError as exc:
    print(f"ChromaDB optional dependency is not installed: {exc}")
else:
    system.remember("ChromaDB backend is optional.", memory_type=MemoryType.PROJECT)
    print(system.build_context("Which backend is optional?"))
