# Week 5: 领域微调与 LoRA 实战

## 🎯 目标
掌握 LoRA/QLoRA 全流程，实现领域增强与热切换。覆盖高质量数据集构建、Unsloth 高效微调、训练稳定性控制、量化评估、权重合并导出、AI 辅助超参寻优及 Agent 工具化注册，最终交付可无缝切换的生产级领域模型。

---

## Day 1：Alpaca 格式数据集构建与清洗

- **目标**：掌握领域数据流水线构建，实现高纯度、结构化微调数据集。
- **实操**：
  1. 收集领域原始语料（文档、FAQ、对话日志、知识库），清洗 HTML/Markdown 噪音、脱敏 PII。
  2. 用 AI 将原始语料转换为 Alpaca 格式 `{"instruction": ..., "input": ..., "output": ...}`。
  3. 编写数据清洗脚本：MinHash/SimHash 去重（Jaccard 阈值 0.85）、长度过滤、格式校验。
  4. LLM 辅助质量打分：逻辑完整性 > 0.8、领域相关性 > 0.7 方可保留。
  5. 划分 train/val/test（8:1:1），导出 `train.jsonl` / `val.jsonl` / `test.jsonl`。
  6. 统计分析：指令长度分布、output 长度分布、类别标签均衡性，生成分布报告与可视化。
- **Prompt 模板**：

```md
你是一位 NLP 数据标注专家。编写领域微调数据清洗与格式化流水线，要求：

1. 将以下领域文本转换为 Alpaca 格式，每条独立不依赖对话历史：
   原始文本：{raw_text}
   返回 JSON：{"instruction": "...", "input": "...", "output": "..."}

2. LLM 辅助质量打分：对每条数据评估逻辑完整性（0-1）和领域相关性（0-1），
   保留两项均 > 0.7 的样本

3. 基于 MinHash + Jaccard 去重，阈值 0.85，支持增量去重缓存

4. 自动校验 instruction/input/output 非空，JSON Schema 合法

5. 批量处理时每 20 条输出统计：平均长度、类别分布、异常数量

6. 自动划分 train/val/test（8:1:1），seed=42，生成数据分布报告（样本数、Token 分布直方图）
```

- **验收**：
  - 产出 3 个 jsonl 文件，总量 >= 1000 条
  - 格式 100% 通过 JSON Schema 校验
  - 去重率 > 30%，PII 零残留
  - 长度分布合理（90% 样本 256 ~ 2048 tokens）
  - 数据分布报告与可视化完整

## Day 2：Unsloth + QLoRA (4-bit) + FlashAttention 配置

- **目标**：搭建低显存、高吞吐微调环境，完成 QLoRA 4-bit 量化配置与 FlashAttention 加速。
- **实操**：
  1. 安装 `unsloth`、`transformers`、`bitsandbytes`、`peft`、`accelerate`。
  2. 使用 `FastLanguageModel.from_pretrained` 加载基座模型（Llama-3/Phi-3/Qwen2.5-7B 择一）至 4-bit NF4 精度。
  3. 配置 LoRA 适配器：`r=16`、`alpha=16`、`target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"]`。
  4. 启用 FlashAttention-2，验证 kernel 激活状态。
  5. 运行 dummy forward/backward，打印可训练参数占比、VRAM 峰值、梯度范数。
  6. 提供 `config.yaml` 管理基座路径、量化策略、LoRA 参数，支持版本切换。
- **Prompt 模板**：

```md
使用 Unsloth 加载模型并配置 QLoRA，要求：

1. 使用 FastLanguageModel.from_pretrained 加载 {model_name}
2. 4-bit 量化：load_in_4bit=True，bnb_4bit_compute_dtype=torch.bfloat16，NF4 数据类型
3. LoRA 配置：r=16，lora_alpha=16，target_modules 包含所有线性层，dropout=0.05
4. 强制启用 FlashAttention-2 和 gradient_checkpointing
5. 运行 1 步 dummy training，输出可训练参数占比、GPU 显存峰值、梯度范数
6. 附显存不足时的 fallback 策略（减少 batch_size / 更小 rank / 更小基座模型）
7. 输出配置文件 config.yaml，支持参数热切换与版本管理
```

