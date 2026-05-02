# Week 2: 多 Agent 编排与状态机架构

## 🎯 目标
从单 Agent 升级到 LangGraph 多智能体状态机，实现任务路由、人工介入与记忆隔离。

## 每日学习计划

## Day 1：LangGraph 基础 - State Schema / Nodes / Edges

- **目标**：掌握 LangGraph 核心概念，理解状态机编程模型。
- **实操**：
  1. 安装 `langgraph`, `langgraph-sdk`
  2. 定义 `AgentState` - 包含 `messages`, `next_action`, `session_id` 等字段
  3. 创建基础 Node：`greet_node`, `process_node`, `respond_node`
  4. 使用 `StateGraph` 连接节点，构建简单 DAG
  5. 编译图并测试调用流程
- **Prompt 模板**：

```md
使用 LangGraph 创建简单状态机。要求：
- 定义 AgentState：messages(list), next_action(str), session_id(str)
- 创建 3 个 Node：greet_node 返回问候，process_node 处理输入，respond_node 返回结果
- 使用 add_edge 连接节点：START -> greet -> process -> respond -> END
- 编译图并调用，验证状态流转
- 附完整代码和状态图可视化
```

- **验收**：`python -c "from langgraph.graph import StateGraph"` 无报错；简单 DAG 可执行并返回正确结果。

---

## Day 2：构建 Router → Executor → Reviewer 协作链

- **目标**：实现多 Agent 协作链，理解节点间数据传递与条件路由。
- **实操**：
  1. 定义 `RouterNode` - 分析用户意图，决定下一步
  2. 定义 `ExecutorNode` - 执行具体任务（搜索/计算/查询）
  3. 定义 `ReviewerNode` - 评估结果质量，决定是否重试或返回
  4. 使用 `add_conditional_edges` 实现动态路由
  5. 对接 Week1 的 Tool Registry
- **Prompt 模板**：

```md
使用 LangGraph 构建 Router -> Executor -> Reviewer 协作链。要求：
- RouterNode：根据用户输入判断是 "weather" | "time" | "calc" | "general"
- ExecutorNode：根据路由执行对应工具，使用 add_tool_node 注册工具
- ReviewerNode：检查结果是否合理（长度 > 5 字符），否则触发重试
- 使用 conditional_edges 根据 Router 返回值决定下一步
- 整合 Week1 的 tool_registry，实现工具调用
- 附 DAG 可视化和调用示例
```

- **验收**：输入"北京天气"自动路由到天气工具；输入"1+1等于多少"自动路由到计算工具；Reviewer 拒绝空结果并触发重试。

---

## Day 3：Human-in-the-Loop 中断点与审批恢复

- **目标**：实现人工介入机制，让 AI 在关键节点暂停等待人类决策。
- **实操**：
  1. 使用 `Command(resume={...})` 实现中断
  2. 定义 `ApprovalNode` - 低置信度时触发人工审批
  3. 实现 `interrupt_before` / `interrupt_after` 配置
  4. 使用 `langgraph checkpointing` 保存中断状态
  5. 提供 REST API 支持人类审批/拒绝
- **Prompt 模板**：

```md
为 LangGraph 添加 Human-in-the-Loop 机制。要求：
- 定义 ApprovalNode：当置信度 < 0.7 时返回 Command(resume={approved: False})
- 使用 interrupt_before=["ApprovalNode"] 配置中断点
- 实现 /api/v1/chat/approve 接口，接受 {thread_id, approved: bool, modified_result}
- 中断恢复后继续执行：approved=True 用原结果，approved=False 用修改结果
- 使用 MemorySaver 实现状态持久化
- 附完整 API 和测试用例
```

- **验收**：`Command(resume={...})` 可中断图执行；恢复后状态一致；API 可审批/拒绝；断线重连不丢状态。

---

## Day 4：会话级记忆隔离 (独立 State 存储)

- **目标**：实现多会话并发隔离，每会话独立记忆上下文。
- **实操**：
  1. 使用 `store` 参数配置独立 MemorySaver
  2. 每个 `thread_id` 对应独立状态存储
  3. 实现会话历史查询接口
  4. 添加会话超时自动清理
  5. 对接 Week1 的 MemoryManager
- **Prompt 模板**：

```md
为 LangGraph 实现会话级记忆隔离。要求：
- 每个 thread_id 使用独立的 MemorySaver 存储
- AgentState 包含 conversation_history: list[dict]
- 每次对话追加到 history：{"role": "user", "content": "...", "timestamp": "..."}
- 提供 /api/v1/sessions/{thread_id}/history 接口查询历史
- 实现会话超时机制：30分钟无活动自动清理
- 并发测试：同时运行 5 个不同 thread_id 的对话，验证无状态污染
- 整合 Week1 的 memory_manager，实现 token 预算压缩
```

- **验收**：5 个并发会话状态完全隔离；会话历史可查询；30 分钟超时后状态清理；token 超限时自动摘要。

---

## Day 5：容错降级 (超时熔断 / 指数退避 / 拒绝 fallback)

