# AI-Native SaaS 一周学习计划（改进版）

> 目标：一周内交付一个可演示、可测试、可部署的 AI-Native SaaS 最小闭环，并保留可复用 Prompt 与工程模板。

## 先说原计划的主要问题

- Day 4~5 复杂度偏高（Agent + Tool Calling + Memory + 压缩），对一周节奏有风险。
- 测试与质量门禁放得偏后，容易到 Day 6 才集中返工。
- 缺少明确的“失败回退”策略（模型限流、工具异常、网络抖动）。
- 验收标准多数是“能跑”，较少“可观测、可复现、可维护”的指标。
- 安全与成本控制未前置（API Key、日志脱敏、token 成本监控）。

---

## Day 1：工程基线 + AI 规则固化

- **目标**：把环境和规范一次性定好，减少后续返工。
- **实操**：
  1. 创建项目：`ai-saas-week1/`，初始化 Git + Python 虚拟环境 + Node 环境。
  2. 建立目录：`backend/`, `frontend/`, `infra/`, `tests/`, `ai-prompts/`, `docs/`。
  3. 写 `.cursorrules`、`.editorconfig`、`.env.example`、`pre-commit`。
  4. 配置 `ruff`, `black`, `mypy`, `pytest` 的基础脚本。
- **新增验收**：
  - `pre-commit run --all-files` 通过；
  - `.env.example` 覆盖所有关键配置；
  - `make lint` / `npm run lint` 可执行。

## Day 2：后端最小可运行（FastAPI + DB + Redis）

- **目标**：先有稳定底座，再叠加 Agent 能力。
- **实操**：
  1. FastAPI `lifespan` 管理 PostgreSQL/Redis 连接。
  2. 路由：`/api/v1/health`、`/api/v1/chat`（先回显或 mock）。
  3. SQLAlchemy 2.0 + Alembic 初始迁移。
  4. 全局异常处理 + 统一响应结构（含 `request_id`）。
- **新增验收**：
  - 健康检查同时探测 API/DB/Redis；
  - Alembic `upgrade head` 在新环境可一次通过；
  - 日志可定位请求链路（基础 request id）。

## Day 3：前端聊天壳 + 稳健交互

- **目标**：先把用户交互闭环打通。
- **实操**：
  1. `Vite + React + TS + Zustand + Tailwind` 初始化。
  2. 组件拆分：`ChatInput`, `MessageBubble`, `ChatContainer`。
  3. 流式占位：`EventSource` 或 fetch stream mock。
  4. 错误态：超时、断网、重试、空状态。
- **新增验收**：
  - 首屏加载 < 2s（本地）；
  - 失败请求有可见提示与重试按钮；
  - 暗色模式切换不破版。

## Day 4：Agent Tool Calling（先简单、再扩展）

- **目标**：可控地引入工具调用，避免一开始做“全自动智能体”。
- **实操**：
  1. 工具仅保留 2 个：`search_web_mock`、`query_db_readonly`。
  2. 严格输出协议：`tool_calls | final_answer | error` 三态。
  3. 限制最大循环步数（如 4 步）防止死循环。
  4. 增加工具失败 fallback（用户可读提示 + trace id）。
- **新增验收**：
  - 工具失败不影响接口 200/4xx 的可读返回；
  - 单次请求执行时长有上限（例如 15s 超时）；
  - 至少 3 条 prompt 回归样例稳定通过。

## Day 5：记忆管理与上下文压缩

- **目标**：保证多轮会话稳定、可恢复、成本可控。
- **实操**：
  1. DB 持久化完整消息；Redis 保存最近 5~10 轮热数据。
  2. 摘要策略从“固定 8000”改为“按模型窗口比例阈值”（如 70%）。
  3. 注入策略：`system = summary + recent_turns + safety_rules`。
  4. 新增会话恢复接口与会话清理任务（TTL + 定时清理）。
- **新增验收**：
  - 连续 15 轮不报 token 超限；
  - 中断恢复后可引用历史事实；
  - 摘要前后关键事实一致率可人工抽检（>= 80%）。

## Day 6：重构 + 测试 + 可观测性

- **目标**：让项目进入“可持续迭代”状态。
- **实操**：
  1. 模块拆分：`llm_client.py`, `memory_manager.py`, `tool_registry.py`, `agent_router.py`。
  2. 单测：mock LLM、mock DB、mock Redis、工具异常场景。
  3. 覆盖率目标 >= 75%，关键路径（路由、Agent 决策、记忆）优先。
  4. 增加结构化日志与基础指标（请求耗时、工具调用次数、token 用量）。
- **新增验收**：
  - `pytest --cov` 达标；
  - `ruff + mypy` 无阻断错误；
  - 可从日志追踪一次请求的完整链路。

## Day 7：容器化交付 + 文档作品化

- **目标**：产出可复用作品集与演示资产。
- **实操**：
  1. Dockerfile 多阶段构建，运行时非 root。
  2. `docker-compose.yml` 编排 app + postgres + redis + healthcheck。
  3. README 补齐：架构图、启动命令、变量说明、常见故障排查。
  4. GitHub Actions：`lint -> test -> build`。
  5. 录制 2 分钟 demo：输入 -> Agent 决策 -> 工具调用 -> 输出。
- **新增验收**：
  - 新机器按 README 在 15 分钟内可跑通；
  - CI 首次通过；
  - Demo 能解释“为什么调用工具而不是直接回答”。

---

## 每日固定产出（建议）

- `docs/daily-log/dayN.md`：记录当日目标、问题、决策、明日计划。
- `ai-prompts/dayN.md`：沉淀当天有效 Prompt（含失败案例）。
- `tests/regression/dayN_cases.json`：沉淀回归输入输出样例。

## 风险与应对

- **模型不稳定/限流**：准备备用模型和降级路径（直接回答模板）。
- **联调卡住**：先 mock 工具与模型，保障端到端链路不断。
- **时间超支**：优先交付“可运行 + 可测试 + 可演示”，再做体验优化。

## 改进版最终验收清单

- `docker-compose up -d` 可一键启动全部依赖。
- `/api/v1/chat` 可完成：普通问答 + 工具调用 + 异常回退。
- 多轮对话具备记忆，触发压缩后不丢核心意图。
- `lint + typecheck + test + build` 全部通过。
- 仓库具备：README、架构图、Prompt 库、回归样例、2 分钟 Demo。