- **验收**：
  - 模型成功加载，可训练参数 < 总参数 1%
  - 单卡 24GB 显存可运行（7B 模型 < 10GB）
  - FlashAttention 启用后推理速度提升 > 30%
  - Dummy 步无 OOM，梯度范数正常

## Day 3：训练循环（LR 调度 / Gradient Checkpoint / Checkpoint）

- **目标**：实现稳定可恢复的训练流程，掌握学习率调度、梯度检查点与 NaN 防护。
- **实操**：
  1. 使用 `SFTTrainer` 封装训练流程，`max_seq_length=2048`，`packing=True`。
  2. 配置余弦退火 LR 调度 + warmup_ratio=0.03，`lr_scheduler_type="cosine"`。
  3. 设置 gradient_checkpointing 降低显存，gradient_accumulation_steps=4，fp16/bf16 混合精度。
  4. 实现 checkpoint 自动保存（每 50 steps 或 best_loss），保留最近 3 个。
  5. 内置 NaN 防护：检测 loss=NaN 自动跳过 batch 并记录警告，连续 3 次触发 early_stop。
  6. 支持 resume_from_checkpoint 断点续训，验证 loss 连续性。
  7. 集成 Wandb / TensorBoard 可视化 loss、lr、grad_norm、throughput 曲线。
- **Prompt 模板**：

```md
编写生产级 LoRA 训练循环脚本，要求：

1. TRL SFTTrainer 完整配置：max_steps，per_device_train_batch_size=4，gradient_accumulation_steps=4，packing=True
2. LR 调度：cosine，learning_rate=2e-4，warmup_ratio=0.03
3. 开启 gradient_checkpointing 与 fp16/bf16 mixed precision
4. 每 50 steps 保存 checkpoint，仅保留 top 3 最佳模型（按 eval_loss）
5. 集成 Wandb/TensorBoard：记录 loss、lr、grad_norm、throughput(samples/s)、VRAM
6. 内置 NaN 防护：检测 loss=NaN 自动跳过 batch，连续 3 次触发 early_stop 并回滚至上一 checkpoint
7. 支持 resume_from_checkpoint 断点续训
8. 训练结束后自动保存最终模型至 ./output/{model_name}-lora
```

- **验收**：
  - 训练 500+ steps 无 OOM、无 NaN
  - Loss 曲线平滑下降，checkpoint 可恢复训练
  - 显存峰值稳定，利用率 > 75%
  - Wandb 面板可实时查看 loss/lr 曲线

## Day 4：Perplexity & 领域 QA 对比评估

- **目标**：建立微调效果评估体系，用 Perplexity 与领域 QA 准确率量化提升。
- **实操**：
  1. 在 test 集上计算基座模型 vs 微调模型的 Perplexity。
  2. 构建领域 QA 评测集（100+ 道选择题/简答题），覆盖核心场景。
  3. 用统一 prompt 对基座模型和微调模型分别推理，收集答案。
  4. 计算 EM（Exact Match）、F1、ROUGE-L 等指标，生成对比报告。
  5. LLM 辅助错误分析：按事实错误、逻辑断裂、格式不符分类统计。
  6. 人工抽检 10% 标注 hallucination 率，记录 bad case 改进方向。
- **Prompt 模板**：

```md
编写评估脚本，要求：

1. 加载基座模型和 LoRA 微调模型，使用同一 tokenizer
2. 对 test.jsonl 逐条推理，计算 PPL（model.eval() + torch.no_grad()）
3. 对领域 QA 评测集，使用同一 prompt 模板：
   "请回答以下{领域}问题：\n{question}\n答案："
   支持 streaming 生成，记录 token 耗时与显存
4. 自动计算 EM、F1、ROUGE-L，输出 macro/micro 平均
5. LLM 辅助错误分类：事实错误 / 逻辑断裂 / 格式不符，生成错误分布图
6. 输出对比表格：模型 | PPL | EM | F1 | ROUGE-L | Hallucination% | 平均推理耗时
7. 结果保存为 evaluation_report.md + evaluation_report.csv
```

