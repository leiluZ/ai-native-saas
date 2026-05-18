# Week 5: 领域微调与 LoRA 实战 学习计划（原版整理）

## Day 1：Alpaca 格式数据集构建与清洗

- **目标**：掌握领域数据集从采集到标准化输出的全流程，产出高质量 Alpaca 格式训练数据。
- **实操**：
  1. 收集领域原始语料（文档、FAQ、对话日志、知识库）。
  2. 用 AI 将原始语料转换为 Alpaca 格式 `{"instruction": ..., "input": ..., "output": ...}`。
  3. 编写数据清洗脚本：去重、长度过滤、敏感词过滤、格式校验。
  4. 划分 train/val/test（8:1:1），导出 `train.jsonl` / `val.jsonl` / `test.jsonl`。
  5. 统计分析：指令长度分布、output 长度分布、类别标签均衡性。
- **Prompt 模板**：

```md
你是一位 NLP 数据标注专家。请将以下领域文本转换为 Alpaca 格式：

原始文本：
{raw_text}

要求：
1. instruction 用清晰的自然语言描述任务
2. input 可为空字符串，若有上下文则填入
3. output 必须准确、完整、专业
4. 每条数据独立，不依赖对话历史
5. 返回 JSON 格式：{"instruction": "...", "input": "...", "output": "..."}

批量处理时，每 20 条输出一次统计：平均长度、类别分布、异常数量。
```

- **验收**：产出 3 个 jsonl 文件，总量 >= 500 条；格式 100% 通过 JSON Schema 校验；去重率 > 95%；长度分布无明显异常。

## Day 2：Unsloth + QLoRA (4-bit) + FlashAttention 配置

- **目标**：搭建高效微调环境，完成 QLoRA 4-bit 量化配置与 FlashAttention 加速。
- **实操**：
  1. 安装 `unsloth`、`transformers`、`bitsandbytes`、`peft`、`accelerate`。
  2. 配置 QLoRA 4-bit 量化参数（NF4 数据类型、双重量化）。
  3. 加载基座模型（Llama-3/Phi-3/Qwen2.5-7B 择一），验证显存占用。
  4. 配置 LoRA rank / alpha / target_modules，打印可训练参数量。
  5. 启用 FlashAttention-2，对比开关前后推理速度。
- **Prompt 模板**：

```md
使用 Unsloth 加载模型并配置 QLoRA，要求：
- 使用 FastLanguageModel.from_pretrained 加载 {model_name}
- 4-bit 量化：load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16
- LoRA 配置：r=16, lora_alpha=16, target_modules 包含所有线性层
- 启用 gradient_checkpointing 和 FlashAttention-2
- 输出可训练参数占比和预估 GPU 显存
- 附显存不足时的 fallback 策略（减少 batch_size / 更小 rank）
```

- **验收**：模型成功加载，可训练参数 < 总参数 1%；单卡 24GB 显存可运行；FlashAttention 启用后推理速度提升 > 30%。

## Day 3：训练循环（LR 调度 / Gradient Checkpoint / Checkpoint）

- **目标**：跑通完整训练循环，掌握学习率调度、梯度检查点与断点续训。
- **实操**：
  1. 使用 `SFTTrainer` 或 `Trainer` 封装训练流程。
  2. 配置余弦退火 LR 调度 + warmup_ratio=0.03。
  3. 设置 gradient_checkpointing 降低显存，gradient_accumulation_steps=4。
  4. 实现 checkpoint 自动保存（按 steps 或 best_loss）。
  5. 从 checkpoint 断点续训，验证 loss 连续性。
  6. 集成 Wandb / TensorBoard 可视化 loss 曲线。
- **Prompt 模板**：

```md
配置 SFTTrainer 训练参数，要求：
- 使用 SFTTrainer，max_seq_length=2048
- LR 调度：cosine，learning_rate=2e-4，warmup_ratio=0.03
- per_device_train_batch_size=4，gradient_accumulation_steps=4
- gradient_checkpointing=True，fp16/bf16 混合精度
- 每 50 steps 保存 checkpoint，保留最近 3 个
- 集成 Wandb，记录 loss / lr / grad_norm
- 训练结束后自动保存最终模型至 ./output/{model_name}-lora
- 附断点续训命令示例
```

