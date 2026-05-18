# Week 5: 领域微调与 LoRA 实战

## 🎯 目标
掌握 LoRA/QLoRA 全流程，实现领域增强与热切换。覆盖高质量数据集构建、Unsloth 高效微调、训练稳定性控制、量化评估、权重合并导出、AI 辅助超参寻优及 Agent 工具化注册，最终交付可无缝切换的生产级领域模型。

---

## Day 1：Alpaca 格式数据集构建与清洗
- **目标**：掌握领域数据流水线构建，实现高纯度、结构化微调数据集。
- **实操**：
  1. 收集原始语料（技术文档、工单记录、内部 QA、行业论文等），清洗 HTML/Markdown 噪音、脱敏 PII。
  2. 使用 MinHash/SimHash 或嵌入向量去重，保留高质量样本。
  3. 构造 `{"instruction", "input", "output"}` 或 ChatML 格式，严格校验 JSON Schema。
  4. 划分 Train/Val (85/15)，统计 token 长度分布，过滤极端长/短样本。
- **Prompt 模板**：
```md
编写领域微调数据清洗与格式化流水线，要求：
1. 支持 PDF/DOCX/Markdown/CSV 批量解析，自动提取纯文本
2. LLM 辅助质量打分：逻辑完整性 >0.8、领域相关性 >0.7 方可保留
3. 基于 MinHash + Jaccard 去重，阈值 0.85，支持增量去重缓存
4. 输出标准 Alpaca/ChatML JSON，自动校验 instruction/input/output 非空
5. 生成数据分布报告：样本数、平均长度、领域标签占比、Token 分布直方图
6. 自动划分 train/val，支持 seed 固定与比例可调
```
- **验收**：
  - ✅ 有效样本 >10k，格式 100% 合法
  - ✅ 去重率 >30%，PII 零残留
  - ✅ 长度分布合理（90% 样本 512~2048 tokens）
  - ✅ 数据分布报告与可视化完整

---

## Day 2：Unsloth + QLoRA (4-bit) + FlashAttention 配置
- **目标**：搭建低显存、高吞吐微调环境，掌握 4-bit 量化加载与注意力加速。
- **实操**：
  1. 安装 `unsloth`，加载基座模型（如 Qwen2.5-7B/14B-Instruct）至 `nf4` 精度。
  2. 配置 LoRA 适配器：`r=16/32`, `alpha=32/64`, `target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"]`。
  3. 启用 `FlashAttention-2/3`，验证 kernel 激活状态。
  4. 运行 dummy forward/backward，监控显存占用与梯度形状，确保无 OOM。
- **Prompt 模板**：
```md
构建 Unsloth QLoRA 微调初始化环境，要求：
1. 使用 unsloth.AutoModelForCausalLM 加载 4-bit nf4 基座，双精度 bfloat16
2. 自动注入 LoRA 配置：r, alpha, dropout, bias=none, target_modules 全覆盖
3. 强制启用 FlashAttention-2/3，输出 attn_implementation 验证日志
4. 运行 1 步 dummy training，打印 VRAM 峰值、梯度范数、激活内存
5. 提供 config.yaml 管理基座路径、量化策略、LoRA 参数
6. 兼容 TRL SFTTrainer 与 Accelerate 分布式配置
```
- **验收**：
  - ✅ 模型加载显存 <8GB (7B) / <14GB (14B)
  - ✅ LoRA 注入成功，FA 状态为 `enabled`
  - ✅ Dummy 步无 OOM，梯度范数正常
  - ✅ 配置支持热切换与版本管理

---

## Day 3：训练循环 (LR 调度 / Gradient Checkpoint / Checkpoint)
- **目标**：实现稳定可恢复的训练流程，掌握显存优化与调度策略。
- **实操**：
  1. 配置 `SFTTrainer`：`max_steps`、`per_device_train_batch_size`、`gradient_accumulation_steps`。
  2. 启用 `gradient_checkpointing`，设置 `learning_rate`、`warmup_ratio`、`lr_scheduler_type="cosine"`。
  3. 配置 Checkpoint 策略：`save_steps`、`save_total_limit`、`metric_for_best_model`。
  4. 集成 W&B/TensorBoard，监控 Loss、Grad Norm、LR；内置 NaN 检测与自动回滚逻辑。