- **验收**：
  - 微调模型 PPL 下降 > 15%
  - 领域 QA 准确率提升 > 25%（EM/F1 综合）
  - Hallucination 率下降 > 30%
  - 评估报告结构完整，bad case 已分类记录

## Day 5：权重合并（merge_and_unload）+ GGUF/FP16 转换

- **目标**：完成 LoRA 权重合并与模型格式转换，实现生产环境部署。
- **实操**：
  1. 使用 `model.merge_and_unload()` 合并 LoRA 权重到基座模型，导出 BF16/FP16 完整模型。
  2. 验证合并后推理精度：对比合并前后同一 batch 的 logits 差异，max_diff < 1e-5。
  3. 使用 `llama.cpp` 的 `convert-hf-to-gguf.py` 转换为 GGUF 格式。
  4. 根据部署场景选择量化级别（Q4_K_M / Q5_K_M / Q8_0），对比体积与精度损耗。
  5. 运行一致性测试：相同 prompt 对比 adapter 推理 / merge 推理 / GGUF 推理的 token 序列重合度 > 98%。
  6. 验证 ollama / vLLM 加载兼容性，记录冷启动时间与首字延迟（TTFT）。
- **Prompt 模板**：

```md
编写模型权重合并与 GGUF 转换流水线，要求：

1. 执行 merge_and_unload，输出完整权重至 ./output/{model_name}-merged
2. 对比合并前后同一 batch 的 logits 差异，确保 max_diff < 1e-5
3. 调用 llama.cpp convert 脚本，自动生成 Q4_K_M / Q5_K_M / Q8_0 三种 GGUF
4. 一致性验证：随机抽取 50 条 prompt，对比 merge/GGUF 输出 token 重合度 > 98%
5. 输出转换报告：格式 | 体积 | 量化损耗(PPL增幅) | 加载速度 | TTFT
6. 自动注册至 ollama/vLLM 模型库，验证推理接口可正常调用
7. 保留原始 checkpoint 与 adapter 权重，支持回滚
```

- **验收**：
  - 合并后模型与 adapter 推理一致性 > 98%
  - GGUF 多精度文件生成完整，可通过 `llama-cli` / ollama 正常加载
  - Q4_K_M 体积约为 FP16 的 25%，量化精度损耗 < 2%（PPL 增幅）
  - vLLM/Ollama 无缝加载，冷启动 < 10s

## Day 6：AI 辅助网格搜索超参调优

- **目标**：通过自动化寻优与 LLM 分析闭环，定位最优训练配置。
- **实操**：
  1. 定义搜索空间：`r ∈ [8, 16, 32]`、`alpha ∈ [16, 32, 64]`、`lr ∈ [1e-5, 2e-5, 5e-5]`、`dropout ∈ [0.0, 0.05, 0.1]`。
  2. 使用 Optuna 或 W&B Sweep 自动调度，每轮记录 val_loss、QA_acc、训练耗时、GPU 利用率。
  3. 内置早停：连续 2 轮无改善自动终止当前 trial。
  4. 将 Sweep 结果输入 LLM，生成归因分析（过拟合/欠拟合/显存瓶颈）与下一轮建议。
  5. 输出 Top-3 配置对比表 + 参数重要性排序，固化最优参数至 `config_best.yaml`。
- **Prompt 模板**：

```md
构建 AI 辅助超参寻优流水线，要求：

1. Optuna 网格/贝叶斯搜索：覆盖 LoRA r/alpha/dropout、learning_rate、batch_size
2. 每轮训练自动上报 Wandb，记录 val_loss、QA_EM、GPU_util、训练耗时
3. 每次搜索前释放 GPU 缓存（torch.cuda.empty_cache()）
4. LLM 分析模块：输入 JSON 结果，输出瓶颈归因（过拟合/欠拟合/显存瓶颈）与参数调整建议
5. 自动生成下一轮建议：参数调整方向、预期收益、风险提示
6. early_pruning：连续 2 轮无改善自动终止该 trial
7. 输出 Top-3 配置对比表 + 参数重要性排序图，固化 config_best.yaml
```

