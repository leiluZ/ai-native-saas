import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from src.rag.vector_store import VectorStore, VectorRecord, SearchResult, InMemoryVectorStore


class TestVectorStore:
    """向量数据库服务测试"""

    @pytest.fixture
    def vector_store(self):
        return VectorStore(
            collection_name="test_collection",
            dimension=1024,
            index_type="HNSW",
        )

    @pytest.fixture
    def sample_records(self):
        """创建测试记录"""
        return [
            VectorRecord(
                id="doc1",
                vector=np.random.randn(1024).astype(np.float32),
                text="测试文档1",
                metadata={"source": "test", "category": "A"},
            ),
            VectorRecord(
                id="doc2",
                vector=np.random.randn(1024).astype(np.float32),
                text="测试文档2",
                metadata={"source": "test", "category": "B"},
            ),
            VectorRecord(
                id="doc3",
                vector=np.random.randn(1024).astype(np.float32),
                text="测试文档3",
                metadata={"source": "prod", "category": "A"},
            ),
        ]

    @pytest.mark.asyncio
    async def test_insert_single_batch(self, vector_store, sample_records):
        """测试单批次插入"""
        with patch.object(vector_store, '_insert_batch') as mock_insert:
            mock_insert.return_value = None

            result = await vector_store.insert(sample_records, batch_size=10)
            assert result["inserted"] == 3
            assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_insert_multiple_batches(self, vector_store, sample_records):
        """测试多批次插入"""
        with patch.object(vector_store, '_insert_batch') as mock_insert:
            mock_insert.return_value = None

            result = await vector_store.insert(sample_records, batch_size=2)
            assert result["inserted"] == 3
            assert mock_insert.call_count == 2  # 2 + 1 = 2 batches

    @pytest.mark.asyncio
    async def test_insert_with_retry(self, vector_store, sample_records):
        """测试插入重试"""
        with patch.object(vector_store, '_insert_batch') as mock_insert:
            # 第一次失败，第二次成功
            mock_insert.side_effect = [Exception("连接失败"), None]

            with patch('asyncio.sleep', return_value=None):
                result = await vector_store.insert(
                    sample_records[:1], batch_size=10, max_retries=3, base_delay=0.1
                )
                assert result["inserted"] == 1
                assert result["errors"] == 0
                assert mock_insert.call_count == 2

    @pytest.mark.asyncio
    async def test_insert_all_retries_failed(self, vector_store, sample_records):
        """测试所有重试都失败"""
        with patch.object(vector_store, '_insert_batch') as mock_insert:
            mock_insert.side_effect = Exception("连接失败")

            with patch('asyncio.sleep', return_value=None):
                result = await vector_store.insert(
                    sample_records[:1], batch_size=10, max_retries=2, base_delay=0.1
                )
                assert result["inserted"] == 0
                assert result["errors"] == 1
                assert mock_insert.call_count == 2

    @pytest.mark.asyncio
    async def test_insert_empty_list(self, vector_store):
        """测试插入空列表"""
        result = await vector_store.insert([])
        assert result["inserted"] == 0
        assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_search_basic(self, vector_store):
        """测试基本搜索"""
        mock_results = [
            MagicMock(
                get=lambda key, default: {
                    'distance': 0.5,
                    'id': 'doc1',
                    'entity': {'text': '测试文档1', 'metadata': {'source': 'test'}}
                }.get(key, default)
            )
        ]

        with patch.object(vector_store, '_client') as mock_client:
            mock_client.search.return_value = [mock_results]
            mock_client.has_collection.return_value = True

            query_vector = np.random.randn(1024).astype(np.float32)
            results = await vector_store.search(query_vector, top_k=5)

            assert len(results) == 1
            assert results[0].id == "doc1"
            assert results[0].distance == 0.5

    @pytest.mark.asyncio
    async def test_search_with_distance_threshold(self, vector_store):
        """测试距离阈值过滤"""
        mock_results = [
            MagicMock(get=lambda key, default: {'distance': 0.3, 'id': 'doc1', 'entity': {'text': '测试1', 'metadata': {}}}.get(key, default)),
            MagicMock(get=lambda key, default: {'distance': 0.8, 'id': 'doc2', 'entity': {'text': '测试2', 'metadata': {}}}.get(key, default)),
        ]

        with patch.object(vector_store, '_client') as mock_client:
            mock_client.search.return_value = [mock_results]
            mock_client.has_collection.return_value = True

            query_vector = np.random.randn(1024).astype(np.float32)
            results = await vector_store.search(query_vector, top_k=5, distance_threshold=0.5)

            assert len(results) == 1
            assert results[0].id == "doc1"

    @pytest.mark.asyncio
    async def test_search_with_metadata_filter(self, vector_store):
        """测试元数据过滤"""
        with patch.object(vector_store, '_client') as mock_client:
            mock_client.search.return_value = [[]]
            mock_client.has_collection.return_value = True

            query_vector = np.random.randn(1024).astype(np.float32)
            await vector_store.search(
                query_vector,
                top_k=5,
                metadata_filter={"source": "test", "category": "A"},
            )

            # 验证过滤表达式构建
            call_kwargs = mock_client.search.call_args[1]
            assert 'filter' in call_kwargs

    @pytest.mark.asyncio
    async def test_delete(self, vector_store):
        """测试删除"""
        with patch.object(vector_store, '_client') as mock_client:
            mock_client.delete.return_value = None

            result = await vector_store.delete(["doc1", "doc2"])
            assert result == 2


