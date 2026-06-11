# Acceptance

Baseline gate:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_MEMORY_CORE_RAG_ACCEPTANCE.py tests/test_PRE_FINAL_MODEL_ROUTING_01.py tests/test_BOOT_01.py tests/test_SP_14.py -q
```

Memory Core focused gate:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_MEMORY_CORE_RAG_ACCEPTANCE.py tests/test_MEMORY_CORE_HISTORY_TRACE_GRAPH.py -q
```

CLI smoke:

```powershell
memory-core --help
memory-core init
memory-core benchmark
```

Optional tests should skip gracefully when dependencies such as `chromadb` or
`mcp` are not installed.
