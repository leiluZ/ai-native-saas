# Week 4: 私有化部署与推理加速

## 🎯 目标
掌握 vLLM 生产部署、量化加速与云/端智能路由，构建高吞吐、低延迟、可观测的私有化大模型推理服务。

---

## Day 1：Ollama vs vLLM 基准测试

- **目标**：掌握主流推理引擎性能评估方法，搭建自动化 Benchmark 脚本，量化吞吐/延迟/显存差异。
- **实操**：
  1. 部署 `vLLM` (0.7+) 与 `Ollama`，拉取同一基座模型（如 Qwen2.5-7B-Instruct）。
  2. 构造测试集：固定长度（128/512/2048 tokens）Prompt 各 100 条，覆盖长文本生成场景。
  3. 编写异步压测脚本：并发请求数可调，记录 TTFT（首字延迟）、TPOT（字间延迟）、Throughput（tokens/s）、峰值显存。
  4. 输出对比报告（CSV + Matplotlib 折线/柱状图），分析引擎架构差异对性能的影响。
- **Prompt 模板**：

```md
编写生产级推理引擎 Benchmark 脚本，要求：
1. 使用 asyncio + aiohttp 并发请求，支持可配置 concurrency & total_requests
2. 精确计算 TTFT、TPOT、End-to-End Latency、Peak GPU VRAM
3. 自动适配 vLLM (OpenAI 兼容接口) 与 Ollama (本地 API) 双端点
4. 结果导出为 CSV，附性能对比可视化脚本（P50/P95/P99 延迟、吞吐曲线）
5. 内置重试与超时控制，失败请求不干扰整体统计
```

- **验收**：压测脚本一键运行；输出结构化 CSV 与对比图表；覆盖短/中/长上下文场景；指标统计无偏差。

---

## Day 2：AWQ/GPTQ/INT8 量化转换流程

- **目标**：掌握主流后训练量化（PTQ）算法，实现模型无损/低损量化与精度验证。
- **实操**：
  1. 使用 `llm-awq`、`AutoGPTQ`、`bitsandbytes` 分别对基座模型进行 4bit/8bit 量化。
  2. 准备校准数据集（WikiText-2/Alpaca 子集），执行量化权重校准。
  3. 验证量化后模型：计算 Perplexity，对比生成质量（ROUGE/BLEU 人工抽检），测试推理延迟。
  4. 封装量化流水线脚本，支持断点续传与量化格式互转验证。
- **Prompt 模板**：

```md
构建模型量化转换与验证流水线，要求：
1. 支持 AWQ/GPTQ/INT8 三种策略，通过 config.yaml 热切换
2. 校准数据集自动下载/加载，支持自定义 sample 数量
3. 量化后自动加载至 vLLM，输出 Perplexity 对比与 TTFT/吞吐指标
4. 包含质量回归测试：相同 Prompt 生成 10 次，计算相似度/一致性
5. 失败自动回滚至 FP16 权重，日志记录量化耗时与显存快照
```

- **验收**：量化流程自动化；显存占用下降 >50%；吞吐提升 >2x；Perplexity 增幅 <5%；质量抽检无严重退化。

---

## Day 3：OpenAI 兼容网关

- **目标**：构建统一 API 网关，实现多模型路由、流式转发、Function Calling 兼容与协议标准化。
- **实操**：
  1. 基于 FastAPI + `litellm` 或自研代理，实现 `/v1/chat/completions` 等核心端点。
  2. 完整兼容 OpenAI SDK：支持 `stream=True`、`tools` 定义、`response_format`。
  3. 实现请求拦截：鉴权、Rate Limit、动态模型路由、超时重试。
  4. 封装流式 Chunk 转发逻辑，确保前端 SSE 稳定不断连。
- **Prompt 模板**：

```md
实现 OpenAI 兼容 API 网关，要求：
1. FastAPI 路由完整映射 chat/completions、models、embeddings
2. 严格遵循 OpenAI 流式协议：SSE 格式 chunk 转发，心跳保活
3. 支持 Function Calling：自动透传 tools 定义，解析 vLLM 返回的 tool_calls
4. 集成 API Key 校验、IP 限流、全局超时与指数退避重试
5. 请求/响应中间件记录 Tracing ID，便于全链路追踪
```

- **验收**：vLLM 完整支持流式 & Function Calling；OpenAI 官方 SDK 零改造直连；网关额外延迟 <50ms；SSE 流稳定不断连。

---

## Day 4：KV Cache & PagedAttention 参数调优

