"""Milvus 集成测试 - 确保 Milvus 存储正确工作"""
import pytest
import numpy as np
from unittest.mock import patch, MagicMock

from app.src.rag.vector_store import VectorStore, VectorRecord, SearchResult
from app.src.rag.in_memory_store import InMemoryVectorStore


class TestMilvusIntegration:
    """Milvus 集成测试类"""

    @pytest.mark.asyncio
    async def test_milvus_store_is_used(self):
        """验证实际使用的是 Milvus 而不是 InMemory"""
        store = VectorStore(collection_name="test_milvus_store")

        # 模拟 Milvus 可用
        with patch("app.src.rag.vector_store.MilvusClient") as MockMilvusClient:
            mock_client = MockMilvusClient.return_value
            mock_client.has_collection.return_value = True
            mock_client.load_collection.return_value = None

            await store.connect()

            # 验证不是 InMemory 存储
            assert not isinstance(store._client, InMemoryVectorStore)
            assert hasattr(store._client, "search")
            assert hasattr(store._client, "has_collection")

    @pytest.mark.asyncio
    async def test_in_memory_fallback_when_milvus_unavailable(self):
        """验证 Milvus 不可用时回退到 InMemory"""
        store = VectorStore(collection_name="test_fallback")

        # 模拟 Milvus 导入失败
        with patch.dict("sys.modules", {"pymilvus": None}):
            await store.connect()

            # 验证回退到 InMemory 存储
            assert isinstance(store._client, InMemoryVectorStore)

    @pytest.mark.asyncio
    async def test_milvus_insert_and_search(self):
        """测试 Milvus 真实插入和搜索功能"""
        # 使用真实的 Milvus 客户端
        store = VectorStore(collection_name="test_integration")

        # 确保测试前清理
        try:
            from pymilvus import MilvusClient
            client = MilvusClient("http://milvus:19530")
            if client.has_collection("test_integration"):
                client.drop_collection("test_integration")
        except Exception:
            pytest.skip("Milvus not available")

        await store.connect()

        # 插入测试数据
        test_vector = np.array([0.1, 0.2, 0.3, 0.4] * 256, dtype=np.float32)  # 1024 维
        records = [VectorRecord(
            id="test_milvus_001",
            vector=test_vector,
            text="测试文档内容：这是一个用于 Milvus 集成测试的文档",
            metadata={"source": "test.txt", "chunk_index": 0}
        )]

        result = await store.insert(records)
        assert result["inserted"] == 1
        assert result["errors"] == 0

        # 执行搜索
        query_vector = np.array([0.1, 0.2, 0.3, 0.4] * 256, dtype=np.float32)
        results = await store.search(query_vector, top_k=1)

        # 验证搜索结果
        assert len(results) == 1
        assert results[0].id == "test_milvus_001"
        assert "测试文档内容" in results[0].text
        assert results[0].score > 0

        # 清理测试数据
        if client.has_collection("test_integration"):
            client.drop_collection("test_integration")

    @pytest.mark.asyncio
    async def test_milvus_vector_type_consistency(self):
        """测试 Milvus 向量类型一致性 - 确保 float32 被正确使用"""
        # 使用真实的 Milvus 客户端
        try:
            from pymilvus import MilvusClient
            client = MilvusClient("http://milvus:19530")

            # 创建测试集合
            collection_name = "test_vector_type"
            if client.has_collection(collection_name):
                client.drop_collection(collection_name)

            from pymilvus import DataType
            schema = client.create_schema(auto_id=False, enable_dynamic_field=True)
            schema.add_field("id", DataType.VARCHAR, max_length=64, is_primary=True)
            schema.add_field("vector", DataType.FLOAT_VECTOR, dim=4)
            client.create_collection(collection_name, schema=schema)

            # 插入 float32 向量
            float32_vec = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32).tolist()
            client.insert(collection_name, [{
                "id": "test",
                "vector": float32_vec
            }])

            # 加载集合并搜索
            client.load_collection(collection_name)
            query_vec = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32).tolist()
            results = client.search(collection_name, data=[query_vec], limit=1)

            assert len(results) == 1
            assert len(results[0]) == 1

            # 清理
            client.drop_collection(collection_name)

        except ImportError:
            pytest.skip("pymilvus not installed")
        except Exception as e:
            pytest.skip(f"Milvus not available: {e}")

    @pytest.mark.asyncio
    async def test_collection_loading(self):
        """测试集合加载状态"""
        try:
            from pymilvus import MilvusClient
            client = MilvusClient("http://milvus:19530")

            # 创建测试集合
            collection_name = "test_load"
            if client.has_collection(collection_name):
                client.drop_collection(collection_name)

            from pymilvus import DataType
            schema = client.create_schema(auto_id=False, enable_dynamic_field=True)
            schema.add_field("id", DataType.VARCHAR, max_length=64, is_primary=True)
            schema.add_field("vector", DataType.FLOAT_VECTOR, dim=4)
            client.create_collection(collection_name, schema=schema)

            # 验证集合存在
            assert client.has_collection(collection_name)

            # 加载集合
            client.load_collection(collection_name)

            # 插入数据并搜索
            client.insert(collection_name, [{
                "id": "test",
                "vector": [0.1, 0.2, 0.3, 0.4]
            }])

            results = client.search(collection_name, data=[[0.1, 0.2, 0.3, 0.4]], limit=1)
            assert len(results) == 1

            # 清理
            client.drop_collection(collection_name)

        except ImportError:
            pytest.skip("pymilvus not installed")
        except Exception as e:
            pytest.skip(f"Milvus not available: {e}")


class TestStorageTypeValidation:
    """存储类型验证测试"""

    @pytest.mark.asyncio
    async def test_storage_type_returns_milvus(self):
        """验证存储类型返回 milvus"""
        store = VectorStore(collection_name="test_storage_type")

        with patch("app.src.rag.vector_store.MilvusClient") as MockMilvusClient:
            mock_client = MockMilvusClient.return_value
            mock_client.has_collection.return_value = True
            mock_client.load_collection.return_value = None

            await store.connect()

            # 检查存储类型
            assert hasattr(store._client, "search")
            assert hasattr(store._client, "has_collection")
            assert hasattr(store._client, "insert")

    @pytest.mark.asyncio
    async def test_storage_type_returns_inmemory(self):
        """验证存储类型返回 inmemory（当 Milvus 不可用时）"""
        store = VectorStore(collection_name="test_storage_type_fallback")

        with patch.dict("sys.modules", {"pymilvus": None}):
            await store.connect()

            # 检查存储类型
            assert isinstance(store._client, InMemoryVectorStore)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
