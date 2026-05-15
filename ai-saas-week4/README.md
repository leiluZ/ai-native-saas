# LLM Inference Engine Benchmark, Quantization Pipeline & OpenAI Compatible Gateway

生产级推理引擎 Benchmark 脚本、模型量化转换流水线与 OpenAI 兼容 API 网关，支持 vLLM/Ollama 双端点对比测试、AWQ/GPTQ/INT8 量化策略，以及多模型路由、流式转发与 Function Calling。

## 功能特性

### Benchmark 功能

- **高性能并发压测**: 基于 asyncio + aiohttp 实现，支持可配置并发数和请求总数
- **精确指标计算**: TTFT（首字延迟）、TPOT（字间延迟）、End-to-End Latency、Peak GPU VRAM
- **双端点适配**: 自动适配 vLLM（OpenAI 兼容接口）与 Ollama（本地 API）
- **结果导出**: CSV 格式输出，包含详细的每请求数据
- **可视化分析**: 生成 P50/P95/P99 延迟曲线、吞吐曲线等对比图表
- **容错机制**: 内置重试与超时控制，失败请求不干扰整体统计

### 量化功能

- **多策略支持**: AWQ、GPTQ、INT8 三种量化策略
- **配置热切换**: 通过 config.yaml 配置文件切换量化策略
- **自动校准**: 自动下载校准数据集（WikiText），支持自定义采样数量
- **质量验证**: Perplexity 计算、质量回归测试（重复生成相似度对比）
- **自动回滚**: 量化失败自动回滚至 FP16 权重
- **显存快照**: 日志记录量化耗时与显存使用情况
- **vLLM 集成**: 支持 `--quantized` 参数加载量化模型

### 网关功能

- **OpenAI 兼容 API**: 完整映射 `/v1/chat/completions`、`/v1/models`、`/v1/embeddings` 端点
- **SSE 流式转发**: 严格遵循 OpenAI 流式协议，SSE 格式 chunk 转发，内置心跳保活
- **Function Calling**: 自动透传 `tools` 定义，解析 vLLM 返回的 `tool_calls`
- **API Key 鉴权**: Bearer Token 校验，支持排除路径配置
- **IP 限流**: 基于滑动窗口的请求频率限制，可配置阈值与窗口大小
- **指数退避重试**: 全局超时控制，自动重试与指数退避策略
- **全链路追踪**: 请求/响应中间件自动注入 `X-Request-ID`，记录延迟
- **模型注册表**: `{name, provider, endpoint, api_key, priority}` 结构化模型管理
- **健康检查与自动降级**: 定期探测模型可用性，连续失败自动降级/下线，恢复后自动上线

### KV Cache 参数自动寻优

- **网格搜索**: 自动遍历 gpu_memory_utilization × block_size × max_num_seqs 组合
- **自动压测**: 每组配置自动启动 vLLM，运行多轮并发压测，记录 OOM/吞吐/延迟
- **动态 Prefill 调整**: 根据长序列 Prefill 阻塞情况自动调整 enable_chunked_prefill 与 max_num_batched_tokens
- **安全阈值**: 显存 >92% 或 P99 延迟 >2s 自动终止，防止硬件损坏
- **GPU 自动扫描**: 检测 GPU 型号、显存、CUDA 版本
- **热加载**: 无需重启容器即可应用新参数
- **可视化输出**: 生成性能对比图与最优 vLLM 启动命令模板

## 项目结构