- **验收**：训练 500+ steps 无 OOM、无 NaN；loss 曲线平滑下降；checkpoint 可恢复训练；Wandb 面板可查看 loss/lr 曲线。

## Day 4：Perplexity & 领域 QA 对比评估

- **目标**：建立微调效果评估体系，用 Perplexity 与领域 QA 准确率量化提升。
- **实操**：
  1. 在 test 集上计算基座模型 vs 微调模型的 Perplexity。
  2. 构建领域 QA 评测集（50+ 道选择题/简答题），覆盖核心场景。
  3. 用统一 prompt 对基座模型和微调模型分别推理，收集答案。
  4. 计算准确率、F1、ROUGE-L 等指标，生成对比报告。
  5. 分析 bad case，记录改进方向。
- **Prompt 模板**：

```md
编写评估脚本，要求：
- 加载基座模型和 LoRA 微调模型，使用同一 tokenizer
- 对 test.jsonl 逐条推理，计算 PPL（使用 model.eval() + torch.no_grad()）
- 对领域 QA 评测集，使用同一 prompt 模板："请回答以下{领域}问题：\n{question}\n答案："
- 输出对比表格：模型 | PPL | 准确率 | F1 | 平均推理耗时
- 高亮准确率变化 > 10% 的样本作为 bad case 分析
- 结果保存为 evaluation_report.json
```

- **验收**：微调模型 PPL 下降 > 20%；领域 QA 准确率提升 > 25%；评估报告自动生成；bad case 已分类记录。

## Day 5：权重合并（merge_and_unload）+ GGUF/FP16 转换

- **目标**：掌握 LoRA 权重合并与模型格式转换，实现生产环境部署。
- **实操**：
  1. 使用 `model.merge_and_unload()` 合并 LoRA 权重到基座模型。
  2. 验证合并后模型的推理精度（与合并前 LoRA 推理对比，误差 < 1e-5）。
  3. 导出为 FP16 格式（`model.save_pretrained`），计算模型大小。
  4. 使用 `llama.cpp` 的 `convert-hf-to-gguf.py` 转换为 GGUF 格式。
  5. 根据部署场景选择量化级别（Q4_K_M / Q5_K_M / Q8_0），对比体积与精度。
  6. 使用 `llama-cli` 或 `ollama` 加载 GGUF 模型做本地推理验证。
- **Prompt 模板**：

```md
合并 LoRA 权重并转换格式，要求：
- model.merge_and_unload() 后保存为 FP16 到 ./output/{model_name}-merged
- 对比合并前后同一 batch 的 logits 差异，确保 max_diff < 1e-5
- 使用 convert-hf-to-gguf.py 转换为 GGUF，尝试 Q4_K_M / Q5_K_M 两种量化
- 输出对比：格式 | 体积 | 加载速度 | 单 token 推理耗时
- 附 ollama Modelfile 模板，支持一键创建自定义模型
```

- **验收**：合并后 logits 误差 < 1e-5；GGUF 模型可被 `llama-cli` 或 `ollama` 正常加载推理；Q4_K_M 体积约为 FP16 的 25%；推理结果与 PyTorch 版本一致。

## Day 6：AI 辅助网格搜索超参调优

- **目标**：用 AI 驱动超参搜索，自动探索最优 LoRA 配置组合。
- **实操**：
  1. 定义超参搜索空间：r ∈ [8, 16, 32, 64]，lora_alpha ∈ [8, 16, 32]，lr ∈ [1e-4, 2e-4, 5e-4]。
  2. 让 AI 生成网格搜索脚本，自动遍历超参组合。
  3. 每个组合训练 200 steps，记录 loss / PPL / 显存占用。
  4. AI 分析结果，推荐最优超参组合并给出理由。
  5. 用最优组合完整训练，对比默认配置的提升幅度。
- **Prompt 模板**：

