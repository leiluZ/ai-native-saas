# AI-Native SaaS 一周学习计划（原版整理）

## Day 1：AI 编程环境初始化 & Vibe Coding 工作流

- **目标**：建立 AI 驱动的开发环境，掌握「自然语言 -> 架构 -> 代码」闭环。
- **实操**：
  1. 安装 Cursor Pro / Cline，创建 `.cursorrules` 全局规则。
  2. 新建 `ai-saas-week1/`，用 AI 生成项目树。
  3. 配置 Git、pre-commit、基础日志。
- **Prompt 模板**：

```md
# .cursorrules
你是一位资深 AI-Native 全栈架构师。输出代码时必须：
1. 使用类型提示、错误边界、异步优先
2. 禁止硬编码，所有配置走 env
3. 每个函数附带 docstring & 基础异常处理
4. 优先 FastAPI + SQLAlchemy 2.0 + Pydantic V2
5. 生成代码后自动附 pytest 测试骨架
```

- **验收**：`cursor .` 可启动；AI 能按规则生成带类型提示模块；本地 Git 初始化完成。

## Day 2：异步后端骨架（FastAPI + PostgreSQL + Redis）

- **目标**：跑通生产级异步 API、DB 连接池、基础路由与错误处理。
- **实操**：
  1. AI 生成 `main.py`（FastAPI + lifespan + 日志）。
  2. 生成 `models.py`（SQLAlchemy 2.0 声明式）。
  3. Alembic 初始化并生成迁移脚本。
  4. Redis 连接封装（缓存/会话）。
- **Prompt 模板**：

```md
基于 .cursorrules，生成 FastAPI 项目基础结构。要求：
- 使用 lifespan 管理 DB/Redis 连接池
- 路由分层：/api/v1/chat, /api/v1/health
- 全局异常处理器返回统一 JSON 结构
- 包含 pydantic 请求/响应模型
- 附 docker-compose.yml（postgres+redis）
```

- **验收**：`uvicorn main:app --reload` 启动成功；`/docs` 可访问；`curl` 健康检查返回 200。

## Day 3：前端骨架 + 流式交互占位（Vue3/React）

- **目标**：前端对接后端 API，实现基础聊天 UI 与流式响应占位。
- **实操**：
  1. `npm create vite@latest frontend -- --template vue-ts`
  2. 安装 `@vueuse/core`、`tailwindcss`、`shadcn-vue`
  3. AI 生成 Chat 组件（输入框、消息列表、SSE 流式占位）
  4. 对接 `/api/v1/chat`，处理网络异常
- **Prompt 模板**：

```md
生成 Vue3 + TS + Tailwind 聊天界面。要求：
- 使用 Composition API，状态用 Pinia
- 消息列表支持自动滚动、加载态、错误提示
- 使用 EventSource 模拟流式响应（后端暂未接 AI）
- 组件拆分为 ChatInput / MessageBubble / ChatContainer
- 附响应式 CSS 与暗色模式开关
```

- **验收**：前端可发送消息；UI 有模拟流式打字；断网/超时有友好提示。

## Day 4：Agent 核心接入 + Function Calling

- **目标**：接入 OpenAI/Claude，实现 Tool 注册与自动路由。
- **实操**：
  1. 安装 `langchain`, `langchain-openai`
  2. 定义 2 个工具：`search_web`（模拟）、`query_db`（SQL 只读）
  3. 构建 Agent 循环（ReAct 或 Tool Calling）
  4. 前后端联调，返回结构化决策
- **Prompt 模板**：

```md
使用 LangChain 创建 Agent，要求：
- 工具定义使用 @tool 装饰器，含详细 docstring
- LLM 必须返回 tool_calls 或 final_answer
- 实现 fallback：若工具调用失败，返回人类可读提示
- 附完整 FastAPI 路由：接收 prompt -> 调用 agent -> 返回 JSON
- 禁止硬编码 API Key，走 os.environ
```

- **验收**：输入“查一下 PostgreSQL 里 user 表结构”可自动调用 `query_db` 并返回；工具失败不崩溃。