```
ai-saas-week4/
├── benchmark/
│   ├── adapters.py        # vLLM 和 Ollama API 适配器
│   ├── metrics.py         # 指标计算模块（TTFT/TPOT/E2E）
│   ├── prompts.py         # 测试数据集（短/中/长 Prompt）
│   ├── main.py            # Benchmark 主程序入口
│   ├── quantize.py        # 量化流水线主入口
│   ├── quantization.py    # 量化核心模块
│   ├── validation.py      # 模型验证模块
│   ├── visualization.py   # 可视化脚本
│   ├── gpu_scanner.py     # GPU 自动扫描（型号/显存/CUDA）
│   ├── kv_cache_config.py # KV Cache 网格搜索配置与安全阈值
│   ├── kv_cache_runner.py # KV Cache 压测编排器
│   ├── kv_cache_tuner.py  # KV Cache 自动寻优主入口
│   ├── kv_cache_visualization.py # KV Cache 性能可视化
│   ├── prefill_adjuster.py # 动态 Prefill 参数调整
│   └── vllm_lifecycle.py  # vLLM 生命周期管理（启动/停止/热加载）
├── gateway/
│   ├── main.py            # FastAPI 应用入口，生命周期管理
│   ├── config.py          # 网关配置（超时、重试、限流、心跳）
│   ├── middleware.py       # API Key 校验、IP 限流、Tracing ID
│   ├── proxy.py           # OpenAI 兼容代理转发、流式处理、重试
│   ├── registry.py        # 模型注册表、健康检查、自动降级
│   └── routes/
│       ├── chat.py        # /v1/chat/completions（含 SSE 流式）
│       ├── embeddings.py  # /v1/embeddings
│       ├── health.py      # /health 网关健康检查
│       └── models.py      # /v1/models
├── tests/
│   ├── test_gateway_registry.py
│   ├── test_gateway_middleware.py
│   ├── test_gateway_proxy.py
│   ├── test_gateway_routes.py
│   ├── test_gateway_main.py
│   ├── test_gateway_e2e.py
│   ├── test_gpu_scanner.py
│   ├── test_kv_cache_config.py
│   ├── test_kv_cache_runner.py
│   ├── test_kv_cache_visualization.py
│   ├── test_kv_cache_integration.py
│   ├── test_kv_cache_e2e.py
│   ├── test_prefill_adjuster.py
│   └── test_vllm_lifecycle.py
├── docker-compose.yml     # vLLM + Ollama 并行部署配置
├── config.yaml            # 配置文件
└── requirements.txt       # 依赖列表
```

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动推理引擎

使用 Docker Compose 启动 vLLM 和 Ollama：

```bash
docker-compose up -d
```

启动量化版本 vLLM：

```bash
docker-compose up -d vllm-quantized
```

## Benchmark 用法

### 单引擎测试

```bash
# 测试 vLLM
python -m benchmark.main --engine vllm --url http://localhost:8000 --total-requests 100 --concurrency 10

# 测试 Ollama
python -m benchmark.main --engine ollama --url http://localhost:11434 --total-requests 100 --concurrency 10
```

### 对比测试

```bash
python -m benchmark.main --compare \
    --vllm-url http://localhost:8000 \
    --ollama-url http://localhost:11434 \
    --total-requests 100 \
    --concurrency 10
```

### 使用配置文件

```bash
python -m benchmark.main --config config.yaml
```

### 生成可视化图表

```bash
python -m benchmark.visualization \
    --csv results/vllm_results.csv results/ollama_results.csv \
    --names vllm ollama \
    --output results/plots
```

## 量化流水线用法

### 运行量化

```bash
# 使用默认配置（AWQ 量化）
python -m benchmark.quantize --config config.yaml

# 指定量化策略
python -m benchmark.quantize --strategy awq
python -m benchmark.quantize --strategy gptq
python -m benchmark.quantize --strategy int8

# 量化并验证
python -m benchmark.quantize --validate

# 失败自动回滚
python -m benchmark.quantize --validate --rollback-on-failure
```

### 量化配置说明

在 `config.yaml` 中配置量化参数：

```yaml
quantization:
  strategy: awq # awq, gptq, int8
  model_name: Qwen/Qwen2.5-7B-Instruct
  quantized_model_path: ./models/quantized
  fp16_model_path: ./models/fp16

  calibration:
    dataset: wikitext
    dataset_name: wikitext-103-v1
    num_samples: 128
    max_seq_length: 512

  awq:
    bits: 4
    group_size: 128
    zero_point: true

  gptq:
    bits: 4
    group_size: 128
    act_order: true

  int8:
    load_in_8bit: true

  validation:
    perplexity: true
    quality_regression: true
    regression_samples: 10
    similarity_threshold: 0.85

  fallback:
    enable: true
    rollback_on_failure: true
```

## 网关用法

### 启动网关

```bash
cd gateway
uvicorn gateway.main:app --host 0.0.0.0 --port 8080 --reload
```

### 环境变量配置

创建 `.env` 文件：

```env
GATEWAY_API_KEY=sk-gateway-default-key
RATE_LIMIT_PER_MINUTE=60
GLOBAL_TIMEOUT=120.0
MAX_RETRIES=3
HEALTH_CHECK_INTERVAL=30
HEARTBEAT_INTERVAL=15.0
```

### API 端点

