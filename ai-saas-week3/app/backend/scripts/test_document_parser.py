import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.rag import DocumentParser, ChunkManager


async def main():
    """测试文档解析管道"""
    parser = DocumentParser()
    chunk_manager = ChunkManager(chunk_size=512, overlap_ratio=0.15)

    # 创建测试文档目录
    test_docs_dir = "test_docs"
    os.makedirs(test_docs_dir, exist_ok=True)

    # 创建测试文档
    test_files = []

    # 创建测试 Markdown 文件
    md_file = os.path.join(test_docs_dir, "test.md")
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write("# 测试文档\n\n## 第一章 介绍\n\n这是一个测试文档，用于验证文档解析管道的功能。\n\n### 1.1 项目概述\n\n本项目旨在构建生产级 RAG 系统，支持多格式文档解析。\n\n## 第二章 功能特性\n\n- 支持 PDF/DOCX/HTML/Markdown 格式\n- 异步并发解析\n- 自动清洗和去重\n- 智能分块策略\n\n---\nPage 1 of 10\n---\n\n## 第三章 技术栈\n\n使用 FastAPI + LangChain + LangGraph 构建。")
    test_files.append(md_file)

    # 创建测试文本文件
    txt_file = os.path.join(test_docs_dir, "readme.txt")
    with open(txt_file, 'w', encoding='utf-8') as f:
        f.write("项目说明\n========\n\n本项目是一个文档解析管道的测试示例。\n\n功能列表:\n1. 文档解析\n2. 内容清洗\n3. 智能分块\n4. 向量索引\n\n2024-01-15")
    test_files.append(txt_file)

    print("=== 开始测试文档解析 ===")
    results = await parser.parse_files(test_files)

    print(f"\n成功解析: {len(results['success'])} 个文件")
    print(f"解析失败: {len(results['errors'])} 个文件")

    for doc in results['success']:
        print(f"\n--- {doc['metadata']['source']} ---")
        print(f"MIME 类型: {doc['metadata']['mime_type']}")
        print(f"内容长度: {len(doc['content'])} 字符")
        print(f"前200字符: {doc['content'][:200]}...")

    # 测试分块功能
    if results['success']:
        print("\n=== 测试智能分块 ===")
        content = results['success'][0]['content']
        source = results['success'][0]['metadata']['source']

        for strategy in ['fixed', 'recursive', 'header_aware']:
            chunks = chunk_manager.chunk_document(content, source, strategy=strategy)
            stats = chunk_manager.get_chunk_stats(chunks)

            print(f"\n策略: {strategy}")
            print(f"总分块: {stats['total_chunks']}")
            print(f"平均 Token: {stats['avg_tokens']}")
            print(f"P95 Token: {stats['p95_tokens']}")

            # 导出分块结果
            chunk_manager.export_chunks(chunks, f"output/chunks_{strategy}.jsonl")
            print(f"分块已导出到 output/chunks_{strategy}.jsonl")

    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    asyncio.run(main())
