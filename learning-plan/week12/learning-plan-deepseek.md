# Week 12: 面试实战与系统设计演练

## 🎯 目标
完成架构白板演练与 Behavioral 问答，达到 JD 交付状态。覆盖核心技术复盘、系统设计实战（0-1 SaaS 架构 + 高并发 AI 服务）、Behavioral 与 AI-Native 问答、两轮模拟面试到简历优化与投递，最终具备从容应对资深工程师面试的能力。

---

## Day 1：核心技术复盘（FastAPI/Agent/RAG/vLLM）

- **目标**：系统性回顾 12 周核心技术栈，梳理知识体系与面试话术。
- **实操**：
  1. 整理技术清单：FastAPI 异步/SSE/WebSocket、LangChain/LangGraph Agent、RAG 检索增强、vLLM 推理加速、LoRA 微调、Taro 小程序。
  2. 为每项技术准备 3 分钟讲解：核心原理 + 实战经验 + 常见陷阱。
  3. 整理 STAR 案例库：每个项目对应 Situation/Task/Action/Result。
  4. 准备"为什么选择 X 而非 Y"的比较话术。
  5. 梳理常见追问链：技术选型 → 实现细节 → 性能优化 → 故障处理。
- **Prompt 模板**：

```md
整理核心技术复盘资料，要求：

1. 技术栈清单与话术（每项 3 分钟）：

   **FastAPI 异步架构**
   - 核心原理：asyncio 事件循环 + asyncpg/httpx 全链路异步
   - 实战经验：连接池管理（Depends + release）、SSE 流式推送、中间件链
   - 常见陷阱：同步调用阻塞事件循环

   **LangGraph Agent**
   - 核心原理：StateGraph + 条件路由 + Tool Calling
   - 实战经验：多 Agent 协作（Supervisor-Worker）、防死循环
   - 常见陷阱：Token 消耗过高、状态管理复杂度

   **vLLM 推理加速**
   - 核心原理：PagedAttention + KV Cache 管理 + Continuous Batching
   - 实战经验：KV Cache 参数网格调优、AWQ 量化
   - 常见陷阱：OOM、长文本延迟大

   **LoRA 微调**
   - 核心原理：低秩适配 + QLoRA 4-bit 量化 + Unsloth 加速
   - 实战经验：Alpaca 数据集构建、Perplexity/QA 评估
   - 常见陷阱：过拟合、Loss NaN

2. STAR 案例库（≥ 3 个）：
   - 案例：优化并发性能（300 → 500 VU，P95 < 2s）
   - 案例：领域模型热切换（延迟 < 100ms，准确率 +25%）

3. 技术对比话术：
   - vLLM vs Ollama / LangGraph vs LangChain / FastAPI vs Flask
```

- **验收**：
  - 核心技术 6 项，每项 3 分钟讲述流畅
  - STAR 案例 ≥ 3 个，逻辑完整
  - 技术对比话术准备到位

## Day 2：系统设计 #1（0-1 SaaS 架构/多租户/成本）

- **目标**：掌握 0-1 SaaS 架构设计，覆盖多租户、成本控制、扩展性。
- **实操**：
  1. 白板画出完整架构：CDN → Load Balancer → API Gateway → Microservices → DB/Cache/MQ。
  2. 多租户方案：Database-per-tenant vs Schema-per-tenant vs Row-level，讨论优缺点。
  3. 成本控制：Token 分级路由、缓存策略、模型 ROI 分析。
  4. 扩展性分析：水平扩展（K8s HPA）、DB 读写分离、Redis Cluster。
  5. 模拟面试：10 分钟内完成白板讲解。
- **Prompt 模板**：

```md
准备 0-1 SaaS 系统设计面试方案：

1. 架构图（白板 10 分钟）：
   [Client] → CDN → [Nginx LB] → [API Gateway] → [Chat/Agent/User Svc]
   → [PG/Redis/Celery/vLLM × 2]

2. 多租户对比：
   | 方案 | 隔离性 | 成本 | 复杂度 | 推荐场景 |
   DB-per-tenant: 最强/高/中/企业 < 100
   Row-level: 中/低/低/快速启动 ✅

3. 成本控制：
   - 简单问答 → GPT-4o-mini ($0.15/1M)
   - 复杂推理 → GPT-4o ($2.50/1M)
   - 缓存命中 → Redis ($0)
   - 单用户月度配额 $50

4. 扩展性：K8s HPA + PG 读写分离 + Redis Cluster + vLLM 多实例
```