- **目标**：深入理解 vLLM 内存管理机制，通过 KV Cache 参数调优最大化并发与吞吐。
- **实操**：
  1. 研究 PagedAttention 原理：`block_size`、`gpu_memory_utilization`、`max_num_seqs`、`max_model_len`。
  2. 设计参数网格，使用 `vllm` 内置 CLI 或 Python API 批量启动不同配置。
  3. 压测各配置下的 Cache Hit Rate、Block Allocation、OOM 边界、请求排队时间。
  4. 结合 `enable_chunked_prefill` 与 `max_num_batched_tokens` 优化 Prefill 阶段吞吐。
- **Prompt 模板**：

```md
编写 vLLM KV Cache 参数自动寻优脚本，要求：
1. 网格搜索：gpu_memory_utilization [0.8, 0.85, 0.9], block_size [16, 32], max_num_seqs [32, 64, 128]
2. 每组配置自动启动 vLLM，运行 3 轮压测，记录 OOM 次数、平均队列深度、吞吐/延迟
3. 动态调整 enable_chunked_prefill 与 max_num_batched_tokens 缓解长序列 Prefill 阻塞
4. 输出最优配置组合与性能收益对比图，附 vLLM 启动命令模板
5. 内置安全阈值：显存占用 >92% 或 P99 延迟 >2s 自动终止该组测试
```

- **验收**：找到最优 KV Cache 配置；并发承载量提升 >30%；零 OOM；Cache 利用率 >85%；参数调优脚本可复用。

---

## Day 5：智能路由策略 (本地优先 -> 云端 fallback)

- **目标**：实现云边协同推理路由，保障高可用、成本优化与无缝降级。
- **实操**：
  1. 构建路由决策层：本地 vLLM 为主，云端 API（如 OpenAI/百炼）为备。
  2. 实现健康探针：定期 Ping 本地端点，监控 GPU 利用率、队列长度、错误率。
  3. 配置降级策略：超时 >800ms、连续 3 次 5xx、或显存满载时自动切换云端。
  4. 实现路由透明化：客户端无感知切换，支持上下文续传与流式聚合。
- **Prompt 模板**：

```md
实现智能路由代理层，要求：
1. 主备路由：优先请求本地 vLLM，触发降级条件无缝切换云端
2. 健康检查：每 5s 探测本地端点，记录成功率/延迟/队列深度
3. 降级触发器：P99 > 800ms、5xx 连续 ≥3、GPU 显存 >95% 自动 fallback
4. 流式聚合：fallback 后继续输出剩余 chunk，前端无断流感知
5. 全量日志：记录每次路由决策、切换原因、耗时，支持 Prometheus 暴露
```

- **验收**：路由切换失败率 <1%；降级触发准确；客户端 SSE 流不断；决策日志完整可审计。

---

## Day 6：AI 辅助 Profiling 定位瓶颈

- **目标**：掌握系统级与框架级 Profiling 工具，定位推理链路性能瓶颈并针对性优化。
- **实操**：
  1. 集成 `torch.profiler`、`nsys` (NVIDIA Nsight)、`py-spy` 进行多维度采样。
  2. 分析 GPU Kernel 耗时、CPU 调度、序列化/反序列化、网络 I/O、Tokenization 瓶颈。
  3. 生成火焰图（Flame Graph）与时间线，定位 Prefill vs Decode 阶段热点。
  4. 应用优化：算子融合、异步 I/O、预编译 Tokenizer、调整 Batch Size。
- **Prompt 模板**：

```md
构建自动化 Profiling 与瓶颈分析流水线，要求：
1. 集成 torch.profiler 与 nsys，自动收集 GPU/CPU 时间线数据
2. 输出火焰图与阶段耗时分布：Prefill、Decode、KV Cache 分配、网络 IO
3. 自动识别 Top 3 瓶颈（如 CPU 序列化阻塞、Kernel 启动延迟、Batch 不均）
4. 生成优化建议报告：对应代码修改点、预期收益、验证命令
5. 脚本支持一键启停，数据自动归档至 profiling_results/ 目录
```

- **验收**：输出完整 Profiling 报告；定位并修复 1~2 个核心瓶颈；P99 延迟较优化前下降 >20%；分析流程自动化。

---

## Day 7：容器化部署 + Prometheus Metrics 暴露

- **目标**：实现生产级容器化交付，构建可观测性监控与告警体系。
- **实操**：
  1. 编写多阶段 Dockerfile，优化镜像体积，配置非 root 用户与健康检查。
  2. 启动 `vLLM --enable-metrics` 暴露 `/metrics` 端点，集成 `prometheus.yml`。
  3. 导入 Grafana 官方 vLLM Dashboard，配置关键面板：GPU Util、Queue Depth、TTFT/TPOT、Error Rate。
  4. 编写 Alertmanager 规则：显存满载、路由连续失败、吞吐量骤降时触发告警。
