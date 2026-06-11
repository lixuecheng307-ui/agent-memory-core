# Contributing

Run the focused gate before submitting changes:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_MEMORY_CORE_RAG_ACCEPTANCE.py tests/test_MEMORY_CORE_HISTORY_TRACE_GRAPH.py -q
```

Rules:

- keep `memory_core/` independent
- avoid implicit secrets
- keep optional dependencies optional
- document any behavior that affects prompt context
