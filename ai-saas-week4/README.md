# LLM Inference Engine Benchmark

生产级推理引擎 Benchmark 脚本，支持 vLLM 和 Ollama 双端点对比测试。

## 功能特性

- **高性能并发压测**: 基于 asyncio + aiohttp 实现，支持可配置并发数和请求总数
- **精确指标计算**: TTFT（首字延迟）、TPOT（字间延迟）、End-to-End Latency、Peak GPU VRAM
- **双端点适配**: 自动适配 vLLM（OpenAI 兼容接口）与 Ollama（本地 API）
- **结果导出**: CSV 格式输出，包含详细的每请求数据
- **可视化分析**: 生成 P50/P95/P99 延迟曲线、吞吐曲线等对比图表
- **容错机制**: 内置重试与超时控制，失败请求不干扰整体统计

## 项目结构

```
ai-saas-week4/
├── benchmark/
│   ├── adapters.py      # vLLM 和 Ollama API 适配器
│   ├── metrics.py       # 指标计算模块（TTFT/TPOT/E2E）
│   ├── prompts.py        # 测试数据集（短/中/长 Prompt）
│   ├── main.py          # 主程序入口
│   └── visualization.py # 可视化脚本
├── docker-compose.yml   # vLLM + Ollama 并行部署配置
├── config.yaml          # 配置文件
└── requirements.txt     # 依赖列表
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

### 运行 Benchmark

#### 单引擎测试

```bash
# 测试 vLLM
python -m benchmark.main --engine vllm --url http://localhost:8000 --total-requests 100 --concurrency 10

# 测试 Ollama
python -m benchmark.main --engine ollama --url http://localhost:11434 --total-requests 100 --concurrency 10
```

#### 对比测试

```bash
python -m benchmark.main --compare \
    --vllm-url http://localhost:8000 \
    --ollama-url http://localhost:11434 \
    --total-requests 100 \
    --concurrency 10
```

#### 使用配置文件

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

## 命令行参数

### main.py

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

## 配置文件示例

```yaml
engine: vllm
base_url: http://localhost:8000

vllm_url: http://localhost:8000
ollama_url: http://localhost:11434

prompt_length: all
total_requests: 100
concurrency: 10
max_tokens: 512
timeout: 300
max_retries: 3

output: ./benchmark_results
```

## 许可证

MIT License
