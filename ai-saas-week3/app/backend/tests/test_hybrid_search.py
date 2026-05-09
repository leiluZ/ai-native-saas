import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from src.rag.hybrid_search import (
    HybridSearchResult,
    RRFFusion,
    LocalReranker,
    RerankerClient,
    HybridSearchPipeline,
)


class TestHybridSearchResult:
    """HybridSearchResult 数据类测试"""

    def test_to_dict(self):
        """测试 to_dict 方法"""
        result = HybridSearchResult(
            doc_id="doc-001",
            score=0.95,
            content="测试内容",
            source="test.md",
            rerank_score=0.95,
            vector_score=0.88,
            text_score=0.0,
            metadata={"key": "value"},
        )

        result_dict = result.to_dict()

        assert result_dict["doc_id"] == "doc-001"
        assert result_dict["score"] == 0.95
        assert result_dict["content"] == "测试内容"
        assert result_dict["source"] == "test.md"
        assert result_dict["rerank_score"] == 0.95
        assert result_dict["vector_score"] == 0.88
        assert result_dict["text_score"] == 0.0
        assert result_dict["metadata"] == {"key": "value"}

    def test_to_dict_with_none_values(self):
        """测试包含 None 值的情况"""
        result = HybridSearchResult(
            doc_id="doc-002",
            score=0.8,
            content="",
            source="",
        )

        result_dict = result.to_dict()

        assert result_dict["rerank_score"] is None
        assert result_dict["vector_score"] is None
        assert result_dict["text_score"] is None
        assert result_dict["metadata"] == {}


class TestRRFFusion:
    """RRF 融合器测试"""

    def test_fuse_with_vector_only(self):
        """测试仅向量检索结果"""
        rrf = RRFFusion(k=60)

        vector_results = [
            {"id": "doc1", "score": 0.9, "text": "内容1", "metadata": {"source": "a.md"}},
            {"id": "doc2", "score": 0.8, "text": "内容2", "metadata": {"source": "b.md"}},
        ]
        text_results = []

        fused = rrf.fuse(vector_results, text_results)

        assert len(fused) == 2
        assert fused[0]["doc_id"] == "doc1"
        assert fused[1]["doc_id"] == "doc2"
        assert fused[0]["rrf_score"] > fused[1]["rrf_score"]

    def test_fuse_with_text_only(self):
        """测试仅文本检索结果"""
        rrf = RRFFusion(k=60)

        vector_results = []
        text_results = [
            {"id": "doc3", "score": 0.95, "text": "内容3", "metadata": {"source": "c.md"}},
            {"id": "doc4", "score": 0.85, "text": "内容4", "metadata": {"source": "d.md"}},
        ]

        fused = rrf.fuse(vector_results, text_results)

        assert len(fused) == 2
        assert fused[0]["doc_id"] == "doc3"

    def test_fuse_with_overlapping_docs(self):
        """测试有重叠文档的融合"""
        rrf = RRFFusion(k=60)

        vector_results = [
            {"id": "doc1", "score": 0.9, "text": "内容1", "metadata": {"source": "a.md"}},
            {"id": "doc2", "score": 0.8, "text": "内容2", "metadata": {"source": "b.md"}},
        ]
        text_results = [
            {"id": "doc2", "score": 0.95, "text": "内容2", "metadata": {"source": "b.md"}},
            {"id": "doc3", "score": 0.85, "text": "内容3", "metadata": {"source": "c.md"}},
        ]

        fused = rrf.fuse(vector_results, text_results)

        assert len(fused) == 3
        # doc2 应该在前面，因为它在两个检索中都出现
        doc2 = next(d for d in fused if d["doc_id"] == "doc2")
        assert doc2["vector_score"] == 0.8
        assert doc2["text_score"] == 0.95

    def test_fuse_empty_results(self):
        """测试空结果"""
        rrf = RRFFusion(k=60)

        fused = rrf.fuse([], [])
        assert fused == []

    def test_rrf_formula(self):
        """验证 RRF 公式计算"""
        rrf = RRFFusion(k=60)

        vector_results = [
            {"id": "doc1", "score": 0.9, "text": "内容1", "metadata": {}},
        ]
        text_results = [
            {"id": "doc1", "score": 0.8, "text": "内容1", "metadata": {}},
        ]

        fused = rrf.fuse(vector_results, text_results)

        # RRF 公式: score = 1/(60+1) + 1/(60+1) = 2/61 ≈ 0.032787
        expected_score = 2.0 / 61.0
        assert abs(fused[0]["rrf_score"] - expected_score) < 0.0001


