# Week 5: 领域微调与 LoRA 实战

## 🎯 目标
掌握 LoRA/QLoRA 全流程，实现领域增强与热切换。

## 🛠️ 每日实操
- D1: Alpaca 格式数据集构建与清洗
- D2: Unsloth + QLoRA (4-bit) + FlashAttention 配置
- D3: 训练循环 (LR 调度 / Gradient Checkpoint / Checkpoint)
- D4: Perplexity & 领域 QA 对比评估
- D5: 权重合并 (merge_and_unload) + GGUF/FP16 转换
- D6: AI 辅助网格搜索超参调优
- D7: 微调模型注册为 Agent 专用工具

## ✅ 验收标准
- 训练 Loss 平稳无 NaN
- 领域 QA 准确率提升 >25%
- Agent 无缝切换微调模型
