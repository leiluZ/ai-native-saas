# AI-Native SaaS Week 4 学习计划（原版整理）

## Day 1：vLLM 基础部署 & 性能基准测试

- **目标**：搭建 vLLM 生产环境，建立性能基准线，理解吞吐/延迟/显存关系。
- **实操**：
  1. 对比 Ollama vs vLLM：安装、启动、API 兼容性。
  2. 使用 Llama 3.1 8B / Mistral 7B 模型进行基准测试。
  3. 测量指标：tokens/s（吞吐）、TTFT（首字延迟）、显存占用。
  4. 记录不同 batch size、max_seq_len 下的性能变化。
- **Prompt 模板**：

```md
生成 vLLM 部署与基准测试脚本，要求：
- 使用 OpenAI 兼容 API（/v1/chat/completions）
- 支持 SSE 流式输出（Server-Sent Events）
- 测试场景：单用户、并发 10、并发 50
- 输出 JSON 报告：{model, throughput, latency, vram_usage, error_rate}
- 包含 Docker Compose 配置（vllm + ollama 并行）
```

- **验收**：vLLM 服务可访问；能生成性能对比报告；流式输出正常。

---

## Day 2：模型量化（AWQ/GPTQ/INT8）实践

- **目标**：掌握量化流程，实现显存降 >50%，吞吐提升 >2x。
- **实操**：
  1. 安装 `autoawq`、`gptq`、`llama.cpp` 量化工具。
  2. 对 Llama 3.1 8B 进行 AWQ 4-bit 量化。
  3. 对比量化前后：显存占用、推理速度、精度损失（perplexity）。
  4. 测试 INT8 vs FP16 vs FP32 性能差异。
- **Prompt 模板**：

```md
编写模型量化流水线，要求：
- 支持多种量化格式：AWQ、GPTQ、INT8、FP4
- 自动选择最优量化策略（基于模型大小/硬件）
- 量化后自动导出 GGUF / SafeTensors 格式
- 提供量化前后对比表：{size, vram, speed, perplexity}
- 集成到 vLLM 部署流程（--quantized 参数）
```

- **验收**：量化后显存降 >50%；吞吐升 >2x；perplexity 增长 <10%。

---

## Day 3：OpenAI 兼容网关开发

- **目标**：构建统一推理网关，屏蔽底层差异，支持多模型切换。
- **实操**：
  1. 设计网关架构：LiteLLM 集成 vs 自研代理。
  2. 实现 `/v1/models` 列表、`/v1/chat/completions` 统一接口。
  3. 支持模型路由：按负载、按用户、按成本策略。
  4. 实现 fallback 机制：本地失败 -> 云端（OpenAI/Claude）。
- **Prompt 模板**：

```md
开发 OpenAI 兼容推理网关，要求：
- 路由策略：优先本地 vLLM，超时/失败切换云端
- 支持流式与非流式（stream=true/false）
- 模型注册表：{name, provider, endpoint, api_key, priority}
- 健康检查：定期探测模型可用性，自动降级
- 日志记录：每次路由决策、延迟、错误原因
```

- **验收**：网关可切换模型；fallback 失败率 <1%；流式输出无中断。

---

## Day 4：KV Cache & PagedAttention 参数调优

- **目标**：优化 vLLM 参数，降低显存占用，提升长文本推理性能。
- **实操**：
  1. 理解 KV Cache 原理：键值缓存、分块、复用策略。
  2. 配置 PagedAttention：`--block-size`、`--max-num-batches`。
  3. 测试不同配置：`--max-seq-len`、`--gpu-memory-utilization`。
  4. 使用 `nvidia-smi` 监控显存使用，找到最优配置。
- **Prompt 模板**：

```md
生成 vLLM 参数优化脚本，要求：
- 自动扫描 GPU：型号、显存、CUDA 版本
- 推荐最优配置：{block_size, max_num_batches, max_seq_len}
- 提供 A/B 测试框架：对比不同配置的吞吐/延迟
- 输出优化报告：{config, vram_usage, throughput, latency}
- 支持热加载：无需重启容器即可应用新参数
```

- **验收**：显存利用率 >80%；长文本（8k+ tokens）延迟降 >20%。

---

## Day 5：智能路由策略实现