- **验收**：
  - 完成 >= 8 组有效 Sweep
  - 最优配置较 baseline QA 提升 > 10%
  - LLM 归因报告可解释、可执行
  - 固化 `config_best.yaml` 并验证复现性

## Day 7：微调模型注册为 Agent 专用工具

- **目标**：将微调模型封装为 Agent 可调用的 Tool，实现意图路由与模型热切换。
- **实操**：
  1. 封装微调模型服务：FastAPI 推理端点 `/api/v1/finetuned/chat`。
  2. 定义 Tool Schema：`name`、`description`、`input_schema`，兼容 OpenAI function calling 规范。
  3. 注册为 LangChain Tool（`@tool` 装饰器），明确模型擅长的领域和调用时机。
  4. 实现意图路由器：基于 embedding 相似度 + 关键词匹配，自动路由至微调模型或基座模型。
  5. 模型管理模块 ModelManager：支持 load/unload/switch，热切换延迟 < 100ms。
  6. 实现 fallback：模型加载失败、推理超时 10s 或拒识时自动回退到基座模型。
  7. 支持流式响应透传，保持 SSE 格式不中断。
  8. 全量日志：记录路由决策、模型名称、响应时间、调用成功率。
- **Prompt 模板**：

```md
将微调模型封装为 Agent Tool 并实现热切换路由，要求：

1. 创建 FinetunedModelTool，使用 @tool 装饰器，兼容 OpenAI function calling 规范
2. 工具描述明确说明模型擅长的领域和调用时机
3. 实现意图路由器：
   - 基于 embedding 相似度 + 关键词匹配，阈值可配
   - 领域问题优先路由至微调模型，通用问题使用基座模型
4. ModelManager 类支持热切换：
   - load(model_name)：加载模型到 GPU
   - unload()：释放 GPU 显存
   - switch(model_name)：热切换到指定模型
5. Agent system prompt 定义路由规则：
   "当用户咨询{领域}相关问题时，优先使用 finetuned_model 工具"
6. fallback 机制：模型加载失败或推理超时 10s，自动回退至基座模型
7. 支持流式响应透传（SSE），切换时不中断
8. 全量日志：记录路由决策、model_name、latency、success、token_count
9. 提供 /admin/agent-tools 调试面板：手动切换、压测、日志追溯
```

- **验收**：
  - Agent 可自动识别领域问题并调用微调模型，路由准确率 > 90%
  - 模型热切换延迟 < 100ms，fallback 机制稳定
  - Function Calling 解析率 100%
  - 路由日志完整，支持全链路追溯

---

## 每日验收标准

| Day | 验收条件 |
|-----|---------|
| D1 | 有效样本 >= 1000 条，格式 100% 合法；去重率 > 30%；PII 零残留；数据分布报告完整 |
| D2 | 7B 模型加载显存 < 10GB；LoRA 注入成功；FA 激活；Dummy 步无 OOM |
| D3 | Loss 平滑无 NaN；Checkpoint 自动保存与回滚；断点续训验证通过；VRAM 稳定 |
| D4 | PPL 下降 > 15%；领域 QA 准确率提升 > 25%；Hallucination 率下降 > 30%；评估报告完整 |
| D5 | 合并一致性 > 98%；GGUF 多精度生成完整；量化损耗 < 2%；ollama/vLLM 加载验证通过 |
| D6 | 完成 >= 8 组 Sweep；最优配置提升 > 10%；LLM 归因报告可执行；config_best.yaml 固化 |
| D7 | Agent 路由准确率 > 90%；热切换 < 100ms；fallback 稳定；全链路日志可审计 |

## 最终验收标准

- 训练 Loss 平稳无 NaN，Checkpoint 可完整恢复
- 领域 QA 准确率提升 > 25%，PPL 显著下降，Hallucination 率明显降低
- LoRA 权重成功合并，GGUF 多精度导出一致，兼容 ollama/llama.cpp/vLLM
- AI 辅助超参寻优输出可复现最优配置
- 微调模型注册为 Agent 专用工具，热切换延迟 < 100ms，无缝降级
- 完整交付物：数据清洗脚本、训练配置、评估报告、GGUF 权重、Agent 路由代码、Sweep 日志