- **验收**：
  - 白板 10 分钟完成架构讲解
  - 多租户方案对比清晰，选择理由充分
  - 成本/扩展性分析有量化数据

## Day 3：系统设计 #2（高并发 AI 服务/容灾/降级）

- **目标**：掌握高并发 AI 推理服务设计，覆盖容灾、降级、雪崩防控。
- **实操**：
  1. 高并发方案：异步 I/O + 连接池 + vLLM Continuous Batching + KV Cache。
  2. 容灾设计：主备 vLLM 实例 + 异地部署 + 流量切换。
  3. 降级链路：vLLM → Cache → LightModel → CloudAPI fallback（4 层）。
  4. 雪崩防控：限流（滑动窗口）+ 熔断（Circuit Breaker）+ 隔离（Bulkhead）。
  5. 模拟面试：10 分钟内讲解 + 画图。
- **Prompt 模板**：

```md
准备高并发 AI 服务系统设计：

1. 高并发架构：
   Client → RateLimiter → Router → [vLLM Pool]
                               ↓ (fallback)
                           [Cache → LightModel → CloudAPI]

2. 容灾设计：Zone A（主 2×A100）+ Zone B（备 1×A100 warm standby）+ DNS/Anycast

3. 降级链路（4 层）：vLLM 本地 → Redis 缓存 → 轻量模型 → 云端 API → 固定兜底

4. 雪崩防控：限流 100 req/s + 熔断 ErrorRate > 50% + 隔离（独立线程池）
```

- **验收**：
  - 高并发 + 容灾 + 降级方案完整
  - 降级链路 4 层分级，雪崩防控 4 手段

## Day 4：Behavioral & AI-Native 问答演练

- **目标**：准备 Behavioral 问答，聚焦 AI-Native 开发者特质与团队协作。
- **实操**：
  1. 准备 Behavioral 常见问题（STAR 框架）：冲突解决、挑战项目、优先级管理、持续学习。
  2. 准备 AI-Native 特色问题：AI 工作流、代码质量、不使用 AI 的场景。
  3. 准备反向提问：团队 AI 工具使用、自研 vs 采购决策。
  4. 录制自测：每个回答控制在 2-3 分钟。
- **Prompt 模板**：

```md
准备 Behavioral & AI-Native 面试问答：

1. Behavioral 问题（STAR）：
   Q: 最挑战的技术决策？
   A: 选择 vLLM vs Ollama → Benchmark 对比 → vLLM QPS 50 P95 1.2s → 500 VU P95 < 2s

   Q: 如何处理团队分歧？
   A: LoRA vs Full Fine-tuning 争议 → 对比实验 → 数据驱动决策

2. AI-Native 问答：
   Q: AI 开发工作流？
   A: 三层工作流（Cursor + AI Review + AI 测试生成），效率提升 60%

   Q: 何时不用 AI？
   A: 安全敏感代码/创新架构/复杂 Bug 调试

3. 反向提问：团队 AI ROI、Prompt 版本管理、降级策略、新人上手流程
```

- **验收**：
  - Behavioral 5 个问题准备完毕，每问 < 3 分钟
  - AI-Native 回答区分度清晰
  - 反向提问展示思考深度

## Day 5：模拟面试 #1（技术深度）

- **目标**：通过全真模拟面试，检验技术深度与表达能力。
- **实操**：
  1. 邀请朋友/同事担任面试官，或使用 AI 语音模拟。
  2. 面试结构（45min）：5min 自我介绍 → 20min 技术深度 → 10min 实时 Coding → 10min 讨论。
  3. 录制全程，回放分析：语速、停顿、逻辑跳跃、缺乏量化数据。
  4. 记录改进点，针对性练习。
- **Prompt 模板**：

```md
模拟技术深度面试（45min）：

1. 问题库（按难度）：
   ★★★: asyncio 事件循环阻塞原理 / PagedAttention KV Cache 管理 / 多 Agent 防死循环
   ★★: SSE 流式心跳重连 / LoRA vs Full Fine-tuning / 分布式限流
   ★: async/await 用法 / RAG 流程 / WebSocket vs SSE

2. Coding 题（10min）：实现 Redis ZSET 滑动窗口限流器

3. 自我评估：技术深度/量化数据/逻辑结构/失误处理
```