- **目标**：实现多级路由，本地优先、云端兜底，成本最优。
- **实操**：
  1. 设计路由决策树：{用户等级、任务复杂度、实时负载}。
  2. 实现本地 vLLM 池：多实例、负载均衡。
  3. 接入云端 API：OpenAI GPT-4、Claude 3.5 Sonnet。
  4. 实现成本追踪：每次推理记录 token 费用。
- **Prompt 模板**：

```md
实现智能路由引擎，要求：
- 路由规则：VIP 用户 -> GPT-4，普通用户 -> 本地 vLLM
- 负载均衡：本地实例 CPU/GPU 利用率 <80% 时才路由
- 成本控制：单用户月度上限 $10，超限降级到本地
- 实时监控：每 5 秒更新模型状态，自动剔除故障节点
- 提供 /admin/routes 仪表盘：可视化路由决策、成本、延迟
```

- **验收**：路由切换延迟 <50ms；云端 fallback 失败率 <1%；成本追踪准确。

---

## Day 6：AI 辅助 Profiling 定位瓶颈

- **目标**：使用 AI 工具自动分析性能瓶颈，生成优化建议。
- **实操**：
  1. 集成 `py-spy`、`memory_profiler` 采集性能数据。
  2. 使用 Claude/Cursor 分析日志：识别热点函数、内存泄漏。
  3. 生成优化报告：{bottlenecks, suggestions, priority}。
  4. 实施优化：异步 I/O、连接池、缓存策略。
- **Prompt 模板**：

```md
创建 AI 辅助性能分析工具，要求：
- 自动采集：CPU、GPU、内存、网络指标
- 使用 LLM 分析日志，生成自然语言优化建议
- 识别瓶颈类型：I/O 密集、计算密集、锁竞争
- 提供代码级优化建议：具体到函数/行号
- 输出优化前后对比：{metric_before, metric_after, improvement}
```

- **验收**：能自动识别 >3 个瓶颈；优化后吞吐升 >30%。

---

## Day 7：容器化部署 + Prometheus Metrics 暴露

- **目标**：生产级部署，监控可观测，支持水平扩展。
- **实操**：
  1. 编写 Dockerfile：多阶段构建、非 root 用户、健康检查。
  2. 配置 Prometheus：暴露 `/metrics` 端点，采集推理指标。
  3. 集成 Grafana：可视化延迟、吞吐、错误率。
  4. 配置 Kubernetes：HPA（自动扩缩容）、ConfigMap（配置管理）。
- **Prompt 模板**：

```md
生成生产级部署配置，要求：
- Dockerfile：多阶段构建，仅保留运行依赖，非 root 用户
- docker-compose：vllm + prometheus + grafana + nginx
- Prometheus 指标：{requests_total, latency_seconds, vram_usage, cache_hit_rate}
- Grafana 仪表盘：实时监控、告警规则（延迟 >500ms）
- Kubernetes：HPA 基于 CPU/GPU 利用率自动扩缩
- 提供 /healthz 端点：K8s liveness/readiness 探测
```

- **验收**：`docker-compose up -d` 一键启动；Prometheus 采集正常；Grafana 仪表盘可访问；HPA 自动扩缩。

---

## 高频 Prompt 模板（占位）

1. 量化策略选择 Prompt（根据硬件/模型自动选择）
2. 路由决策树优化 Prompt（降低决策延迟）
3. 成本控制策略 Prompt（动态调整云端配额）
4. 性能瓶颈分析 Prompt（AI 辅助诊断）

---

## 动态调整建议（原版）

- **硬件弱 / 模型强**：Day 1-2 放慢节奏，先跑通 vLLM 基础后再做量化。
- **硬件强 / 模型弱**：Day 3-5 优先路由策略，更多时间放 Day 6-7 的监控与优化。
- **无部署经验**：先聚焦 Day 1-3 的基础部署，量化与优化放在后三天。
- **熟悉 Docker/K8s**：Day 7 可以快速完成，更多时间放 Day 4-6 的性能调优。

---

## 第 7 天自测清单（原版）

- `docker-compose up` 跑通 vLLM + Prometheus + Grafana
- 量化后显存降 >50%，吞吐升 >2x
- 路由切换失败率 <1%
- Prometheus 采集正常，Grafana 仪表盘可访问
- AI 辅助 Profiling 能识别 >3 个瓶颈
- HPA 自动扩缩正常
- 能清晰口述部署与性能优化方法论
