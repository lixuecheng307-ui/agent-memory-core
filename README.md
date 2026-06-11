# Agent Memory Core

本地优先、项目隔离、可审计的 AI Agent 记忆核心。
Lightweight, local, project-isolated, auditable memory core for AI agents.

Agent Memory Core 是一个可复用的本地记忆与 RAG 子系统，适合接入 Python 智能体项目。它可以帮助智能体保存长期记忆、按项目隔离记忆、检索相关记忆，并在调用大模型前构建经过审计的上下文。

Agent Memory Core is a reusable local memory and RAG subsystem for Python-based AI agents. It helps agents store, isolate, retrieve, audit, and inject long-term memory before model calls.

---

## 这个项目解决什么问题？

普通 AI Agent 容易遇到几个问题：

1. 长期信息容易丢失。
2. 不同项目的记忆容易混在一起。
3. 删除或禁用的记忆可能仍然被错误召回。
4. 原始对话日志如果直接进入 prompt，容易污染长期记忆。
5. 很多 RAG Demo 只做文档问答，没有处理记忆管理、项目隔离和用户控制。

Agent Memory Core 的目标是提供一个轻量、可复制、可测试的记忆核心，让智能体可以更安全地管理长期记忆。

---

## What problem does it solve?

AI agents often forget long-term context, mix information across projects, or accidentally reuse disabled/deleted memories.

Agent Memory Core provides a small local memory layer that separates memories by project, supports selected global memory sharing, and prevents disabled or deleted memories from being recalled.

---

## 核心能力 / Features

* 项目级记忆：不同项目使用不同 `project_id` 隔离。
* 全局记忆：长期偏好等信息可以跨项目共享。
* 13 类记忆类型：用于组织偏好、任务、事实、习惯等信息。
* 本地 SQLite 存储：默认不需要外部服务。
* 本地向量召回：支持离线测试和演示。
* 可选 ChromaDB 后端。
* 可选 OpenAI-compatible embedding provider。
* 记忆审计：判断记忆是否适合保存或注入上下文。
* 上下文注入控制：不是所有记忆都会自动进入 prompt。
* 删除 / 禁用过滤：删除或禁用后的记忆不会再参与召回。
* 冲突标记与替换关系。
* 事件历史与版本记录。
* RetrievalTrace / ContextBuildTrace：可以查看哪些记忆被使用，哪些被过滤。
* 轻量 Graph Memory。
* CLI 命令行工具。
* Benchmark 评测。
* Examples 示例。
* GitHub Actions 自动测试。

---

## 安装 / Install

在项目目录下执行：

```powershell
python -m pip install -e .
```

默认使用 SQLite，本地即可运行，不需要外部数据库。

The default backend uses SQLite and does not require an external service.

---

## 快速示例 / Quick Example

```python
from pathlib import Path
from memory_core import MemoryType, RagMemorySystem

memory = RagMemorySystem(Path("memory.sqlite3"), default_project_id="agent_app")

memory.remember(
    "用户喜欢简洁直接的回答。",
    memory_type=MemoryType.PREFERENCE,
)

context = memory.build_context("应该用什么风格回答用户？")
print(context)
```

---

## 命令行使用 / CLI

```powershell
memory-core --help
memory-core init
memory-core remember --project alpha_agent --text "用户喜欢简洁 UI。"
memory-core search --project alpha_agent --query "用户喜欢什么 UI 风格？"
memory-core context --project alpha_agent --query "回答时应该注意什么？"
memory-core benchmark
```

---

## 示例 / Examples

示例位于 `examples/` 目录：

* `basic_usage.py`
* `project_isolation_demo.py`
* `context_injection_demo.py`
* `delete_disable_demo.py`
* `conflict_resolution_demo.py`
* `history_timeline_demo.py`
* `graph_memory_demo.py`
* `agent_context_injection_demo.py`
* `chroma_usage.py`
* `openai_compatible_embedding_usage.py`

---

## Benchmark

运行：

```powershell
memory-core benchmark
```

当前 benchmark 会检查：

* Recall@K
* 项目记忆泄漏率 / Project Leakage Rate
* 禁用记忆召回率 / Disabled Recall Rate
* 删除记忆召回率 / Deleted Recall Rate
* 敏感记忆注入率 / Sensitive Injection Rate
* 冲突处理准确率 / Conflict Resolution Accuracy
* 平均检索耗时 / Average Retrieval Latency
* 上下文长度估算 / Context Token Estimate

---

## 文档 / Documentation

* `docs/ARCHITECTURE.md`
* `docs/API_REFERENCE.md`
* `docs/ACCEPTANCE.md`
* `docs/SECURITY_AND_PRIVACY.md`
* `docs/AGENT_INTEGRATION.md`
* `docs/ROADMAP.md`

---

## 重要说明 / Important Notes

* 默认 embedding provider 主要用于本地测试和演示，不代表生产级语义效果。
* SQLite 是默认本地后端。
* ChromaDB 是可选后端。
* OpenAI-compatible embedding provider 需要宿主应用显式传入 API key。
* 原始日志建议使用 `allow_context_injection=False`，避免未经筛选的信息直接进入 prompt。
* MCP、LangGraph、LlamaIndex 和 Web Demo 属于可选 / 实验性接入，不承诺长期生产级兼容。

The default deterministic embedding provider is for offline tests and demos. It is not a production-grade semantic embedding model.

MCP, LangGraph, LlamaIndex, and the web demo are optional or experimental integrations.

---

## 测试 / Testing

运行：

```powershell
python -m pytest tests -q
```

GitHub Actions 会在 push 时自动运行核心测试。

---

## 项目状态 / Project Status

当前版本适合用于：

* AI Agent 记忆系统 Demo
* 个人作品集项目
* 智能体长期记忆方案验证
* 本地记忆 / RAG 子系统实验
* 其他 Agent 项目的可复用记忆核心参考

当前版本不宣称是企业生产级系统。如果用于真实生产环境，还需要补充权限控制、加密、并发测试、迁移机制和更完整的长期维护策略。

This project is suitable for demos, experiments, portfolio use, and integration prototypes. It is not advertised as an enterprise production system.

---

## License

MIT License.