- **验收**：
  - 模拟面试完成，录制回放分析
  - 识别 ≥ 3 个改进点
  - Coding 题 10 分钟内完成

## Day 6：模拟面试 #2（白板架构/故障排查）

- **目标**：通过第二轮模拟面试，聚焦系统设计与故障排查能力。
- **实操**：
  1. 面试结构（45min）：5min 自我介绍 → 20min 系统设计 → 10min 故障排查 → 10min 讨论。
  2. 系统设计题："设计一个高并发 AI Chat API"（Requirement → High-Level → Deep Dive → Edge Cases）。
  3. 故障排查题："用户反馈延迟突然飙升，如何定位？"（结构化诊断流程）。
  4. 评分解读：Level、Signal、Gap Analysis。
- **Prompt 模板**：

```md
模拟系统设计与故障排查面试：

1. 系统设计：Design a high-concurrency AI Chat API
   - 需求澄清：500 concurrent / SSE / model switching / P95 < 2s
   - 高层设计：Client → CDN → LB → API Gateway → Agent Router → vLLM Pool
   - 深层探讨：Async I/O / Streaming / Rate Limiting / Fallback
   - 边界条件：OOM / Network partition / Abuse

2. 故障排查：P95 延迟突然飙升
   诊断流程：Grafana 定位 → 排除 Network/DB/Cache → 定位 Inference → Connection pool exhausted → 修复 + 监控

3. 评分：需求澄清 / 架构清晰度 / 权衡分析 / 沟通互动
```

- **验收**：
  - 架构图 10 分钟白板画出，组件关系清晰
  - 故障排查思路结构化，逐层定位
  - 评分 ≥ 85/100

## Day 7：简历对齐 / 话术优化 / 投递清单确认

- **目标**：完成简历终稿，优化自我介绍话术，确认投递目标清单。
- **实操**：
  1. 简历终审：项目经验对齐 JD、量化成果突出、关键词匹配。
  2. 自我介绍话术打磨（1 分钟电梯演讲）：开场 → 亮眼成果 → 求职动机。
  3. 投递清单确认：目标公司（5-10 家）+ 优先级排序 + 投递渠道 + 跟进策略。
  4. 准备 Cover Letter 模板：定制化 30 秒可修改。
  5. 心态调整与终局 Checklist。
- **Prompt 模板**：

```md
完成简历终审与投递准备：

1. 简历优化重点（量化驱动）：
   ✅ "将 AI Chat API 并发从 300 VU 提升至 500 VU，P95 延迟从 3s 降至 2s" → "Reduced P95 latency 40% at 500 concurrent users"
   ✅ "主导从 0 搭建多 Agent 协作架构，任务完成率提升至 92%" → "Built multi-Agent architecture (LangGraph), task completion rate: 65% → 92%"
   ❌ "负责后端开发" / ❌ "参与了 AI 项目"

2. 1 分钟自我介绍：
   "我是 XXX，3 年全栈/AI 开发经验。最近主导了一个 AI-Native SaaS 项目——
   从 FastAPI 异步架构到 LangGraph 多 Agent 系统，再到 vLLM 推理部署。
   亮点包括：500 VU 高并发优化（P95 降低 40%）、微调模型热切换（准确率 +25%）、
   CI/CD 持续交付流水线。我正在寻找能发挥 AI-Native 开发能力的团队，
   这个岗位的 [X] 方向与我的项目经验高度匹配。"

3. 投递清单模板：
   | 公司 | 优先级 | 渠道 | 状态 |
   |------|--------|------|------|
   | 公司 A | P0 | 内推 | 待投 |
   | 公司 B | P0 | LinkedIn | 待投 |
   | 公司 C | P1 | Boss 直聘 | 待投 |

4. Cover Letter 模板：
   "Hi [Name], I came across [Position] at [Company]. With [X years] experience
   in [keywords], I've recently built [project highlight]. I'm particularly drawn
   to [Company] because [reason]. Would love to chat about how I can contribute."

5. 终局 Checklist：
   - [ ] 简历中英双版，PDF format
   - [ ] LinkedIn/GitHub/Blog 资料一致且活跃
   - [ ] Portfolio 页面 + Demo 视频已上线
   - [ ] 投递清单 5-10 家公司，优先级排序
   - [ ] 模拟面试 × 2 已完成，改进点已修正
   - [ ] 心态：12 周实战积累 = 真实竞争力
```