## 高频 Prompt 模板

1. **领域数据清洗与 Alpaca 格式化**
   - 多格式解析 + LLM 辅助质量打分
   - MinHash 去重 + 长度过滤
   - 自动划分 train/val/test 与分布报告生成

2. **Unsloth QLoRA 环境初始化**
   - 4-bit NF4 加载 + bfloat16 精度对齐
   - LoRA 参数全覆盖注入 + FA 强制启用
   - Dummy 步显存与梯度验证

3. **训练异常诊断（Loss 爆炸 / NaN / 不收敛）**
   - SFTTrainer 完整配置 + gradient checkpointing
   - Cosine LR 调度 + warmup
   - NaN 防护、断点续训与 W&B 集成

4. **PPL 与领域 QA 对比评估**
   - 跨模型 PPL 计算 + 流式生成压测
   - EM / F1 / ROUGE-L 自动统计
   - LLM 辅助错误分类与可视化报告

5. **权重合并与 GGUF 导出流水线**
   - merge_and_unload + llama.cpp 转换
   - 一致性验证 + 量化损耗评估
   - ollama / vLLM 兼容性测试

6. **AI 辅助超参网格寻优**
   - Optuna / W&B Sweep 自动调度 + early_pruning
   - LLM 归因分析与下一轮建议生成
   - Top-3 配置对比 + 参数重要性排序

7. **Agent 工具注册与热切换路由**
   - OpenAI 兼容 Tool Schema 定义
   - 意图路由器 + embedding 匹配 + fallback 降级
   - 流式 SSE 透传 + 全链路日志追踪

## 动态调整建议

- **数据充足 / 质量高**：Day 1 可压缩至半天，更多时间投入 Day 4 评估与 Day 6 调优。
- **数据稀缺（< 500 条）**：Day 1 引入 Self-Instruct 自指令生成与数据增强（回译/paraphrasing），Day 4 侧重 Few-shot Prompt 对比。
- **显存不足（单卡 < 16GB）**：Day 2-3 降级 `r=8, alpha=16`，优先探索更小基座模型（Phi-3-mini / Qwen2.5-1.5B），启用 `packing=False`。
- **训练不稳定（Loss 震荡/NaN）**：Day 3 调低 learning_rate 至 1e-5，增大 warmup_ratio 至 0.05，开启 gradient_clipping=1.0，检查数据集中脏样本。
- **后端经验丰富 / 模型部署新手**：Day 5 和 Day 7 放慢节奏，重点理解 GGUF 量化原理与 Agent 工具注册机制。
- **无 Wandb 权限**：使用本地 TensorBoard + CSVLogger 替代，指标手动聚合。
- **Agent 框架不熟悉**：Day 7 优先使用 LangChain `@tool` 装饰器跑通路由，再考虑迁移至 LangGraph 状态机。
- **追求极致推理性能**：Day 5 优先导出 Q4_K_M，Day 7 结合 vLLM PagedAttention 验证并发吞吐。

## 第 7 天自测清单

- [ ] 数据清洗脚本一键运行，输出合法 Alpaca JSON 与分布报告
- [ ] Unsloth 4-bit 加载成功，FA 激活，Dummy 步显存符合预期
- [ ] 训练脚本连续运行无 NaN，Checkpoint 可断点恢复，W&B 曲线平滑
- [ ] PPL 与 QA 评估脚本输出对比报告，领域准确率提升 > 25%
- [ ] merge_and_unload 一致性 > 98%，GGUF 多精度文件可被 ollama/llama.cpp/vLLM 加载
- [ ] Optuna/W&B Sweep 完成 >= 8 轮，LLM 输出归因报告，最优配置固化至 YAML
- [ ] Agent 工具注册成功，意图路由准确率 > 90%，热切换 < 100ms，fallback 稳定
- [ ] 仓库包含：数据脚本、训练配置、评估流水线、GGUF 权重、Agent 路由代码、Sweep 日志
- [ ] 能清晰口述 QLoRA 原理、训练稳定性控制、量化导出流程与 Agent 热切换架构
