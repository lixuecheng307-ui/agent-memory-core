$ErrorActionPreference = "Stop"
$db = ".agent_memory_core\demo.sqlite3"

memory-core --db $db init
memory-core --db $db remember --project alpha_agent --text "alpha_agent project memory: finish the auditable RAG loop first." --type project
memory-core --db $db remember --project job_agent --text "job_agent 项目记忆：先做简历解析。" --type project
memory-core --db $db remember --global-memory --text "全局偏好：回答要直接、短。" --type preference
memory-core --db $db search --project alpha_agent --query "当前项目目标"
memory-core --db $db search --project job_agent --query "当前项目目标"
memory-core --db $db context --project alpha_agent --query "怎么回答当前项目问题" --trace
memory-core benchmark