class TestInMemoryVectorStore:
    """内存向量存储测试"""

    @pytest.fixture
    def memory_store(self):
        return InMemoryVectorStore(dimension=1024)

    @pytest.fixture
    def sample_records(self):
        return [
            VectorRecord(
                id="doc1",
                vector=np.array([1.0, 0.0, 0.0] + [0.0] * 1021, dtype=np.float32),
                text="文档1",
                metadata={"category": "A"},
            ),
            VectorRecord(
                id="doc2",
                vector=np.array([0.0, 1.0, 0.0] + [0.0] * 1021, dtype=np.float32),
                text="文档2",
                metadata={"category": "B"},
            ),
            VectorRecord(
                id="doc3",
                vector=np.array([0.5, 0.5, 0.0] + [0.0] * 1021, dtype=np.float32),
                text="文档3",
                metadata={"category": "A"},
            ),
        ]

    @pytest.mark.asyncio
    async def test_insert_and_search(self, memory_store, sample_records):
        """测试插入和搜索"""
        await memory_store.insert(sample_records)

        # 搜索与 doc1 相似的向量
        query = np.array([1.0, 0.0, 0.0] + [0.0] * 1021, dtype=np.float32)
        results = await memory_store.search(query, top_k=2)

        assert len(results) == 2
        assert results[0].id == "doc1"  # 最相似

    @pytest.mark.asyncio
    async def test_search_with_metadata_filter(self, memory_store, sample_records):
        """测试元数据过滤搜索"""
        await memory_store.insert(sample_records)

        query = np.array([1.0, 0.0, 0.0] + [0.0] * 1021, dtype=np.float32)
        results = await memory_store.search(
            query, top_k=10, metadata_filter={"category": "A"}
        )

        assert len(results) == 2
        assert all(r.metadata["category"] == "A" for r in results)

    @pytest.mark.asyncio
    async def test_search_with_distance_threshold(self, memory_store, sample_records):
        """测试距离阈值"""
        await memory_store.insert(sample_records)

        query = np.array([1.0, 0.0, 0.0] + [0.0] * 1021, dtype=np.float32)
        results = await memory_store.search(query, top_k=10, distance_threshold=1.0)

        # 只有 doc1 和 doc3 的距离小于 1.0
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_delete(self, memory_store, sample_records):
        """测试删除"""
        await memory_store.insert(sample_records)
        await memory_store.delete(["doc1"])

        query = np.array([1.0, 0.0, 0.0] + [0.0] * 1021, dtype=np.float32)
        results = await memory_store.search(query, top_k=10)

        assert len(results) == 2
        assert all(r.id != "doc1" for r in results)

    @pytest.mark.asyncio
    async def test_empty_store_search(self, memory_store):
        """测试空存储搜索"""
        query = np.random.randn(1024).astype(np.float32)
        results = await memory_store.search(query, top_k=5)
        assert len(results) == 0


class TestVectorStoreFilter:
    """过滤表达式测试"""

    @pytest.fixture
    def vector_store(self):
        return VectorStore(dimension=1024)

    def test_build_filter_string(self, vector_store):
        """测试字符串过滤"""
        filter_dict = {"source": "test", "category": "A"}
        expr = vector_store._build_filter(filter_dict)
        assert 'metadata["source"] == "test"' in expr
        assert 'metadata["category"] == "A"' in expr
        assert " and " in expr

    def test_build_filter_number(self, vector_store):
        """测试数字过滤"""
        filter_dict = {"version": 1, "score": 0.5}
        expr = vector_store._build_filter(filter_dict)
        assert 'metadata["version"] == 1' in expr
        assert 'metadata["score"] == 0.5' in expr

    def test_build_filter_list(self, vector_store):
        """测试列表过滤"""
        filter_dict = {"status": ["active", "pending"]}
        expr = vector_store._build_filter(filter_dict)
        assert 'metadata["status"] in ["active", "pending"]' in expr

    def test_build_filter_empty(self, vector_store):
        """测试空过滤"""
        expr = vector_store._build_filter({})
        assert expr == ""