## Day 5：记忆管理 & Context Engineering

- **目标**：实现对话历史持久化、上下文压缩、窗口滑动策略。
- **实操**：
  1. PostgreSQL 存储 `messages(id, session_id, role, content, timestamp)`
  2. Redis 缓存最近 5 轮对话（快速检索）
  3. 超阈值时调用 LLM 做摘要压缩
  4. Agent 注入 `chat_history` 到 prompt
- **Prompt 模板**：

```md
实现会话记忆管理器，要求：
- 每次对话追加到 DB，同时更新 Redis TTL（30min）
- 当 token 数 > 8000 时，触发摘要压缩：
  "将以下对话历史压缩为 3 句话摘要，保留用户意图与关键事实：\n{history}"
- Agent system prompt 动态注入 `{summary} + {recent_turns}`
- 提供 /api/v1/sessions/{id}/history 接口
```

- **验收**：连续对话 15 轮不超限；中断恢复会话可继承上下文；摘要后意图不丢失。

## Day 6：AI 驱动重构 & 测试覆盖

- **目标**：用 AI 自动化重构、生成测试、提升代码质量。
- **实操**：
  1. 对 `agent.py` 执行模块化拆分（路由/记忆/工具/LLM）
  2. 生成 pytest 单元测试（mock LLM、mock DB）
  3. 配置 `pytest-cov`，覆盖率目标 > 75%
  4. 运行 `ruff + black` 格式化
- **Prompt 模板**：

```md
对当前 agent.py 执行以下操作：
1. 拆分为：llm_client.py, memory_manager.py, tool_registry.py, agent_router.py
2. 为每个模块生成 pytest 测试，使用 pytest-mock 隔离外部调用
3. 确保所有函数有类型提示与异常边界
4. 输出 pytest 运行命令与覆盖率检查脚本
```

- **验收**：`pytest --cov` > 75%；无 lint 报错；模块职责清晰，无循环依赖。

## Day 7：容器化部署 & 作品集封装

- **目标**：一键部署、编写技术文档、录制 Demo、沉淀 Prompt 库。
- **实操**：
  1. 编写 Dockerfile（多阶段构建）+ `docker-compose.yml`
  2. 生成 `README.md`（架构图、本地运行、AI 辅助比例说明）
  3. 录制 2 分钟端到端演示视频
  4. 整理 `ai-prompts/` 目录，提交 GitHub
- **Prompt 模板**：

```md
为当前项目生成生产级部署与文档：
1. Dockerfile：多阶段构建，仅保留运行依赖，非 root 用户
2. docker-compose：postgres + redis + app + 健康检查
3. README：包含架构图（Mermaid）、本地启动命令、环境变量示例、AI 工作流说明
4. 输出 GitHub Actions CI 模板（lint -> test -> build）
```

- **验收**：`docker-compose up -d` 一键启动；README 完整；Demo 展示 Agent 决策流；Prompt 库结构化归档。

## 高频 Prompt 模板（占位）

1. Context Engineering 压缩策略
2. Agent 路由防死循环 Prompt
3. AI-Native 代码审查 Prompt（Cline/Cursor Review）

## 动态调整建议（原版）

- 前端强 / 后端弱：Day 2-4 放慢节奏，先跑通 FastAPI 基础后再接 Agent。
- 后端强 / 前端弱：Day 3 优先组件库，更多时间放 Day 4-5 的 Agent 与记忆。
- 无 AI 开发经验：先聚焦 Day 4-6 的 Agent 管道与 Prompt 工程。
- 熟 Flask 不熟 FastAPI：追加“保持 Flask 类似装饰器风格，但使用 FastAPI 异步语法”。

## 第 7 天自测清单（原版）

- `docker-compose up` 跑通前后端 + DB + Redis
- Agent 可自动工具调用/回答，不卡死
- 对话超 8k token 能摘要压缩，意图不丢失
- pytest 覆盖率 >= 75%，无 lint 报错
- GitHub 仓库含架构图、运行命令、Prompt 库、2 分钟 Demo
- 能清晰口述 AI 开发闭环方法论
