from pathlib import Path
import tempfile

from memory_core import MemoryType, OpenAICompatibleEmbeddingProvider, RagMemorySystem


def build_system(explicit_api_key: str):
    provider = OpenAICompatibleEmbeddingProvider(
        api_key=explicit_api_key,
        base_url="https://api.example.test/v1",
        model="text-embedding-example",
    )
    return RagMemorySystem(Path(tempfile.mkdtemp()) / "example_openai_embeddings.sqlite3", embedding_provider=provider)


print("Pass an explicit API key from the host app, then call build_system(key).")
print("No environment variables or local config files are read by this example.")