| 端点                      | 方法 | 说明                         |
| ------------------------- | ---- | ---------------------------- |
| `/`                       | GET  | 网关信息                     |
| `/health`                 | GET  | 网关健康检查（含模型状态）   |
| `/v1/chat/completions`    | POST | Chat Completions（支持流式） |
| `/v1/models`              | GET  | 列出可用模型                 |
| `/v1/models/{model_name}` | GET  | 获取指定模型信息             |
| `/v1/embeddings`          | POST | 文本向量化                   |

### 使用示例

```bash
# 非流式 Chat
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer sk-gateway-default-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "vllm-local",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'

# 流式 Chat
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer sk-gateway-default-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "vllm-local",
    "messages": [{"role": "user", "content": "Tell me a story."}],
    "stream": true
  }'

# Function Calling
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer sk-gateway-default-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "vllm-local",
    "messages": [{"role": "user", "content": "Weather in Beijing?"}],
    "tools": [{
      "type": "function",
      "function": {
        "name": "get_weather",
        "parameters": {
          "type": "object",
          "properties": {"location": {"type": "string"}},
          "required": ["location"]
        }
      }
    }]
  }'

# 列出模型
curl http://localhost:8080/v1/models \
  -H "Authorization: Bearer sk-gateway-default-key"

# Embeddings
curl -X POST http://localhost:8080/v1/embeddings \
  -H "Authorization: Bearer sk-gateway-default-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "vllm-local",
    "input": "Hello world"
  }'

# 健康检查
curl http://localhost:8080/health
```

### 使用 OpenAI SDK 直连

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="sk-gateway-default-key",
)

# 非流式
response = client.chat.completions.create(
    model="vllm-local",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)

# 流式
stream = client.chat.completions.create(
    model="vllm-local",
    messages=[{"role": "user", "content": "Tell me a story."}],
    stream=True,
)
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")

# Function Calling
response = client.chat.completions.create(
    model="vllm-local",
    messages=[{"role": "user", "content": "Weather in Beijing?"}],
    tools=[{
        "type": "function",
        "function": {
            "name": "get_weather",
            "parameters": {
                "type": "object",
                "properties": {"location": {"type": "string"}},
                "required": ["location"],
            },
        },
    }],
)
print(response.choices[0].message.tool_calls)
```

### 运行网关测试

```bash
cd ai-saas-week4
source venv/bin/activate
PYTHONPATH="$(pwd)" python -m pytest tests/test_gateway_*.py -v
```

## KV Cache 参数自动寻优

### 背景知识

#### 什么是 vLLM？

[vLLM](https://github.com/vllm-project/vllm) 是 UC Berkeley 开源的 LLM 推理加速框架，通过 **PagedAttention** 算法实现接近零浪费的 KV Cache 显存管理，推理吞吐可达 HuggingFace Transformers 的 **24 倍**。vLLM 提供 OpenAI 兼容 API，支持连续批处理（Continuous Batching）、量化推理（AWQ/GPTQ/INT8）、多 GPU 张量并行等生产级特性。

> 参考：[vLLM 官方文档](https://docs.vllm.ai/) | [vLLM GitHub](https://github.com/vllm-project/vllm) | [PagedAttention 论文](https://arxiv.org/abs/2309.06180)

#### 为什么需要 KV Cache？

在 Transformer 的自回归解码过程中，每个新 token 的生成都需要对**所有历史 token** 计算注意力（Attention）。如果不做缓存，每生成一个 token 就要重新计算所有历史 Key 和 Value 矩阵，计算量呈 **O(n²)** 增长。

**KV Cache** 的核心思想是：将已计算过的 Key 和 Value 矩阵缓存到显存中，生成下一个 token 时只需计算新 token 的 Query，然后与缓存的 K/V 做注意力运算。这样每个 step 的计算量降为 **O(n)**，推理速度大幅提升。

```
无 KV Cache: 每步重新计算所有 K/V → O(n²) 计算量
有 KV Cache: 缓存历史 K/V，仅计算增量 → O(n) 计算量
```

然而，KV Cache 也带来了新的挑战——**显存碎片化**。每个请求的 KV Cache 大小不同（取决于序列长度），频繁的分配与释放导致显存碎片，实际可用显存远低于理论值。

#### PagedAttention 如何解决显存碎片化？

PagedAttention 借鉴了操作系统中**虚拟内存分页**的思想，将 KV Cache 划分为固定大小的 **Block**（类似内存页），每个 Block 可存储固定数量 token 的 K/V 矩阵。这些 Block 在物理显存中不需要连续，通过**页表**映射到逻辑序列。

```
传统方案（连续分配）:
  Req A: [████████████░░░░░░░░░░░░░░░░] 预分配 2048 tokens，实际只用 800
  Req B: [████████░░░░░░░░░░░░░░░░░░░░] 预分配 2048 tokens，实际只用 500
  → 内部碎片 ~60%，外部碎片严重