```md
编写网格搜索脚本，要求：
- 搜索空间：r=[8,16,32]，lora_alpha=[8,16,32]，lr=[1e-4,2e-4,5e-4]
- 每组训练 200 steps，在 val 集计算 PPL
- 每次搜索前释放 GPU 缓存（torch.cuda.empty_cache()）
- 记录结果到 grid_search_results.csv：r | alpha | lr | loss | ppl | gpu_memory
- 搜索结束后，AI 自动分析并输出最优组合与选择理由
- 附早停策略：若 loss 3 轮不降则提前终止当前组合
```

- **验收**：自动化搜索 >= 12 组超参组合；产出 `grid_search_results.csv`；AI 推荐的最优组合有数据支撑；最优组合 loss 低于默认配置。

## Day 7：微调模型注册为 Agent 专用工具

- **目标**：将微调模型封装为 Agent 可调用的 Tool，实现模型热切换与领域路由。
- **实操**：
  1. 封装微调模型服务：FastAPI 推理端点 `/api/v1/finetuned/chat`。
  2. 模型管理模块：加载/卸载/切换模型，支持热切换（不含重启服务）。
  3. 注册为 LangChain Tool：定义工具名、描述、参数 schema。
  4. Agent 路由逻辑：根据用户意图自动选择基座模型 or 微调模型。
  5. 实现 fallback：微调模型不可用时自动回退到基座模型。
  6. 添加模型切换日志与性能监控（调用次数、平均耗时、成功率）。
- **Prompt 模板**：

```md
将微调模型封装为 Agent Tool，要求：
- 创建 FinetunedModelTool，使用 @tool 装饰器
- 工具描述：明确说明模型擅长的领域和调用时机
- 模型管理类 ModelManager 支持 load/unload/switch：
  - load(model_name): 加载模型到 GPU
  - unload(): 释放 GPU 显存
  - switch(model_name): 热切换到指定模型
- Agent system prompt 中定义路由规则：
  "当用户咨询{领域}相关问题时，优先使用 finetuned_model 工具"
- fallback：模型加载失败或推理超时 10s，自动使用 base_model 回答
- 记录每次调用的 metadata：model_name, latency, success, token_count
```

- **验收**：Agent 可自动识别领域问题并调用微调模型；模型切换延迟 < 3s；fallback 机制工作正常；调用日志完整可追溯。

## 高频 Prompt 模板（占位）

1. Alpaca 格式批量转换与质量审核 Prompt
2. QLoRA 显存不足时的自动降级策略 Prompt
3. 训练异常诊断 Prompt（Loss 爆炸 / NaN / 不收敛）
4. 领域评测集自动生成 Prompt
5. Agent 模型路由决策 Prompt（意图识别 + 模型选择）

## 动态调整建议（原版）

- 数据充足 / 质量高：Day 1 可压缩至半天，更多时间投入 Day 4 评估与 Day 6 调优。
- 显存不足（< 16GB）：Day 2-3 优先探索更小基座模型（Phi-3-mini / Qwen2.5-1.5B）或更大 rank 压缩。
- 后端经验丰富 / 模型部署新手：Day 5 和 Day 7 放慢节奏，重点理解 GGUF 量化原理与 Agent 工具注册机制。
- 已有评测体系：Day 4 聚焦领域特有指标设计，快速集成到现有 pipeline。
- 无 NLP 经验：Day 1-3 为核心路径，优先跑通数据->训练->推理全流程，Day 6 可降级为手动调参。

## 第 7 天自测清单（原版）

- 数据集 >= 500 条 Alpaca 格式，train/val/test 划分完整，格式校验通过
- QLoRA 训练跑通 >= 500 steps，loss 曲线平滑无 NaN
- 微调模型 PPL 下降 > 20%，领域 QA 准确率提升 > 25%
- LoRA 权重成功合并，GGUF 模型可被 ollama/llama.cpp 加载推理
- 网格搜索结果产出 csv，最优超参组合有数据支撑
- Agent 可自动识别领域意图并路由到微调模型，fallback 正常
- 模型切换日志完整，包含调用次数、耗时、成功率
- 能清晰口述 LoRA/QLoRA 原理、训练技巧与部署注意事项