- **Prompt 模板**：
```md
编写生产级 LoRA 训练循环脚本，要求：
1. TRL SFTTrainer 完整配置：max_steps, grad_accum, max_seq_length, packing=True
2. LR 调度：cosine + warmup_ratio=0.03，支持 linear/warmup_stable_decay
3. 开启 gradient_checkpointing 与 fp16/bf16 mixed precision
4. 每 1000 step 保存 checkpoint，仅保留 top 3 最佳模型（按 val_loss）
5. 集成 W&B 日志：loss, lr, grad_norm, throughput(samples/s), VRAM
6. 内置 NaN 防护：检测 loss=NaN 自动跳过 batch 并记录警告，连续 3 次触发 early_stop
7. 支持 resume_from_checkpoint 断点续训
```
- **验收**：
  - ✅ Loss 曲线平滑下降，无 NaN/梯度爆炸
  - ✅ Checkpoint 自动保存与清理，断点续训验证通过
  - ✅ 显存峰值稳定，利用率 >75%
  - ✅ W&B 面板实时更新训练指标

---

## Day 4：Perplexity & 领域 QA 对比评估
- **目标**：量化微调效果，构建基线与微调模型的客观对比体系。
- **实操**：
  1. 在 Val 集计算 PPL（Baseline vs QLoRA），验证语言建模能力。
  2. 构建领域 QA Benchmark（500+ 题），运行 Baseline 与微调模型生成。
  3. 计算 EM (Exact Match)、F1、ROUGE-L，人工抽检 10% 标注 hallucination 率。
  4. 生成对比报告：指标提升热力图、错误类型分布（事实错误/逻辑断裂/格式不符）。
- **Prompt 模板**：
```md
构建领域微调评估与对比流水线，要求：
1. 自动加载 val 集与 baseline/fine-tuned 模型，计算跨样本 Perplexity
2. 运行领域 QA 测试集：支持 streaming 生成，记录 token 耗时与显存
3. 自动计算 EM、F1、ROUGE-L，输出 macro/micro 平均
4. LLM 辅助错误分析：按事实错误、格式错误、过度自信分类统计
5. 生成 Markdown 评估报告 + CSV 明细，附指标提升对比图
6. 支持多模型并行评测，结果自动聚合至 leaderboard.csv
```
- **验收**：
  - ✅ PPL 下降 >15%
  - ✅ 领域 QA 准确率提升 >25%（EM/F1 综合）
  - ✅ Hallucination 率下降 >30%
  - ✅ 评估报告结构完整，可复现

---

## Day 5：权重合并 (merge_and_unload) + GGUF/FP16 转换
- **目标**：完成适配器权重合并，导出生产可用格式并验证一致性。
- **实操**：
  1. 使用 `model.merge_and_unload()` 融合 LoRA 权重，导出 BF16/FP16 完整模型。
  2. 使用 `llama.cpp` 转换管线导出 GGUF，支持 `Q4_K_M`、`Q5_K_S`、`Q8_0` 多精度。
  3. 运行一致性测试：相同 prompt 对比 adapter推理、merge推理、GGUF推理 的 logprobs 与输出文本。
  4. 验证 vLLM/Ollama 加载兼容性，记录冷启动时间与首字延迟。
- **Prompt 模板**：
```md
编写模型权重合并与 GGUF 转换流水线，要求：
1. 执行 merge_and_unload，输出完整权重至独立目录
2. 调用 llama.cpp convert 脚本，自动生成 Q4/Q5/Q8 GGUF 文件
3. 一致性验证：随机抽取 50 条 prompt，对比 merge/GGUF 输出的 token 序列重合度 >98%
4. 自动注册至 vLLM/Ollama 模型库，验证 /v1/models 接口可见
5. 输出转换报告：文件大小、量化损耗、冷启动时间、TTFT 对比
6. 支持回滚：保留原始 checkpoint 与 adapter 权重
```
- **验收**：
  - ✅ 合并后模型与 adapter 推理一致性 >98%
  - ✅ GGUF 多精度文件生成完整，可通过 `llama-cli` 验证
  - ✅ 量化精度损耗 <2%（PPL 增幅）
  - ✅ vLLM/Ollama 无缝加载，冷启动 <10s

---