- **Prompt 模板**：

```md
编写生产级容器化部署与可观测性配置，要求：
1. 多阶段 Dockerfile：仅保留推理运行时依赖，镜像 < 4GB，健康检查 /health
2. docker-compose.yml 编排 vLLM + Prometheus + Grafana + Node Exporter
3. 自动注入 vLLM 启动参数，暴露 8000 (API) 与 8001 (Metrics)
4. Grafana 导入预置 JSON Dashboard，展示吞吐/延迟/缓存命中率/错误率
5. Alertmanager 规则：队列积压 >50 或 连续 2min 无响应时触发企业微信/Slack 告警
```

- **验收**：`docker-compose up` 一键拉起全栈；Prometheus 抓取正常；Grafana 面板实时刷新；模拟故障触发告警；资源占用符合预期。

---

## 每日验收标准

| Day | 验收条件 |
|-----|---------|
| D1 | Benchmark 脚本一键运行；输出结构化 CSV 与对比图表；覆盖短/中/长上下文场景 |
| D2 | 显存占用下降 >50%；吞吐提升 >2x；Perplexity 增幅 <5%；质量抽检无严重退化 |
| D3 | vLLM 完整支持流式 & Function Calling；OpenAI SDK 零改造直连；SSE 流稳定不断连 |
| D4 | 找到最优 KV Cache 配置；并发承载量提升 >30%；零 OOM；Cache 利用率 >85% |
| D5 | 路由切换失败率 <1%；降级触发准确；客户端 SSE 流不断；决策日志完整可审计 |
| D6 | 输出完整 Profiling 报告；定位并修复核心瓶颈；P99 延迟下降 >20% |
| D7 | `docker-compose up` 一键拉起全栈；Prometheus/Grafana 实时刷新；模拟故障触发告警 |

## 最终验收标准
- vLLM 完整支持流式输出 & Function Calling，OpenAI 兼容网关零改造接入
- 量化后显存降 >50%，吞吐升 >2x，Perplexity 增幅 <5%
- 智能路由切换失败率 <1%，降级过程客户端无感知
- KV Cache 参数调优使并发承载量提升 >30%，零 OOM
- Profiling 定位瓶颈并优化，P99 延迟下降 >20%
- 容器化部署一键启动，Prometheus + Grafana 可观测体系完整运行

## 高频 Prompt 模板（占位）
1. 推理引擎 Benchmark 自动化脚本 Prompt
2. AWQ/GPTQ/INT8 量化转换与精度验证 Prompt
3. OpenAI 兼容网关与流式转发代理 Prompt
4. vLLM KV Cache 参数网格寻优 Prompt
5. 本地-云端智能路由与降级策略 Prompt
6. AI 辅助 Profiling 瓶颈定位与优化 Prompt
7. 容器化部署 + Prometheus/Grafana 监控集成 Prompt

## 动态调整建议
- **GPU 资源受限**：Day 2 优先使用 `bitsandbytes` INT8 量化，显存占用更低；Day 4 降低 `max_num_seqs` 避免 OOM。
- **无生产部署经验**：Day 3 先使用 `LiteLLM` 现成网关跑通协议兼容，再逐步替换为自研 FastAPI 代理。
- **无监控经验**：Day 7 优先跑通 `vLLM --enable-metrics` + 单节点 Prometheus，Grafana 导入官方模板即可快速可视化。
- **算法背景弱**：Day 4/6 聚焦参数调优与 Profiling 报告解读，无需深入 CUDA Kernel 实现，掌握“调参-压测-对比”闭环即可。

## 第 7 天自测清单
- [ ] `docker-compose up` 成功拉起 vLLM + 网关 + Prometheus + Grafana
- [ ] `curl` 模拟流式请求与 Function Calling，返回符合 OpenAI 规范
- [ ] 量化模型加载成功，显存占用降 >50%，吞吐升 >2x
- [ ] 压测脚本触发降级阈值，路由切换失败率 <1%
- [ ] Grafana 面板实时显示 TTFT/TPOT、Queue Depth、GPU Util、Error Rate
- [ ] 模拟本地服务宕机，Alertmanager 30s 内触发告警通知
- [ ] 仓库包含 `docker-compose.yml`、`prometheus.yml`、Grafana JSON、Benchmark/Profiling 脚本与运行文档
