# Week 4: 私有化部署与推理加速

## 🎯 目标
掌握 vLLM 生产部署、量化加速与云/端智能路由。

## 🛠️ 每日实操
- D1: Ollama vs vLLM 基准测试 (吞吐/延迟/显存)
- D2: AWQ/GPTQ/INT8 量化转换流程
- D3: OpenAI 兼容网关 (LiteLLM 或自研代理)
- D4: KV Cache & PagedAttention 参数调优
- D5: 智能路由策略 (本地优先 -> 云端 fallback)
- D6: AI 辅助 Profiling 定位瓶颈
- D7: 容器化部署 + Prometheus Metrics 暴露

## ✅ 验收标准
- vLLM 支持流式 & Function Calling
- 量化后显存降 >50%，吞吐升 >2x
- 路由切换失败率 <1%
