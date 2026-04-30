# Week 3: RAG 管道构建与检索评估

## 🎯 目标
构建生产级 RAG，掌握分块、混合检索、重排与自动化评估闭环。

## 🛠️ 每日实操
- D1: 文档解析 (Unstructured/PyPDF) + 清洗
- D2: 智能分块 (段落/标题/Token 重叠)
- D3: Embedding (BGE-M3) + Milvus/Chroma 索引
- D4: 混合检索 (BM25+向量) + Cross-Encoder Rerank
- D5: RAGAS 评估 (Faithfulness/Relevance/Context Precision)
- D6: 基于 RAGAS 分数自动调优 chunk_size/rerank 阈值
- D7: 集成 `rag_search` 工具至 Agent 管道

## ✅ 验收标准
- Rerank 后 Top-3 命中率提升 >30%
- RAGAS 一键输出评估报告
- Agent 返回带引用的结构化答案
