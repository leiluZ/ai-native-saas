#!/usr/bin/env python3
"""简单的 Milvus 集成测试脚本"""
import sys
import os

# 添加 src 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import asyncio
import numpy as np

async def test_milvus_store():
    """测试 Milvus 存储功能"""
    from rag.vector_store import VectorStore, VectorRecord

    print("=== Milvus 集成测试 ===")

    # 创建存储实例
    store = VectorStore(collection_name="test_milvus_simple")

    try:
        # 连接
        await store.connect()
        print("✓ 连接成功")

        # 检查存储类型
        if hasattr(store._client, "__class__"):
            class_name = store._client.__class__.__name__
            if class_name == "InMemoryVectorStore":
                print("✗ 使用的是 InMemory 存储，不是 Milvus")
                return False
            print(f"✓ 使用的是 {class_name} 存储")

        # 插入测试数据
        test_vector = np.random.rand(1024).astype(np.float32)
        records = [VectorRecord(
            id="test_milvus_simple_001",
            vector=test_vector,
            text="测试文档内容",
            metadata={"source": "test.txt"}
        )]

        result = await store.insert(records)
        print(f"✓ 插入成功: {result}")

        # 手动加载集合（确保数据可用）
        print("正在加载集合...")
        store._client.load_collection(store.collection_name)

        # 查询验证数据是否存在
        from pymilvus import MilvusClient
        client = MilvusClient("http://milvus:19530")
        query_results = client.query(store.collection_name, "id like '%'", output_fields=["id", "text"])
        print(f"✓ 查询验证: 集合中有 {len(query_results)} 条数据")

        # 执行搜索
        results = await store.search(test_vector, top_k=1)
        print(f"✓ 搜索成功: 找到 {len(results)} 条结果")

        if len(results) > 0:
            print(f"✓ 搜索结果验证通过: {results[0].id}")
        else:
            print("✗ 搜索结果为空")
            return False

        # 清理
        try:
            from pymilvus import MilvusClient
            client = MilvusClient("http://milvus:19530")
            if client.has_collection("test_milvus_simple"):
                client.drop_collection("test_milvus_simple")
                print("✓ 清理测试数据成功")
        except Exception as e:
            print(f"清理数据时出错: {e}")

        return True

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_milvus_store())
    sys.exit(0 if success else 1)
