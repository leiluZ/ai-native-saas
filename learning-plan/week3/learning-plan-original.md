# Week 3: 生产级 RAG 管道构建与检索评估实战

## 🎯 目标
构建生产级 RAG，掌握文档解析、智能分块、混合检索、重排与自动化评估闭环，最终集成至 LangGraph Agent 管道。

---

## Day 1：文档解析与清洗流水线

- **目标**：掌握多格式文档提取、表格/OCR 解析与噪声清洗，构建可复用的 ETL 管道。
- **实操**：
  1. 安装 `unstructured`, `pypdf`, `pdfplumber`，配置 OCR 引擎（Tesseract/PaddleOCR）。
  2. 编写异步解析器：自动路由 PDF/DOCX/HTML/Markdown 格式。
  3. 实现清洗规则：去除页眉页脚、修复乱码、扁平化嵌套表格、统一 Unicode 编码。
  4. 输出结构化 JSONL（含 `source`, `page`, `section`, `content`）。
- **Prompt 模板**：

```md
构建生产级文档解析管道，要求：
1. 使用 async def，支持并发解析 + tqdm 进度条
2. 自动识别文件 MIME 类型并路由对应解析器
3. 清洗后内容需去除多余空白/页码/水印占位符，表格转为 Markdown 格式
4. 失败文件记录至 error_log.json，不中断整体流程
5. 输出统一 Pydantic 模型：ParsedDocument(content, metadata)
```

- **验收**：10+ 混合格式文档解析成功率 >95%；清洗后文本无冗余字符；错误文件可追溯。

---

## Day 2：智能分块策略实现

- **目标**：理解分块粒度对召回的影响，实现语义/结构/Token 重叠分块算法。
- **实操**：
  1. 实现 3 种分块器：固定字符长度、递归字符（按 `\n\n`, `.`, ` `）、标题感知（Header-aware）。
  2. 添加 10%~20% Token 重叠，保留上下文边界。
  3. 计算并统计分块分布：平均长度、P95、重叠率。
  4. 导出分块结果至 JSONL，带完整元数据。
- **Prompt 模板**：

```md
实现可配置的智能分块器，要求：
1. 支持 chunk_size, overlap_ratio, strategy 参数热切换
2. 标题感知分块需保留 H1/H2 层级至 metadata["heading"]
3. 使用 tiktoken 精确计算 Token 数，非字符数
4. 重叠部分需做去重哈希校验，避免重复入库
5. 附单元测试：验证边界条件（空文档/单字符/超长段落）
```

- **验收**：分块策略可配置切换；Token 计数准确；重叠逻辑无误；输出带层级元数据。

---

## Day 3：Embedding 与向量索引构建

- **目标**：掌握 BGE-M3 多语言 Embedding，构建 Milvus/Chroma 高效向量索引。
- **实操**：
  1. 加载 `BAAI/bge-m3`，封装异步 Embedding Service。
  2. 初始化 Chroma/Milvus Collection，定义 Schema（id, vector, metadata）。
  3. 批量插入分块数据，实现断点续传与指数退避重试。
  4. 验证基础 Cosine Similarity 查询与过滤条件（metadata filtering）。
- **Prompt 模板**：

```md
封装 Embedding 与向量数据库服务，要求：
1. BGE-M3 使用 ONNX 推理加速，支持 CPU/GPU 自动降级
2. 批量插入实现 chunk_size=500 异步并发，带 exponential backoff 重试
3. 向量索引配置：HNSW / IVF_FLAT，M=16, ef_construction=200
4. 查询接口支持 metadata 过滤 + top_k + 距离阈值
5. 所有 DB 连接池化，lifespan 管理启停
```

- **验收**：10k 分块入库 < 2min；相似查询返回延迟 < 100ms；连接池无泄漏；支持元数据过滤。

---

## Day 4：混合检索与 Cross-Encoder 重排

- **目标**：突破单一向量检索瓶颈，实现 BM25 + 向量融合 + 精排闭环。
- **实操**：
  1. 实现 BM25 检索（基于 `rank-bm25` 或 DB 原生全文索引）。
  2. 设计分数融合策略：RRF（Reciprocal Rank Fusion）或加权线性融合。
  3. 接入 `BGE-Reranker-Large`，对 Top-50 候选进行 Cross-Encoder 精排。
  4. 对比基线 vs 混合 vs 重排 Top-K 命中率。
- **Prompt 模板**：

```md
构建混合检索与重排管道，要求：
1. 实现 RRF 融合公式：score = Σ 1/(k + rank)，k=60
2. Reranker 异步调用，超时 800ms 自动 fallback 至向量结果
3. 缓存重排结果（Redis TTL 1h），避免重复计算
4. 返回统一结构：[ {doc_id, score, content, source, rerank_score} ]
5. 附性能压测脚本：QPS=50 下的 P99 延迟与命中率
```

- **验收**：Rerank 后 Top-3 命中率较基线提升 >30%；P99 延迟 < 1.2s；超时降级不崩溃。

---

## Day 5：RAGAS 自动化评估闭环

- **目标**：建立量化评估体系，自动化计算 Faithfulness / Answer Relevance / Context Precision。
- **实操**：
  1. 构造测试集：50+ 问答对（含 ground_truth 与人工标注上下文）。
  2. 配置 RAGAS `EvaluationDataset`，对接本地/云端 LLM 作为 Judge。
  3. 运行 `evaluate()`，解析指标并生成 Markdown/HTML 报告。
  4. 实现评估流水线与 CI 集成（可选 GitHub Actions）。
- **Prompt 模板**：