- **验收**：
  - 简历终稿完成，量化成果突出
  - 自我介绍 < 1 分钟，流畅自然
  - 投递清单 5-10 家，优先级清晰
  - 心态自信，准备好迎接面试

---

## 每日验收标准

| Day | 验收条件 |
|-----|---------|
| D1 | 6 项技术复盘 > 3min/项；STAR 案例 ≥ 3 个；技术对比话术到位 |
| D2 | 白板 10min 架构图；多租户对比清晰；成本/扩展性量化 |
| D3 | 高并发/容灾/降级完整；雪崩防控 4 手段；追问应对有数据 |
| D4 | Behavioral 5 问 ≤ 3min/问；AI-Native 区分度清晰；反向提问到位 |
| D5 | 模拟面试完成；> 3 个改进点；Coding 题 ≤ 10min |
| D6 | 架构图清晰；故障排查结构化；评分 ≥ 85/100 |
| D7 | 简历量化优化；自我介绍 ≤ 1min；投递清单 5-10 家 |

## 最终验收标准

- 核心 6 项技术复盘完成，每项可流利讲解 3 分钟
- 两次模拟面试完成，技术深度 + 系统设计双维度评分 ≥ 85/100
- 简历量化优化终稿 + 1 分钟自我介绍打磨完毕
- 投递清单确认（5-10 家），优先级清晰

## 高频 Prompt 模板

1. **核心技术复盘 Prompt**
   - 6 项技术 3 分钟讲解（原理 + 实战 + 陷阱）
   - STAR 案例库（Situation/Task/Action/Result）
   - 技术对比话术（vLLM vs Ollama 等）

2. **0-1 SaaS 系统设计 Prompt**
   - 白板架构图（CDN → LB → API GW → Svc → DB/Cache）
   - 多租户方案对比（DB/Schema/Row-level）
   - 成本控制 + 扩展性分析

3. **高并发 AI 服务设计 Prompt**
   - 异步 I/O + vLLM Pool + Continuous Batching
   - 容灾（主备 + 异地 + 流量切换）
   - 4 层降级 + 雪崩防控 4 手段

4. **Behavioral & AI-Native 问答 Prompt**
   - STAR 框架 Behavioral 5 问
   - AI-Native 特色问答（工作流/质量/边界）
   - 反向提问策略

5. **模拟技术面试 Prompt**
   - 三级难度问题库（★/★★/★★★）
   - 10min Coding 题（滑动窗口限流）
   - 自我评估维度

6. **系统设计与故障排查 Prompt**
   - 设计题：Requirement → HL → Deep Dive → Edge Cases
   - 故障排查：Grafana → 排除法 → 根因 → 修复
   - 评分维度

7. **简历投递准备 Prompt**
   - 量化简历优化（数字驱动）
   - 1 分钟电梯演讲
   - 投递清单 + Cover Letter + 终局 Checklist

## 动态调整建议

- **应届生/转行**：Day 1 技术复盘放慢，先补齐基础概念；Day 2-3 系统设计可简化为单机架构。
- **有经验但无 AI 背景**：Day 1 重点 vLLM/Agent/LoRA 三项，FastAPI 快速过。
- **已有 Offer 在流程中**：Day 5-6 模拟面试按目标公司个性化命题（如目标公司用 Go → 增加 Go 并发讨论）。
- **面试紧张**：Day 5-6 面试前深呼吸练习，准备好"不知道就说不知道"的诚实策略。
- **时间紧张**：Day 2-3 系统设计合并为 1 天，Day 4 Behavioral 压缩至半天。

## 第 7 天自测清单

- [ ] 6 项核心技术复盘完成，每项可流利讲解
- [ ] STAR 案例 ≥ 3 个，技术对比话术准备到位
- [ ] 系统设计 × 2（SaaS 架构 + 高并发 AI）白板可 10 分钟讲完
- [ ] Behavioral 5 问 + AI-Native 3 问准备完毕
- [ ] 模拟面试 × 2 完成，评分 ≥ 85/100
- [ ] 简历量化优化终稿，自我介绍 ≤ 1 分钟
- [ ] 投递清单确认（5-10 家），Cover Letter 模板就绪
- [ ] 能清晰口述所有核心技术原理、系统设计方案与项目实战成果