class TestLocalReranker:
    """本地重排器测试"""

    @pytest.mark.asyncio
    async def test_rerank_basic(self):
        """测试基本重排功能"""
        reranker = LocalReranker()

        query = "人工智能"
        documents = [
            {"doc_id": "doc1", "content": "人工智能是计算机科学的一个分支", "source": "a.md"},
            {"doc_id": "doc2", "content": "机器学习是人工智能的核心技术", "source": "b.md"},
            {"doc_id": "doc3", "content": "天气很好", "source": "c.md"},
        ]

        result = await reranker.rerank(query, documents, top_k=2)

        assert len(result) == 2
        assert result[0]["doc_id"] in ["doc1", "doc2"]
        assert "rerank_score" in result[0]
        assert result[0]["rerank_score"] > result[1]["rerank_score"]

    @pytest.mark.asyncio
    async def test_rerank_empty_documents(self):
        """测试空文档列表"""
        reranker = LocalReranker()

        result = await reranker.rerank("测试", [], top_k=5)
        assert result == []

    @pytest.mark.asyncio
    async def test_rerank_query_match(self):
        """测试查询词匹配"""
        reranker = LocalReranker()

        query = "Python 编程"
        documents = [
            {"doc_id": "doc1", "content": "Python 是一种编程语言", "source": "a.md"},
            {"doc_id": "doc2", "content": "Java 也是编程语言", "source": "b.md"},
            {"doc_id": "doc3", "content": "Python 编程入门教程", "source": "c.md"},
        ]

        result = await reranker.rerank(query, documents, top_k=3)

        # doc3 应该得分最高，因为包含两个查询词
        doc3_score = next(r["rerank_score"] for r in result if r["doc_id"] == "doc3")
        doc1_score = next(r["rerank_score"] for r in result if r["doc_id"] == "doc1")
        doc2_score = next(r["rerank_score"] for r in result if r["doc_id"] == "doc2")

        assert doc3_score >= doc1_score > doc2_score

    @pytest.mark.asyncio
    async def test_rerank_content_length_bonus(self):
        """测试内容长度惩罚"""
        reranker = LocalReranker()

        query = "测试"
        documents = [
            {"doc_id": "doc1", "content": "测试", "source": "a.md"},  # 短内容
            {"doc_id": "doc2", "content": "测试 " * 1000, "source": "b.md"},  # 长内容
        ]

        result = await reranker.rerank(query, documents, top_k=2)

        # 短内容应该得分更高
        assert result[0]["doc_id"] == "doc1"

    @pytest.mark.asyncio
    async def test_rerank_chinese_and_english(self):
        """测试中英文混合"""
        reranker = LocalReranker()

        query = "AI 人工智能"
        documents = [
            {"doc_id": "doc1", "content": "AI is Artificial Intelligence", "source": "a.md"},
            {"doc_id": "doc2", "content": "人工智能是 AI 的中文翻译", "source": "b.md"},
            {"doc_id": "doc3", "content": "机器学习 Machine Learning", "source": "c.md"},
        ]

        result = await reranker.rerank(query, documents, top_k=2)

        assert len(result) == 2
        assert result[0]["rerank_score"] > 0


class TestRerankerClient:
    """重排客户端测试"""

    @pytest.mark.asyncio
    async def test_rerank_with_local_fallback(self):
        """测试外部服务不可用时 fallback 到本地重排"""
        # Mock 外部服务失败
        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_post.side_effect = Exception("Connection refused")

            reranker = RerankerClient(use_local_fallback=True)
            documents = [
                {"doc_id": "doc1", "content": "测试内容", "source": "test.md"},
            ]

            result = await reranker.rerank("测试查询", documents, top_k=1)

            assert len(result) == 1
            assert "rerank_score" in result[0]

    @pytest.mark.asyncio
    async def test_rerank_timeout_fallback(self):
        """测试超时 fallback"""
        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_post.side_effect = asyncio.TimeoutError()

            reranker = RerankerClient(timeout_ms=100, use_local_fallback=True)
            documents = [
                {"doc_id": "doc1", "content": "测试", "source": "a.md"},
            ]

            result = await reranker.rerank("测试", documents, top_k=1)

            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_rerank_without_local_fallback(self):
        """测试不使用本地 fallback 的情况"""
        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_post.side_effect = Exception("Connection refused")

            reranker = RerankerClient(use_local_fallback=False)
            documents = [
                {"doc_id": "doc1", "content": "测试", "source": "a.md", "rrf_score": 0.8},
            ]

            result = await reranker.rerank("测试", documents, top_k=1)

            assert len(result) == 1
            assert result[0]["rerank_score"] == 0.8  # 使用 rrf_score

    @pytest.mark.asyncio
    async def test_rerank_empty_documents(self):
        """测试空文档"""
        reranker = RerankerClient()
        result = await reranker.rerank("测试", [], top_k=5)
        assert result == []

    @pytest.mark.asyncio
    async def test_close_session(self):
        """测试关闭会话"""
        reranker = RerankerClient()
        # 确保不会抛出异常
        await reranker.close()