PagedAttention（分页分配）:
  Block 0: [Req A tok 0-15]
  Block 1: [Req B tok 0-15]
  Block 2: [Req A tok 16-31]
  Block 3: [Req B tok 16-31]
  Block 4: [Req A tok 32-47]
  ...
  → 按需分配，零内部碎片，显存利用率可达 96%
```

**PagedAttention 的核心优势**：

- **零内部碎片**：按 Block 粒度按需分配，不再预分配最大长度
- **显存共享**：并行采样（Beam Search）或前缀缓存场景下，多个序列可共享同一组物理 Block
- **高吞吐**：显存利用率从传统方案的 20-40% 提升至 **>90%**，单 GPU 可同时服务更多请求

**关键参数**（本工具自动寻优的对象）：
| 参数 | 说明 | 典型值 |
|------|------|--------|
| `gpu_memory_utilization` | GPU 显存中用于 KV Cache 的比例 | 0.80 - 0.95 |
| `block_size` | 每个 KV Cache Block 的 token 数 | 8 / 16 / 32 |
| `max_num_seqs` | 最大并发序列数 | 32 - 256 |
| `enable_chunked_prefill` | 将长 Prefill 分块处理，避免阻塞解码 | true/false |
| `max_num_batched_tokens` | 单次 Prefill 最大 token 数 | 2048 - 8192 |

### 用法

```bash
# 基本用法：对指定模型运行网格搜索
python -m benchmark.kv_cache_tuner \
    --model meta-llama/Llama-2-7b-hf \
    --port 8000

# 自定义网格搜索范围
python -m benchmark.kv_cache_tuner \
    --model Qwen/Qwen2.5-7B-Instruct \
    --gmu-values 0.80 0.85 0.90 \
    --bs-values 16 32 \
    --mns-values 32 64 128 \
    --rounds 3 \
    --prompts 50 \
    --concurrency 8

# 指定输出目录
python -m benchmark.kv_cache_tuner \
    --model meta-llama/Llama-2-7b-hf \
    --output-dir ./tuning_results

# 禁用图表生成
python -m benchmark.kv_cache_tuner \
    --model meta-llama/Llama-2-7b-hf \
    --no-plots
