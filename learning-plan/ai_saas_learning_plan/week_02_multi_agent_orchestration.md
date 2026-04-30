# Week 2: 多 Agent 编排与状态机架构

## 🎯 目标
从单 Agent 升级到 LangGraph 多智能体状态机，实现任务路由、人工介入与记忆隔离。

## 🛠️ 每日实操
- D1: LangGraph State Schema / Nodes / Edges 基础
- D2: 构建 Router → Executor → Reviewer 协作链
- D3: Human-in-the-Loop 中断点与审批恢复
- D4: 会话级记忆隔离 (独立 State 存储)
- D5: 容错降级 (超时熔断 / 指数退避 / 拒绝 fallback)
- D6: 迁移 W1 Agent 至 LangGraph + 补充测试
- D7: `langgraph-cli` 可视化轨迹图 + 并发测试

## ✅ 验收标准
- 低置信度自动触发人工审核
- 多会话并发无状态污染
- 执行 DAG 图清晰可追溯