class TestHybridSearchPipeline:
    """混合检索管道测试"""

    @pytest.mark.asyncio
    async def test_search_with_cache_hit(self):
        """测试缓存命中"""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = '[{"doc_id": "doc1", "score": 0.9, "content": "test", "source": "test.md", "rerank_score": 0.9}]'

        mock_vector_store = MagicMock()
        mock_embedding = MagicMock()
        mock_reranker = MagicMock()

        pipeline = HybridSearchPipeline(
            vector_store=mock_vector_store,
            embedding_service=mock_embedding,
            redis_client=mock_redis,
            reranker=mock_reranker,
        )

        results = await pipeline.search("测试查询", top_k=10)

        assert len(results) == 1
        assert results[0].doc_id == "doc1"
        # 验证没有调用向量检索和重排
        mock_embedding.encode.assert_not_called()
        mock_vector_store.search.assert_not_called()
        mock_reranker.rerank.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_with_cache_miss(self):
        """测试缓存未命中"""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        mock_vector_store = MagicMock()
        mock_vector_store.search.return_value = [
            MagicMock(id="doc1", text="内容1", metadata={"source": "a.md"}, score=0.9),
        ]

        mock_embedding = MagicMock()
        mock_embedding.encode.return_value = [[0.1, 0.2, 0.3]]

        mock_reranker = MagicMock()
        mock_reranker.rerank.return_value = [
            {"doc_id": "doc1", "content": "内容1", "source": "a.md", "rerank_score": 0.95, "vector_score": 0.9, "text_score": 0.0},
        ]

        pipeline = HybridSearchPipeline(
            vector_store=mock_vector_store,
            embedding_service=mock_embedding,
            redis_client=mock_redis,
            reranker=mock_reranker,
        )

        results = await pipeline.search("测试查询", top_k=1)

        assert len(results) == 1
        assert results[0].doc_id == "doc1"
        assert results[0].score == 0.95
        mock_redis.setex.assert_called_once()  # 验证写入缓存

    @pytest.mark.asyncio
    async def test_search_disable_rerank(self):
        """测试禁用重排"""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        mock_vector_store = MagicMock()
        mock_vector_store.search.return_value = [
            MagicMock(id="doc1", text="内容1", metadata={"source": "a.md"}, score=0.9),
        ]

        mock_embedding = MagicMock()
        mock_embedding.encode.return_value = [[0.1, 0.2, 0.3]]

        mock_reranker = MagicMock()

        pipeline = HybridSearchPipeline(
            vector_store=mock_vector_store,
            embedding_service=mock_embedding,
            redis_client=mock_redis,
            reranker=mock_reranker,
        )

        results = await pipeline.search("测试查询", top_k=1, enable_rerank=False)

        assert len(results) == 1
        mock_reranker.rerank.assert_not_called()  # 验证没有调用重排

    @pytest.mark.asyncio
    async def test_search_text_search_empty(self):
        """测试文本检索返回空结果"""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        mock_vector_store = MagicMock()
        mock_vector_store.search.return_value = [
            MagicMock(id="doc1", text="内容1", metadata={"source": "a.md"}, score=0.9),
        ]

        mock_embedding = MagicMock()
        mock_embedding.encode.return_value = [[0.1, 0.2, 0.3]]

        mock_reranker = MagicMock()
        mock_reranker.rerank.return_value = [
            {"doc_id": "doc1", "content": "内容1", "source": "a.md", "rerank_score": 0.9, "vector_score": 0.9, "text_score": 0.0},
        ]

        pipeline = HybridSearchPipeline(
            vector_store=mock_vector_store,
            embedding_service=mock_embedding,
            redis_client=mock_redis,
            reranker=mock_reranker,
        )

        # _text_search 默认返回空列表
        results = await pipeline.search("测试查询", top_k=1)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_health_check(self):
        """测试健康检查"""
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True

        mock_vector_store = MagicMock()
        mock_vector_store.health_check.return_value = True

        mock_embedding = MagicMock()

        pipeline = HybridSearchPipeline(
            vector_store=mock_vector_store,
            embedding_service=mock_embedding,
            redis_client=mock_redis,
        )

        status = await pipeline.health_check()

        assert status["vector_store"] == "healthy"
        assert status["redis"] == "healthy"
        assert status["reranker"] == "configured"
        assert "timestamp" in status

    @pytest.mark.asyncio
    async def test_health_check_redis_unavailable(self):
        """测试 Redis 不可用"""
        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = Exception("Connection refused")

        mock_vector_store = MagicMock()
        mock_vector_store.health_check.return_value = True

        mock_embedding = MagicMock()

        pipeline = HybridSearchPipeline(
            vector_store=mock_vector_store,
            embedding_service=mock_embedding,
            redis_client=mock_redis,
        )

        status = await pipeline.health_check()

        assert status["redis"] == "unhealthy"
