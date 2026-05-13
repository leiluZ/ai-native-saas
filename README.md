# AI Native SaaS - 12周全栈 AI 应用开发实战

> 本项目是一个**分阶段构建的 AI Native SaaS 全栈应用**，从基础的 Chat Agent 到生产级 RAG 管道，逐步掌握现代 AI 应用开发的核心技术栈。

---

## 12周学习路线图

| 周次 | 核心主题 | 技术栈 | 状态 |
|:---:|:---|:---|:---:|
| [W1](ai-saas-week1/) | AI-Native 环境 & SaaS 骨架 | Cursor, FastAPI, React, LangChain | ✅ |
| [W2](ai-saas-week2/) | 多 Agent 编排与状态机 | LangGraph, Human-in-the-Loop | ✅ |
| [W3](ai-saas-week3/) | RAG 管道与检索评估 | BGE-M3, Milvus, 智能分块 | ✅ |
| [W4](ai-saas-week4/) | 私有化部署与推理加速 | vLLM, Ollama, AWQ/GPTQ | ✅ |
| W5 | 领域微调与 LoRA 实战 | Unsloth, PEFT, QLoRA | 📋 |
| W6 | 小程序端接入与 UI/UX | Taro/Uniapp, 跨端同步 | 📋 |
| W7 | 高并发与流式优化 | WebSockets, Celery, k6 | 📋 |
| W8 | 长上下文与安全工程 | Context Compression, OWASP LLM | 📋 |
| W9 | CI/CD 与生产监控 | GitHub Actions, Prometheus | 📋 |
| W10 | AI-Native 工作流标准化 | Prompt 版本库, 成本追踪 | 📋 |
| W11 | 作品集打磨与开源贡献 | GitHub 优化, Tech Blog | 📋 |
| W12 | 面试实战与系统设计 | 白板架构、故障排查 | 📋 |

> **图例**: ✅ 已完成 | 📋 计划中

---

## 每周详细内容

### [Week 1: AI-Native 环境初始化 & 基础 SaaS 骨架](ai-saas-week1/)

**学习目标**: 建立 AI 驱动的开发环境，掌握「自然语言 -> 架构 -> 代码」闭环。

**核心功能**:
- FastAPI + SQLAlchemy 2.0 + Alembic 异步后端架构
- LangChain Agent + Function Calling + 工具路由
- React + Vite + Tailwind + Zustand 前端骨架
- 记忆管理 (PostgreSQL/Redis) + 上下文压缩
- Docker Compose 一键部署

**关键交付物**:
- 异步 API + 基础 Agent
- 工具注册系统（天气、时间、计算器）
- 完整 Docker 化部署

---

### [Week 2: 多 Agent 编排与状态机架构](ai-saas-week2/)

**学习目标**: 从单 Agent 升级到 LangGraph 多智能体状态机，实现任务路由、人工介入与记忆隔离。

**核心功能**:
- LangGraph State Schema / Nodes / Edges 基础架构
- Router → Executor → Reviewer 多 Agent 协作链
- Human-in-the-Loop 中断点与审批恢复
- 会话级记忆隔离（独立 State 存储）
- 容错降级（超时熔断 / 指数退避 / 拒绝 fallback）

**关键交付物**:
- 可路由/可中断的多 Agent 系统
- 低置信度自动触发人工审核
- 执行 DAG 图可视化

---

### [Week 3: RAG 管道构建与检索评估](ai-saas-week3/)

**学习目标**: 构建生产级 RAG，掌握文档解析、智能分块、混合检索、重排与自动化评估闭环。

**核心功能**:
- 文档解析 (PDF/DOCX/TXT/HTML) + 清洗 + 编码检测
- 智能分块（固定长度/递归/标题感知）+ Token 重叠去重
- BGE-M3 Embedding + ONNX 推理加速 + CPU/GPU 自动降级
- Milvus 向量索引（HNSW/IVF_FLAT）+ 批量插入 + 指数退避
- 检索接口（metadata 过滤 + top_k + 距离阈值）

**关键交付物**:
- 企业级知识库 RAG 管道
- 10k 分块入库 < 2min，查询延迟 < 100ms
- 文档解析成功率 >95%

---

### [Week 4: 私有化部署与推理加速](ai-saas-week4/)

**学习目标**: 掌握 vLLM 生产部署、量化加速与云/端智能路由，构建完整的推理引擎 Benchmark 与量化流水线。

**核心功能**:
- vLLM vs Ollama 高性能并发压测 (吞吐/TTFT/TPOT 指标)
- AWQ/GPTQ/INT8 三种量化策略配置驱动切换
- 自动校准数据集下载 (WikiText-103-v1)
- Perplexity 计算与质量回归测试 (重复生成相似度对比)
- 量化失败自动回滚机制
- vLLM 量化模型加载集成 (`--quantized` 参数)

**关键交付物**:
- Benchmark 脚本支持短/中/长 Prompt 场景
- 量化流水线一键运行，配置热切换
- 显存节省 >50%，吞吐提升 >2x
- Perplexity 增幅 <5%，质量无严重退化

---

### Week 5: 领域微调与 LoRA 实战 (计划中)

**学习目标**: 掌握 LoRA/QLoRA 全流程，实现领域增强与热切换。

**核心内容**:
- Alpaca 格式数据集构建与清洗
- Unsloth + QLoRA (4-bit) + FlashAttention
- 训练循环 (LR 调度 / Gradient Checkpoint)
- Perplexity & 领域 QA 对比评估
- 权重合并 + GGUF/FP16 转换

---

### Week 6: 小程序端接入与 UI/UX (计划中)

**学习目标**: 完成微信小程序接入，实现跨端同步与高还原度 UI。