```md
实现 RAGAS 一键评估脚本，要求：
1. 自动从 test_set.json 加载问题/答案/上下文
2. Judge LLM 使用本地 vLLM 或 OpenAI，支持 rate limit 自动重试
3. 输出指标：faithfulness, answer_relevance, context_precision
4. 报告含分数分布、低分样本溯源、改进建议
5. 评估结果写入 SQLite，支持历史版本对比
```

- **验收**：`python run_eval.py` 一键输出评估报告；3 项核心指标完整；低分样本可定位溯源。

---

## Day 6：基于评估分数的自动调优

- **目标**：用数据驱动参数寻优，自动化调整 chunk_size 与 rerank 阈值。
- **实操**：
  1. 定义参数网格：`chunk_size` [256, 512, 1024], `overlap` [10%, 20%], `rerank_threshold` [0.7, 0.8, 0.9]。
  2. 编写自动调优循环：跑管道 → RAGAS 评估 → 记录分数 → 寻优。
  3. 引入早停策略与并行化（`concurrent.futures` / `asyncio.gather`）。
  4. 输出最优配置至 `config.yaml`，附对比雷达图。
- **Prompt 模板**：

```md
构建 RAG 参数自动调优器，要求：
1. 参数网格遍历使用 itertools.product，支持随机采样降维
2. 并发执行 3 组配置，日志记录至 CSV（含耗时/显存/分数）
3. 目标函数：加权综合分 = 0.4*faithfulness + 0.4*relevance + 0.2*precision
4. 达到阈值或连续 2 轮无提升则早停
5. 输出最佳配置 YAML + 分数对比图表（matplotlib/plotly）
```

- **验收**：自动调优器找到最优组合；综合分较默认配置提升 ≥15%；输出可复现的配置与图表。

---

## Day 7：集成 `rag_search` 至 Agent 管道

- **目标**：将 RAG 管道封装为工具，无缝接入 LangGraph Agent，输出带引用的结构化答案。
- **实操**：
  1. 使用 `@tool` 封装 `rag_search(query, top_k, rerank)`。
  2. 在 LangGraph 中注册工具，配置条件路由（检索 vs 直接回答）。
  3. 强制 System Prompt 要求带引用格式：`[1](source_url)`。
  4. 对接 `langgraph dev`，测试流式输出与错误降级。
- **Prompt 模板**：

```md
将 RAG 管道封装为 LangGraph 工具并集成至 Agent，要求：
1. 工具定义含完整 Pydantic schema，支持 query, filters, top_k
2. Agent 决策逻辑：知识型问题 → 调用 rag_search；闲聊/计算 → 直接回答
3. 返回结果强制附加引用 ID，缺失引用时标记置信度 low
4. 工具调用失败返回人类可读提示，不抛出裸异常
5. 适配 langgraph dev 热重载，支持流式 chunk 输出
```

- **验收**：Agent 返回带引用的结构化 JSON；RAGAS 指标在 Agent 链路中保持；`langgraph dev` 调试无阻塞。

---

## 每日验收标准

| Day | 验收条件 |
|-----|---------|
| D1 | 10+ 混合格式文档解析成功率 >95%；清洗后文本无冗余字符；错误文件可追溯 |
| D2 | 分块策略可配置切换；Token 计数准确；重叠逻辑无误；输出带层级元数据 |
| D3 | 10k 分块入库 < 2min；相似查询返回延迟 < 100ms；连接池无泄漏；支持元数据过滤 |
| D4 | Rerank 后 Top-3 命中率较基线提升 >30%；P99 延迟 < 1.2s；超时降级不崩溃 |
| D5 | `python run_eval.py` 一键输出评估报告；3 项核心指标完整；低分样本可定位溯源 |
| D6 | 自动调优器找到最优组合；综合分较默认配置提升 ≥15%；输出可复现的配置与图表 |
| D7 | Agent 返回带引用的结构化 JSON；RAGAS 指标在 Agent 链路中保持；`langgraph dev` 调试无阻塞 |

## 最终验收标准

- Rerank 后 Top-3 命中率提升 >30%
- RAGAS 一键输出评估报告
- Agent 返回带引用的结构化答案
- 自动调优找到最优参数组合，综合分较默认提升 ≥15%
- 混合检索 P99 延迟 < 1.2s，超时降级不崩溃
- 10k 级分块入库 < 2min，查询延迟 < 100ms

## 高频 Prompt 模板（占位）

1. 文档解析清洗 Prompt
2. 智能分块策略 Prompt
3. 混合检索与重排 Prompt
4. RAGAS 评估与调优 Prompt
5. Agent RAG 工具集成 Prompt

## 动态调整建议

- 无 NLP 基础：Day 2 放慢节奏，先理解 chunk 对召回率的影响，再动手实现。
- 无向量数据库经验：Day 3 优先使用 Chroma（轻量），再迁移至 Milvus。
- 无评估经验：Day 5 先理解 RAGAS 指标含义，再构造测试集。
- 无 LangGraph 经验：Day 7 参考 Week 2 的 LangGraph 基础，先跑通单工具调用。

## 第 7 天自测清单

- [ ] `docker-compose up` 跑通解析 + 分块 + Embedding + 检索 + 评估全链路
- [ ] Rerank 后 Top-3 命中率较纯向量检索提升 >30%
- [ ] `python run_eval.py` 一键输出 RAGAS 报告，faithfulness > 0.8
- [ ] 自动调优器找到最优 chunk_size + overlap + rerank_threshold 组合
- [ ] Agent 调用 `rag_search` 返回带 `[1](source_url)` 引用的结构化答案
- [ ] pytest 覆盖率 >= 75%，无 lint 报错
- [ ] GitHub 仓库含架构图、运行命令、Prompt 库、2 分钟 Demo