## Day 6：AI 辅助网格搜索超参调优
- **目标**：通过自动化寻优与 LLM 分析闭环，定位最优训练配置。
- **实操**：
  1. 定义搜索空间：`r∈[8,16,32]`, `alpha∈[16,32,64]`, `dropout∈[0.0,0.05,0.1]`, `lr∈[1e-5, 2e-5, 5e-5]`, `epochs∈[2,3,4]`。
  2. 使用 Optuna/W&B Sweep 自动调度，记录每轮 val_loss、QA_acc、训练耗时。
  3. 将 Sweep 结果输入 LLM，生成归因分析与下一轮建议。
  4. 输出 Top-3 配置对比，固化最优参数至 `config_best.yaml`。
- **Prompt 模板**：
```md
构建 AI 辅助超参寻优流水线，要求：
1. Optuna 网格/贝叶斯搜索：覆盖 LoRA r/alpha/dropout、LR、batch_size、epochs
2. 每轮训练自动上报 W&B，记录 val_loss、QA_EM、GPU_util、耗时
3. LLM 分析模块：输入 JSON 结果，输出瓶颈归因（如过拟合/欠拟合/显存瓶颈）
4. 自动生成下一轮建议：参数调整方向、预期收益、风险提示
5. 输出 Top-3 配置对比表 + 参数重要性排序图 (SHAP/Permutation)
6. 支持 early_pruning：连续 2 轮无改善自动终止该 trial
```
- **验收**：
  - ✅ 完成 ≥8 组有效 Sweep
  - ✅ 最优配置较 Baseline QA 提升 >10%
  - ✅ LLM 归因报告可解释、可执行
  - ✅ 固化 `config_best.yaml` 并验证复现性

---

## Day 7：微调模型注册为 Agent 专用工具
- **目标**：将领域模型封装为 Agent 工具，实现意图路由与热切换。
- **实操**：
  1. 定义 Tool Schema：`name`, `description`, `input_schema`, `output_format`。
  2. 集成 LangGraph / LlamaIndex / 自研 Router，实现意图识别后动态路由至微调模型。
  3. 实现热切换逻辑：基座与领域模型双加载，根据上下文/成本阈值自动 fallback。
  4. 端到端测试：复杂多轮对话、工具调用链、延迟监控、降级验证。
- **Prompt 模板**：
```md
实现 Agent 领域工具注册与热切换路由，要求：
1. 定义标准 Tool Schema，兼容 OpenAI function calling 规范
2. 实现意图路由器：基于 embedding 相似度 + 关键词匹配，阈值可配
3. 热切换逻辑：优先路由至 QLoRA 合并模型，超时/高成本/拒识时 fallback 至基座
4. 支持流式响应透传，保持 SSE 格式不中断
5. 全量日志：记录路由决策、模型响应时间、工具调用成功率
6. 提供 /admin/agent-tools 调试面板：支持手动切换、压测、日志追溯
7. 单元测试覆盖：正常路由、降级触发、并发冲突、Schema 校验
```
- **验收**：
  - ✅ Agent 无缝调用领域工具，Function Calling 解析率 100%
  - ✅ 热切换延迟 <100ms，fallback 机制稳定
  - ✅ 领域任务由微调模型处理准确率 >90%
  - ✅ 路由日志完整，支持全链路追溯

---

## 每日验收标准

| Day | 验收条件 |
|-----|---------|
| D1 | 有效样本 >10k，格式 100% 合法；去重率 >30%；数据分布报告完整 |
| D2 | 7B 模型加载显存 <8GB；LoRA 注入成功；FA 激活；Dummy 步无 OOM |
| D3 | Loss 平滑无 NaN；Checkpoint 自动保存；断点续训验证通过；VRAM 稳定 |
| D4 | PPL 下降 >15%；领域 QA 准确率提升 >25%；Hallucination 率下降 >30% |
| D5 | 合并一致性 >98%；GGUF 多精度生成完整；vLLM/Ollama 加载验证通过 |
| D6 | 完成 ≥8 组 Sweep；最优配置提升 >10%；LLM 归因报告可执行；配置固化 |
| D7 | Agent 路由解析率 100%；热切换 <100ms；fallback 稳定；全链路日志可审计 |

---

