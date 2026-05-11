import logging
import asyncio
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


class RagSearchInput(BaseModel):
    query: str = Field(
        ...,
        description="搜索查询字符串，支持自然语言问题",
    )
    filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="元数据过滤条件，例如 {'source': 'doc.pdf', 'page': 5}",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="返回结果数量，范围 1-50",
    )


class RagSearchResult(BaseModel):
    doc_id: str = Field(..., description="文档块唯一 ID")
    content: str = Field(..., description="检索到的文本内容")
    score: float = Field(..., description="相似度分数")
    source: str = Field(default="", description="来源文档名")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="完整元数据")


class RagSearchResponse(BaseModel):
    query: str = Field(..., description="原始查询")
    results: List[RagSearchResult] = Field(
        default_factory=list, description="检索结果列表"
    )
    total_found: int = Field(default=0, description="检索到的结果总数")
    confidence: str = Field(default="medium", description="置信度: high/medium/low")
    references: List[str] = Field(default_factory=list, description="引用 ID 列表")


def _build_rag_search_tool():
    @tool(args_schema=RagSearchInput)
    async def rag_search(
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
    ) -> str:
        """
        在知识库中搜索相关文档内容。

        适用于需要从已索引的文档中检索信息的场景，如技术文档查询、
        产品手册搜索、内部知识库问答等。

        Args:
            query: 搜索查询字符串
            filters: 可选的元数据过滤条件
            top_k: 返回结果数量 (1-50)

        Returns:
            JSON 格式的搜索结果，包含文档内容、来源引用和置信度
        """
        try:
            from src.main import app as fastapi_app

            embedding_service = getattr(fastapi_app.state, "embedding_service", None)
            vector_store = getattr(fastapi_app.state, "vector_store", None)

            if embedding_service is None or vector_store is None:
                return RagSearchResponse(
                    query=query,
                    results=[],
                    total_found=0,
                    confidence="low",
                    references=[],
                ).model_dump_json()

            query_vector = await embedding_service.encode(query)

            search_results = await vector_store.search(
                query_vector=query_vector,
                top_k=top_k,
                metadata_filter=filters,
            )

            results: List[RagSearchResult] = []
            references: List[str] = []

            for sr in search_results:
                doc_id = sr.id
                source = sr.metadata.get("source", "unknown")
                references.append(doc_id)

                results.append(
                    RagSearchResult(
                        doc_id=doc_id,
                        content=sr.text,
                        score=round(sr.score, 4),
                        source=source,
                        metadata=sr.metadata,
                    )
                )

            if not references:
                confidence = "low"
            elif len(references) < top_k // 2 + 1:
                confidence = "medium"
            else:
                confidence = "high"

            response = RagSearchResponse(
                query=query,
                results=results,
                total_found=len(results),
                confidence=confidence,
                references=references,
            )

            logger.info(
                f"[rag_search] query='{query}', top_k={top_k}, "
                f"found={len(results)}, confidence={confidence}"
            )

            return response.model_dump_json()

        except ImportError as e:
            logger.warning(f"[rag_search] RAG 服务未初始化: {str(e)}")
            return RagSearchResponse(
                query=query,
                results=[],
                total_found=0,
                confidence="low",
                references=[],
            ).model_dump_json()

        except asyncio.TimeoutError:
            logger.error(f"[rag_search] 搜索超时 - query='{query}'")
            return RagSearchResponse(
                query=query,
                results=[],
                total_found=0,
                confidence="low",
                references=[],
            ).model_dump_json()

        except Exception as e:
            logger.error(f"[rag_search] 搜索失败: {str(e)}")
            return RagSearchResponse(
                query=query,
                results=[],
                total_found=0,
                confidence="low",
                references=[],
            ).model_dump_json()

    return rag_search


rag_search_tool = _build_rag_search_tool()