```

### 命令行参数

| 参数                    | 说明                          | 默认值           |
| ----------------------- | ----------------------------- | ---------------- |
| `--model`               | 模型名称或路径（必填）        | -                |
| `--port`                | vLLM 服务端口                 | 8000             |
| `--host`                | vLLM 服务地址                 | 127.0.0.1        |
| `--gmu-values`          | gpu_memory_utilization 搜索值 | 0.80 0.85 0.90   |
| `--bs-values`           | block_size 搜索值             | 16 32            |
| `--mns-values`          | max_num_seqs 搜索值           | 32 64 128        |
| `--bt-values`           | max_num_batched_tokens 搜索值 | None 4096 8192   |
| `--no-chunked-prefill`  | 禁用 chunked_prefill 搜索     | False            |
| `--rounds`              | 每组配置压测轮数              | 3                |
| `--prompts`             | 每轮请求数                    | 50               |
| `--concurrency`         | 并发数                        | 8                |
| `--max-tokens`          | 最大生成 token 数             | 512              |
| `--timeout`             | 超时时间（秒）                | 300              |
| `--gpu-mem-max`         | 显存安全阈值（%）             | 92.0             |
| `--p99-latency-max`     | P99 延迟安全阈值（秒）        | 2.0              |
| `--consecutive-oom-max` | 连续 OOM 上限                 | 2                |
| `--output-dir`          | 输出目录                      | ./tuning_results |
| `--no-plots`            | 不生成图表                    | False            |

### 输出文件

```
tuning_results/
├── tuning_results.json              # 完整调优结果
├── kv_cache_throughput_vs_config.png # 吞吐量对比图
├── kv_cache_heatmap.png             # 参数热力图
├── kv_cache_performance_gain.png    # 性能收益对比图
└── kv_cache_oom_distribution.png    # OOM 分布图
```

### 运行测试

```bash
cd ai-saas-week4
source venv/bin/activate
PYTHONPATH="$(pwd)" python -m pytest tests/test_gpu_scanner.py tests/test_kv_cache_config.py tests/test_prefill_adjuster.py tests/test_vllm_lifecycle.py tests/test_kv_cache_runner.py tests/test_kv_cache_visualization.py tests/test_kv_cache_integration.py tests/test_kv_cache_e2e.py -v
```

## 命令行参数

### main.py（Benchmark）

| 参数               | 说明                                     | 默认值                 |
| ------------------ | ---------------------------------------- | ---------------------- |
| `--engine`         | 推理引擎类型（vllm/ollama）              | -                      |
| `--url`            | 引擎地址                                 | -                      |
| `--compare`        | 启用 vLLM vs Ollama 对比模式             | False                  |
| `--vllm-url`       | vLLM 地址                                | http://localhost:8000  |
| `--ollama-url`     | Ollama 地址                              | http://localhost:11434 |
| `--prompt-length`  | Prompt 长度类别（short/medium/long/all） | all                    |
| `--total-requests` | 请求总数                                 | 100                    |
| `--concurrency`    | 并发数                                   | 10                     |
| `--max-tokens`     | 最大生成 token 数                        | 512                    |
| `--timeout`        | 超时时间（秒）                           | 300                    |
| `--max-retries`    | 最大重试次数                             | 3                      |
| `--output`         | 输出目录                                 | ./benchmark_results    |
| `--config`         | 配置文件路径                             | -                      |

### quantize.py（量化）

| 参数                    | 说明                      | 默认值      |
| ----------------------- | ------------------------- | ----------- |
| `--config`              | 配置文件路径              | config.yaml |
| `--strategy`            | 量化策略（awq/gptq/int8） | -           |
| `--validate`            | 量化后运行验证            | False       |
| `--rollback-on-failure` | 验证失败时回滚到 FP16     | False       |

### visualization.py

| 参数       | 说明                     | 默认值              |
| ---------- | ------------------------ | ------------------- |
| `--csv`    | CSV 文件路径（支持多个） | -                   |
| `--names`  | 引擎名称（对应 CSV）     | -                   |
| `--output` | 输出目录                 | ./benchmark_results |
| `--show`   | 显示图表                 | False               |

## 测试数据集

测试集包含三种长度的 Prompt：

- **Short（短）**: ≤ 128 tokens，共 100 条
- **Medium（中）**: 128-512 tokens，共 100 条
- **Long（长）**: 512-2048 tokens，共 100 条

## 输出指标

### 延迟指标

| 指标 | 说明                            |
| ---- | ------------------------------- |
| TTFT | Time To First Token，首字延迟   |
| TPOT | Time Per Output Token，字间延迟 |
| E2E  | End-to-End Latency，端到端延迟  |

### 统计指标

| 指标       | 说明                 |
| ---------- | -------------------- |
| P50        | 50% 请求延迟低于此值 |
| P95        | 95% 请求延迟低于此值 |
| P99        | 99% 请求延迟低于此值 |
| Throughput | 吞吐率（tokens/秒）  |

### 量化指标

| 指标           | 说明                 |
| -------------- | -------------------- |
| Perplexity     | 困惑度，衡量生成质量 |
| Memory Savings | 显存节省比例         |
| Similarity     | 重复生成相似度       |

## 验收标准

### Benchmark 验收

- ✅ Benchmark 脚本一键运行
- ✅ 输出结构化 CSV 与对比图表
- ✅ 覆盖短/中/长上下文场景
- ✅ 指标统计无偏差

### 量化验收

- ✅ 量化流程自动化
- ✅ 显存占用下降 >50%
- ✅ 吞吐提升 >2x
- ✅ Perplexity 增幅 <5%
- ✅ 质量抽检无严重退化

### 网关验收

- ✅ vLLM 完整支持流式 & Function Calling
- ✅ OpenAI 官方 SDK 零改造直连
- ✅ 网关额外延迟 <50ms
- ✅ SSE 流稳定不断连

### KV Cache 寻优验收

- ✅ 找到最优 KV Cache 配置
- ✅ 并发承载量提升 >30%
- ✅ 零 OOM
- ✅ Cache 利用率 >85%
- ✅ 显存利用率 >80%
- ✅ 长文本（8k+ tokens）延迟降 >20%

## 许可证

MIT License