## 最终验收标准
- ✅ 训练 Loss 平稳无 NaN，Checkpoint 可完整恢复
- ✅ 领域 QA 准确率提升 >25%，PPL 显著下降
- ✅ GGUF 多精度导出一致，兼容主流推理引擎
- ✅ AI 辅助超参寻优输出可复现最优配置
- ✅ 微调模型注册为 Agent 专用工具，热切换延迟 <100ms，无缝降级
- ✅ 完整交付物：数据清洗脚本、训练配置、评估报告、GGUF 权重、Agent 路由代码、Sweep 日志

---

## 高频 Prompt 模板
1. **领域数据清洗与 Alpaca 格式化 Prompt**
   - 支持多格式解析与 LLM 质量打分
   - MinHash 去重与长度过滤
   - 自动划分 train/val 与分布报告生成

2. **Unsloth QLoRA 环境初始化 Prompt**
   - 4-bit nf4 加载与 bfloat16 精度对齐
   - LoRA 参数全覆盖注入与 FA 强制启用
   - Dummy 步显存与梯度验证

3. **生产级训练循环与稳定性控制 Prompt**
   - SFTTrainer 完整配置与 gradient checkpointing
   - Cosine LR 调度与 warmup
   - NaN 防护、断点续训与 W&B 集成

4. **PPL 与领域 QA 对比评估 Prompt**
   - 跨模型 PPL 计算与流式生成压测
   - EM/F1/ROUGE-L 自动统计
   - LLM 辅助错误分类与可视化报告

5. **权重合并与 GGUF 导出流水线 Prompt**
   - merge_and_unload 与 llama.cpp 转换
   - 一致性验证与量化损耗评估
   - vLLM/Ollama 兼容性测试

6. **AI 辅助超参网格寻优 Prompt**
   - Optuna/W&B 自动调度与 early_pruning
   - LLM 归因分析与下一轮建议生成
   - Top-3 配置对比与重要性排序

7. **Agent 工具注册与热切换路由 Prompt**
   - OpenAI 兼容 Tool Schema 定义
   - 意图路由器与 fallback 降级逻辑
   - 流式透传与全链路日志追踪

---

## 动态调整建议
- **显存受限 (单卡 <12GB)**：
  - D2 降级 `r=8, alpha=16`，启用 `gradient_accumulation_steps=4`
  - D3 使用 `unsloth` 的 `packing=False` 降低激活内存
- **数据稀缺 (<5k 样本)**：
  - D1 引入自指令生成 (Self-Instruct) 与数据增强 (回译/ paraphrasing)
  - D4 侧重 Few-shot Prompt 对比，避免过拟合评估
- **训练不稳定 (Loss 震荡/NaN)**：
  - D3 调低 `learning_rate` 至 1e-5，增大 `warmup_ratio` 至 0.05
  - 开启 `gradient_clipping=1.0`，检查数据集中脏样本
- **无 W&B/MLflow 权限**：
  - 使用本地 `TensorBoard` + `CSVLogger`，指标手动聚合
- **Agent 框架不熟悉**：
  - 优先使用 `LangChain` 的 `@tool` 装饰器跑通路由，再迁移至 `LangGraph` 状态机
- **追求极致推理性能**：
  - D5 优先导出 `Q4_K_M`，D7 结合 vLLM PagedAttention 验证并发吞吐

---

## 第 7 天自测清单
- [ ] 数据清洗脚本一键运行，输出合法 Alpaca JSON 与分布报告
- [ ] Unsloth 4-bit 加载成功，FA 激活，Dummy 步显存符合预期
- [ ] 训练脚本连续运行无 NaN，Checkpoint 可断点恢复，W&B 曲线平滑
- [ ] PPL 与 QA 评估脚本输出对比报告，领域准确率提升 >25%
- [ ] `merge_and_unload` 一致性 >98%，GGUF 多精度文件生成且可被 llama.cpp/vLLM 加载
- [ ] Optuna Sweep 完成 ≥8 轮，LLM 输出归因报告，最优配置固化至 YAML
- [ ] Agent 工具注册成功，意图路由准确率 >90%，热切换延迟 <100ms，fallback 稳定
- [ ] 仓库包含：数据脚本、训练配置、评估流水线、GGUF 权重、Agent 路由代码、Sweep 日志、部署文档
- [ ] 能清晰口述 QLoRA 原理、训练稳定性控制、量化导出流程与 Agent 热切换架构
