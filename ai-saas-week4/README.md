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
│   └── visualization.py   # 可视化脚本
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
│   └── test_gateway_main.py
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

## 许可证

MIT License