**核心内容**:
- Taro/Uniapp 初始化 + 多端构建
- Pinia/Zustand 持久化 + 本地缓存策略
- 微信授权/分享/订阅消息 API 接入
- 组件库定制 + 暗色/动态主题
- AI 辅助 Figma -> Tailwind 组件生成

---

### Week 7: 高并发与流式架构优化 (计划中)

**学习目标**: 优化高并发流式架构，实现连接池、降级策略与压测验证。

**核心内容**:
- FastAPI 异步深度优化 (asyncpg/redis 连接池)
- SSE/WebSocket 生产化 (心跳/重连/保序)
- Celery/RQ 解耦长耗时任务
- Redis 滑动窗口限流 + IP 封禁
- k6/Locust 压测 (500 VU) + 瓶颈定位

---

### Week 8: 长上下文管理与安全工程 (计划中)

**学习目标**: 攻克长上下文瓶颈，构建防注入、脱敏、审计管道。

**核心内容**:
- Token 爆炸 / 注意力稀释 / KV Cache 瓶颈分析
- 上下文压缩 (滑动窗口 + 摘要链)
- OWASP LLM Top 10 防御 (Prompt 注入/越权)
- PII 脱敏 (正则/NLP) + 审计日志
- 红队测试 (10 种 Jailbreak 用例)

---

### Week 9: CI/CD 流水线与生产监控 (计划中)

**学习目标**: 搭建自动化 CI/CD 与可观测性体系。

**核心内容**:
- GitHub Actions (Lint->Test->Build->Deploy)
- Docker 多阶段构建 + Trivy 扫描
- Prometheus + Grafana + Loki 监控栈
- 结构化 JSON 日志 + TraceID 透传
- 蓝绿部署/滚动更新 + 零停机回滚

---

### Week 10: AI-Native 工作流标准化 (计划中)

**学习目标**: 沉淀团队级 Prompt 工程库与自动化审查流程。

**核心内容**:
- Context Engineering 进阶 (分层提示/防幻觉)
- 自动化 PR Review (Cursor/Cline 审查模板)
- Prompt 版本库 (分类/A/B 测试)
- Token 成本追踪与模型路由核算
- AI Coding ROI 基准测试

---

### Week 11: 作品集打磨与开源贡献 (计划中)

**学习目标**: 提升 GitHub 活跃度与技术影响力。

**核心内容**:
- 仓库审计 (结构/License/敏感信息清理)
- README 重构 (Mermaid 架构/快速启动/AI 声明)
- 技术博客撰写与发布
- 开源 PR 提交 (LangChain/vLLM 等)
- 3 分钟 Demo 视频录制

---

### Week 12: 面试实战与系统设计演练 (计划中)

**学习目标**: 完成架构白板演练与 Behavioral 问答，达到 JD 交付状态。

**核心内容**:
- 核心技术复盘 (FastAPI/Agent/RAG/vLLM)
- 系统设计 #1 (0-1 SaaS 架构/多租户/成本)
- 系统设计 #2 (高并发 AI 服务/容灾/降级)
- Behavioral & AI-Native 问答演练
- 模拟面试 (技术深度 + 白板架构)

---

## 技术栈

| 层级 | 技术 |
|------|------|
| **前端** | React 19, TypeScript, Vite, Tailwind CSS, Zustand, Playwright |
| **后端** | Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2 |
| **AI/LLM** | LangChain, LangGraph, Ollama, OpenAI API |
| **推理** | vLLM (PagedAttention), AWQ/GPTQ/INT8 量化, Perplexity 验证 |
| **数据** | PostgreSQL 16, Redis 7, Milvus (向量数据库) |
| **RAG** | BGE-M3 Embedding, HNSW/IVF_FLAT 索引, 智能分块 |
| **部署** | Docker, Docker Compose, GitHub Actions CI/CD |

---

## 快速开始

```bash
# 选择当前周目录（以 Week 3 为例）
cd ai-saas-week3

# 配置环境变量
cp .env.example .env

# 启动所有服务
docker compose up -d

# 查看服务状态
docker compose ps
```

### 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| Web UI | 3000 | React 前端 |
| API | 8000 | FastAPI 后端 |
| PostgreSQL | 5432 | 关系数据库 |
| Redis | 6379 | 缓存与会话存储 |
| Ollama | 11434 | 本地 LLM 服务 |
| Milvus | 19530 | 向量数据库 (Week3+) |

---

## 项目结构

```
ai-native-saas/
├── ai-saas-week1/          # Week 1: 基础 Chat Agent
├── ai-saas-week2/          # Week 2: LangGraph 多 Agent
├── ai-saas-week3/          # Week 3: RAG 管道
├── ai-saas-week4/          # Week 4: 私有化部署 & 量化加速
├── ...
├── learning-plan/          # 学习计划文档
│   ├── ai_saas_learning_plan/    # 12周全栈路线图
│   ├── week1/
│   ├── week2/
│   ├── week3/
│   └── week4/
├── .github/workflows/      # CI/CD 配置
└── README.md               # 本文件
```

---

## 学习资源

- [12周全景路线图](learning-plan/ai_saas_learning_plan/overall_learning_plan.md)
- [Week 1 详细计划](learning-plan/week1/learning-plan-original.md)
- [Week 2 详细计划](learning-plan/week2/learning-plan-original.md)
- [Week 3 详细计划](learning-plan/week3/learning-plan-original.md)
- [Week 4 详细计划](learning-plan/week4/learning-plan-original.md)

---

## 贡献指南

1. 每周基于上周 `main` 分支迭代
2. 最终仓库即为完整生产级项目
3. PR 需通过 CI 检查（Lint + Test）

## 许可证

[MIT](LICENSE)
