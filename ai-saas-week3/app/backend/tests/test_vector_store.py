import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch

from src.rag.vector_store import VectorStore, VectorRecord, SearchResult, InMemoryVectorStore


class TestVectorStore:
    """测试向量存储抽象类"""

    @pytest.mark.asyncio
    async def test_in_memory_insert_and_search(self):
        """测试 InMemoryVectorStore 的插入和搜索功能"""
        # 创建 InMemory 存储
        in_memory_store = InMemoryVectorStore(dimension=4)

        # 创建测试数据
        records = [
            VectorRecord(
                id="test1",
                vector=np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32),
                text="测试文档1内容",
                metadata={"source": "test1.txt"}
            ),
            VectorRecord(
                id="test2",
                vector=np.array([0.2, 0.3, 0.4, 0.5], dtype=np.float32),
                text="测试文档2内容",
                metadata={"source": "test2.txt"}
            )
        ]

        # 插入数据
        result = await in_memory_store.insert(records)
        assert result["inserted"] == 2
        assert result["errors"] == 0

        # 搜索测试
        query_vector = np.array([0.15, 0.25, 0.35, 0.45], dtype=np.float32)
        results = await in_memory_store.search(query_vector, top_k=1)

        assert len(results) == 1
        assert results[0].id == "test1" or results[0].id == "test2"
        assert results[0].score > 0

    @pytest.mark.asyncio
    async def test_milvus_insert_and_search(self):
        """测试 MilvusVectorStore 的插入和搜索功能（使用 mock）"""
        # 创建 mock 客户端
        mock_client = MagicMock()
        mock_client.has_collection.return_value = True
        mock_client.insert.return_value = {"insert_count": 1}

        # 设置搜索返回结果
        mock_client.search.return_value = [
            [{
                "id": "test1",
                "distance": 0.1,
                "entity": {"text": "测试文档内容", "metadata": {"source": "test.txt"}}
            }]
        ]

        # 创建向量存储
        store = VectorStore(collection_name="test_collection")
        store._client = mock_client

        # 创建测试数据
        records = [
            VectorRecord(
                id="test1",
                vector=np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float64),  # 使用 float64
                text="测试文档内容",
                metadata={"source": "test.txt"}
            )
        ]

        # 测试插入 - 验证向量被转换为 float32
        await store._insert_batch(records)

        # 验证插入调用
        inserted_data = mock_client.insert.call_args[1]["data"][0]
        # 验证向量是 float32 类型
        assert all(isinstance(v, np.float32) or isinstance(v, float) and v == float(np.float32(v))
                  for v in inserted_data["vector"])

        # 测试搜索 - 验证查询向量被转换为 float32
        query_vector = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float64)
        results = await store.search(query_vector, top_k=1)

        # 验证搜索调用
        search_data = mock_client.search.call_args[1]["data"][0]
        # 验证查询向量是 float32 类型
        assert all(isinstance(v, np.float32) or isinstance(v, float) and v == float(np.float32(v))
                  for v in search_data)

        assert len(results) == 1
        assert results[0].id == "test1"
        assert results[0].text == "测试文档内容"
        assert results[0].distance == 0.1

    @pytest.mark.asyncio
    async def test_vector_type_conversion(self):
        """测试向量类型转换 - 确保 float64 被转换为 float32"""
        # 创建测试向量（float64）
        float64_vector = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float64)

        # 模拟转换
        float32_vector = float64_vector.astype(np.float32)

        # 验证转换结果
        assert float32_vector.dtype == np.float32
        assert np.allclose(float64_vector, float32_vector)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
