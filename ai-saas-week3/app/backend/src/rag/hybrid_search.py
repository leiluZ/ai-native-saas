import logging
import asyncio
import hashlib
import json
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import redis.asyncio as redis

logger = logging.getLogger(__name__)


@dataclass
class HybridSearchResult:
    """混合检索统一结果结构"""

    doc_id: str
    score: float
    content: str
    source: str
    rerank_score: Optional[float] = None
    vector_score: Optional[float] = None
    text_score: Optional[float] = None
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "score": self.score,
            "content": self.content,
            "source": self.source,
            "rerank_score": self.rerank_score,
            "vector_score": self.vector_score,
            "text_score": self.text_score,
            "metadata": self.metadata or {},
        }


class RRFFusion:
    """RRF (Reciprocal Rank Fusion) 融合器"""

    def __init__(self, k: int = 60):
        self.k = k
        logger.info(f"[RRFFusion] Initialized with k={k}")

    def fuse(
        self,
        vector_results: List[Dict[str, Any]],
        text_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        RRF 融合公式: score = Σ 1/(k + rank)

        Args:
            vector_results: 向量检索结果列表，每项需含 id, score, text, metadata
            text_results: 文本检索结果列表，每项需含 id, score, text, metadata

        Returns:
            融合后的结果列表（按 RRF 分数降序）
        """
        rrf_scores: Dict[str, Dict[str, Any]] = {}

        # 处理向量结果
        for rank, item in enumerate(vector_results, start=1):
            doc_id = item.get("id") or item.get("doc_id")
            if not doc_id:
                continue
            if doc_id not in rrf_scores:
                rrf_scores[doc_id] = {
                    "doc_id": doc_id,
                    "content": item.get("text", ""),
                    "source": item.get("metadata", {}).get("source", ""),
                    "metadata": item.get("metadata", {}),
                    "vector_score": item.get("score", 0.0),
                    "text_score": 0.0,
                    "rrf_score": 0.0,
                }
            rrf_scores[doc_id]["rrf_score"] += 1.0 / (self.k + rank)

        # 处理文本结果
        for rank, item in enumerate(text_results, start=1):
            doc_id = item.get("id") or item.get("doc_id")
            if not doc_id:
                continue
            if doc_id not in rrf_scores:
                rrf_scores[doc_id] = {
                    "doc_id": doc_id,
                    "content": item.get("text", ""),
                    "source": item.get("metadata", {}).get("source", ""),
                    "metadata": item.get("metadata", {}),
                    "vector_score": 0.0,
                    "text_score": item.get("score", 0.0),
                    "rrf_score": 0.0,
                }
            else:
                rrf_scores[doc_id]["text_score"] = item.get("score", 0.0)
            rrf_scores[doc_id]["rrf_score"] += 1.0 / (self.k + rank)

        # 按 RRF 分数降序排序
        fused = sorted(rrf_scores.values(), key=lambda x: x["rrf_score"], reverse=True)
        logger.info(
            f"[RRFFusion] Fused {len(vector_results)} vector + {len(text_results)} text = {len(fused)} results"
        )
        return fused


class LocalReranker:
    """本地重排器（仅用于测试目的，基于简单的词频匹配）"""

    def __init__(self):
        logger.info("[LocalReranker] Initialized (test mode)")

    async def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        使用简单的词频匹配进行重排（测试用）

        Args:
            query: 查询文本
            documents: 待重排文档列表
            top_k: 返回 Top-K 结果

        Returns:
            重排后的结果列表（含 rerank_score）
        """
        if not documents:
            return []

        query_tokens = set(self._tokenize(query))
        scored = []

        for doc in documents:
            content = doc.get("content", "")
            doc_tokens = self._tokenize(content)

            # 计算匹配度：查询词在文档中出现的比例
            match_count = sum(1 for token in query_tokens if token in doc_tokens)
            score = match_count / max(len(query_tokens), 1)

            # 加上内容长度的惩罚（更短的内容更精确）
            content_bonus = min(1.0, 100 / max(len(content), 100))
            final_score = (score * 0.7) + (content_bonus * 0.3)

            scored.append(
                {
                    **doc.copy(),
                    "rerank_score": round(final_score, 4),
                }
            )

        # 按分数降序排序
        scored.sort(key=lambda x: x["rerank_score"], reverse=True)
        logger.info(
            f"[LocalReranker] Reranked {len(scored)} docs, returning top {top_k}"
        )

        return scored[:top_k]

    def _tokenize(self, text: str) -> set:
        """简单的分词（仅保留字母和数字）"""
        tokens = re.findall(r"[a-zA-Z0-9\u4e00-\u9fa5]+", text.lower())
        return set(tokens)


class RerankerClient:
    """重排服务客户端（异步调用，支持超时 fallback 到本地重排）"""

    def __init__(
        self,
        api_url: str = "http://localhost:8080/rerank",
        timeout_ms: float = 800.0,
        model: str = "bge-reranker-v2-m3",
        use_local_fallback: bool = True,
    ):
        self.api_url = api_url
        self.timeout = timeout_ms / 1000.0  # 转换为秒
        self.model = model
        self.use_local_fallback = use_local_fallback
        self._session: Optional[Any] = None
        self._local_reranker = LocalReranker() if use_local_fallback else None
        logger.info(
            f"[RerankerClient] Initialized - url={api_url}, timeout={timeout_ms}ms, local_fallback={use_local_fallback}"
        )

    async def _get_session(self):
        if self._session is None:
            import aiohttp

            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
        return self._session

    async def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        异步调用重排服务，超时则 fallback 到本地重排

        Args:
            query: 查询文本
            documents: 待重排文档列表
            top_k: 返回 Top-K 结果

        Returns:
            重排后的结果列表（含 rerank_score）
        """
        if not documents:
            return []

        payload = {
            "model": self.model,
            "query": query,
            "documents": [d.get("content", "") for d in documents],
            "top_k": top_k,
        }

        try:
            session = await self._get_session()
            async with session.post(self.api_url, json=payload) as resp:
                if resp.status != 200:
                    logger.warning(f"[RerankerClient] API returned {resp.status}")
                    return await self._fallback(query, documents, top_k)

                data = await resp.json()
                results = data.get("results", [])

                # 映射回原始文档结构
                reranked = []
                for r in results:
                    idx = r.get("index", 0)
                    if 0 <= idx < len(documents):
                        doc = documents[idx].copy()
                        doc["rerank_score"] = r.get("relevance_score", 0.0)
                        reranked.append(doc)

                logger.info(
                    f"[RerankerClient] Rerank complete - returned {len(reranked)} results"
                )
                return reranked

        except asyncio.TimeoutError:
            logger.warning(f"[RerankerClient] Timeout after {self.timeout}s")
            return await self._fallback(query, documents, top_k)
        except Exception as e:
            logger.error(f"[RerankerClient] Error: {e}")
            return await self._fallback(query, documents, top_k)

    async def _fallback(
        self, query: str, documents: List[Dict[str, Any]], top_k: int
    ) -> List[Dict[str, Any]]:
        """fallback：使用本地重排或保留原始顺序"""
        if self._local_reranker:
            logger.info("[RerankerClient] Falling back to LocalReranker")
            return await self._local_reranker.rerank(query, documents, top_k)

        # 最终 fallback：保留原始 RRF 分数作为 rerank_score
        fallback = []
        for doc in documents[:top_k]:
            d = doc.copy()
            d["rerank_score"] = doc.get("rrf_score", doc.get("score", 0.0))
            fallback.append(d)
        return fallback

    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None


class HybridSearchPipeline:
    """混合检索与重排管道"""

    def __init__(
        self,
        vector_store: Any,
        embedding_service: Any,
        redis_client: redis.Redis,
        reranker: Optional[RerankerClient] = None,
        rrf_k: int = 60,
        cache_ttl: int = 3600,
        enable_cache: bool = True,
    ):
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.redis = redis_client
        self.reranker = reranker or RerankerClient()
        self.rrf = RRFFusion(k=rrf_k)
        self.cache_ttl = cache_ttl
        self.enable_cache = enable_cache
        logger.info(
            f"[HybridSearchPipeline] Initialized - rrf_k={rrf_k}, cache_ttl={cache_ttl}s, cache_enabled={enable_cache}"
        )

    def _cache_key(self, query: str, top_k: int) -> str:
        """生成缓存键"""
        key_str = f"hybrid_search:{query}:{top_k}"
        return f"hybrid:{hashlib.sha256(key_str.encode()).hexdigest()[:16]}"

    async def _get_cache(self, cache_key: str) -> Optional[List[Dict[str, Any]]]:
        """从 Redis 获取缓存结果"""
        if not self.enable_cache:
            return None
        try:
            data = await self.redis.get(cache_key)
            if data:
                logger.info(f"[HybridSearchPipeline] Cache hit - key={cache_key}")
                return json.loads(data)
        except Exception as e:
            logger.warning(f"[HybridSearchPipeline] Cache read error: {e}")
        return None

    async def _set_cache(self, cache_key: str, results: List[Dict[str, Any]]):
        """写入 Redis 缓存"""
        if not self.enable_cache:
            return
        try:
            await self.redis.setex(
                cache_key, self.cache_ttl, json.dumps(results, ensure_ascii=False)
            )
            logger.info(f"[HybridSearchPipeline] Cache set - key={cache_key}")
        except Exception as e:
            logger.warning(f"[HybridSearchPipeline] Cache write error: {e}")

    async def search(
        self,
        query: str,
        top_k: int = 10,
        vector_top_k: int = 50,
        text_top_k: int = 50,
        enable_rerank: bool = True,
    ) -> List[HybridSearchResult]:
        """
        执行混合检索与重排

        Args:
            query: 查询文本
            top_k: 最终返回结果数
            vector_top_k: 向量检索召回数
            text_top_k: 文本检索召回数
            enable_rerank: 是否启用重排

        Returns:
            统一结构的检索结果列表
        """
        cache_key = self._cache_key(query, top_k)

        # 1. 尝试读取缓存
        cached = await self._get_cache(cache_key)
        if cached is not None:
            return [HybridSearchResult(**item) for item in cached]

        # 2. 向量检索
        query_vector = await self.embedding_service.encode(query)
        if query_vector.ndim == 1:
            query_vector = query_vector.reshape(1, -1)

        vector_results = await self.vector_store.search(
            query_vector=query_vector[0],
            top_k=vector_top_k,
        )
        vector_hits = [
            {
                "id": r.id,
                "score": r.score,
                "text": r.text,
                "metadata": r.metadata,
            }
            for r in vector_results
        ]

        # 3. 文本检索（简化版：基于关键词匹配，实际可接入 Elasticsearch）
        text_hits = await self._text_search(query, top_k=text_top_k)

        # 4. RRF 融合
        fused = self.rrf.fuse(vector_hits, text_hits)

        # 5. 重排（异步 + 超时 fallback）
        if enable_rerank:
            reranked = await self.reranker.rerank(query, fused, top_k=top_k)
        else:
            reranked = fused[:top_k]
            for r in reranked:
                r["rerank_score"] = r.get("rrf_score", r.get("score", 0.0))

        # 6. 组装统一结果
        final_results = []
        for item in reranked[:top_k]:
            final_results.append(
                HybridSearchResult(
                    doc_id=item["doc_id"],
                    score=item.get("rerank_score", item.get("rrf_score", 0.0)),
                    content=item.get("content", ""),
                    source=item.get("source", ""),
                    rerank_score=item.get("rerank_score"),
                    vector_score=item.get("vector_score", 0.0),
                    text_score=item.get("text_score", 0.0),
                    metadata=item.get("metadata", {}),
                )
            )

        # 7. 写入缓存
        await self._set_cache(cache_key, [r.to_dict() for r in final_results])

        logger.info(
            f"[HybridSearchPipeline] Search complete - query='{query}', results={len(final_results)}"
        )
        return final_results

    async def _text_search(self, query: str, top_k: int = 50) -> List[Dict[str, Any]]:
        """
        文本检索（简化实现：从向量库中基于关键词匹配）
        实际生产环境可替换为 Elasticsearch / BM25 检索
        """
        # 简化：这里返回空列表，由子类或外部注入具体实现
        # 若需要，可从现有向量库中基于 text 字段做简单过滤
        logger.info(f"[HybridSearchPipeline] Text search placeholder - query='{query}'")
        return []

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        vector_ok = await self.vector_store.health_check()
        redis_ok = False
        try:
            await self.redis.ping()
            redis_ok = True
        except Exception:
            pass
        return {
            "vector_store": "healthy" if vector_ok else "unhealthy",
            "redis": "healthy" if redis_ok else "unhealthy",
            "reranker": "configured",
            "timestamp": datetime.utcnow().isoformat(),
        }