- **目标**：实现生产级容错机制，保证系统稳定性。
- **实操**：
  1. 实现 LLM 调用超时（使用 asyncio.timeout）
  2. 定义 `MaxRetriesReached` 异常
  3. 实现指数退避重试（2s -> 4s -> 8s -> 16s）
  4. 实现熔断器：连续 5 次失败后进入 OPEN 状态
  5. 定义 FallbackNode：熔断触发时返回降级响应
  6. 实现手动恢复机制
- **Prompt 模板**：

```md
为 LangGraph 添加容错降级机制。要求：
- LLM 调用使用 asyncio.timeout(30)，超时触发重试
- 实现指数退避：第 N 次重试等待 2^N 秒
- 定义 CircuitBreaker：连续 5 次失败后熔断
- 熔断时调用 FallbackNode，返回："抱歉，服务暂时繁忙，请稍后再试"
- 提供 /api/v1/agent/reset-circuit 接口手动恢复
- 每个 Agent 节点捕获异常并记录日志
- 附熔断状态可视化（OPEN/HALF_OPEN/CLOSED）
```

- **验收**：LLM 超时自动重试；指数退避正确；熔断后返回友好提示；恢复后可正常工作。

---

## Day 6：迁移 W1 Agent 至 LangGraph + 补充测试

- **目标**：将 Week1 的单 Agent 迁移到 LangGraph 状态机架构。
- **实操**：
  1. 将 `llm_client.py`, `tool_registry.py`, `memory_manager.py` 整合
  2. 定义 LangGraph Node：`analyze_node`, `tool_node`, `response_node`, `memory_node`
  3. 配置条件边实现工具调用循环
  4. 迁移健康检查端点
  5. 补充 LangGraph 相关单元测试
  6. 运行 `pytest --cov`，覆盖率 > 80%
- **Prompt 模板**：

```md
将 Week1 的单 Agent 迁移到 LangGraph 架构。要求：
- 整合 llm_client, tool_registry, memory_manager 为 LangGraph Agent
- 定义 Node：
  - analyze_node：解析用户输入，判断是否需要工具
  - tool_node：调用 tool_registry 执行工具
  - response_node：生成最终回复
  - memory_node：保存对话历史，检查 token 预算
- 使用 add_conditional_edges 实现循环：analyze -> tool (loop until no tool) -> response
- 迁移 /api/v1/health/ 端点，验证状态机正常工作
- 生成 pytest 测试，覆盖所有 Node 和边
- 确保 pytest --cov > 80%
```

- **验收**：原有 Agent 功能完整迁移；LangGraph DAG 清晰可追溯；pytest 覆盖率 > 80%；无循环依赖。

---

## Day 7：langgraph-cli 可视化轨迹图 + 并发测试

- **目标**：实现执行轨迹可视化，掌握并发压力测试方法。
- **实操**：
  1. 安装配置 `langgraph-cli`
  2. 使用 `get_state_history` 获取执行轨迹
  3. 生成 Mermaid 格式的轨迹图
  4. 编写并发测试脚本：100 并发请求
  5. 测试状态隔离和熔断在高并发下表现
  6. 生成测试报告
- **Prompt 模板**：

```md
实现 LangGraph 可视化和并发测试。要求：
- 使用 langgraph-cli 创建可视化界面
- 实现 /api/v1/agent/{thread_id}/history 接口，返回执行轨迹
- 轨迹格式：[{node: "analyze", state: {...}, timestamp: "..."}, ...]
- 生成 Mermaid 序列图展示执行流程
- 编写并发测试：使用 asyncio + aiohttp 发起 100 并发请求
- 验证：无状态污染、无死锁、熔断正常工作
- 生成 HTML 测试报告（包含响应时间、成功率、错误分布）
```

- **验收**：`langgraph-cli` 可启动并查看状态机；轨迹图清晰展示执行路径；100 并发无失败；测试报告完整。

---

## 每日验收标准

| Day | 验收条件 |
|-----|---------|
| D1 | LangGraph StateGraph 可执行，简单 DAG 状态流转正确 |
| D2 | Router 自动路由到正确工具，Reviewer 拒绝无效结果 |
| D3 | Command(resume) 中断和恢复成功，状态不丢失 |
| D4 | 5 并发会话状态隔离，会话历史可查询 |
| D5 | 超时重试、指数退避、熔断器正常工作 |
| D6 | Week1 Agent 完整迁移，pytest 覆盖率 > 80% |
| D7 | 轨迹可视化正常，100 并发测试通过 |

## 最终验收标准

- 低置信度自动触发人工审核
- 多会话并发无状态污染
- 执行 DAG 图清晰可追溯
- 熔断/降级机制生产级可用
- 所有节点类型测试覆盖 > 80%

## 高频 Prompt 模板（占位）

1. LangGraph 节点设计 Prompt
2. 条件边路由策略 Prompt
3. Human-in-the-Loop 审批 Prompt
4. 容错降级 Fallback Prompt
