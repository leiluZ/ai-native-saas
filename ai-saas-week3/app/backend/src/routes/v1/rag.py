import logging
from typing import List
from fastapi import (
    APIRouter,
    File,
    UploadFile,
    HTTPException,
    Form,
    Request,
    Query,
    Body,
)
import shutil
import tempfile

from src.rag import DocumentParser, ChunkManager, VectorRecord

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG"])

parser = DocumentParser()
chunk_manager = ChunkManager()


@router.post("/parse", response_model=dict)
async def parse_document(
    files: List[UploadFile] = File(...),
    chunk_size: int = Form(512),
    overlap_ratio: float = Form(0.15),
    chunk_strategy: str = Form("recursive"),
):
    logger.info(
        f"[RAGAPI] POST /parse - files_count={len(files)}, chunk_size={chunk_size}, "
        f"overlap_ratio={overlap_ratio}, chunk_strategy='{chunk_strategy}'"
    )

    try:
        results = {"success": [], "errors": []}

        for file in files:
            try:
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=file.filename
                ) as tmp:
                    shutil.copyfileobj(file.file, tmp)
                    tmp_path = tmp.name

                logger.info(f"[RAGAPI] Parsing file: {tmp_path}")
                result = await parser.parse_file(tmp_path)

                chunks = chunk_manager.chunk_document(
                    content=result.content,
                    source=file.filename,
                    strategy=chunk_strategy,
                    chunk_size=chunk_size,
                    overlap_ratio=overlap_ratio,
                )

                stats = chunk_manager.get_chunk_stats(chunks)

                results["success"].append(
                    {
                        "content": result.content,
                        "metadata": {
                            "source": file.filename,
                            "file_type": file.content_type
                            or "application/octet-stream",
                            "parsed_at": result.metadata.get("parsed_at", ""),
                        },
                        "chunks": [c.model_dump() for c in chunks],
                        "chunk_stats": stats,
                    }
                )

                logger.info(
                    f"[RAGAPI] Parse complete - filename='{file.filename}', "
                    f"content_length={len(result.content)}, chunks={len(chunks)}"
                )
            except Exception as e:
                logger.error(
                    f"[RAGAPI] Parse failed - filename='{file.filename}', error={str(e)}"
                )
                results["errors"].append({"file": file.filename, "error": str(e)})

        return {
            "success_count": len(results["success"]),
            "error_count": len(results["errors"]),
            "documents": results["success"],
            "errors": results["errors"],
        }

    except Exception as e:
        logger.error(f"[RAGAPI] Parse error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chunk", response_model=dict)
async def chunk_document(request: dict = Body(...)):
    content = request.get("content", "")
    strategy = request.get("strategy", "recursive")
    chunk_size = request.get("chunk_size", 512)
    overlap_ratio = request.get("overlap_ratio", 0.15)

    logger.info(
        f"[RAGAPI] POST /chunk - content_length={len(content)}, strategy='{strategy}', chunk_size={chunk_size}, overlap_ratio={overlap_ratio}"
    )

    chunks = chunk_manager.chunk_document(
        content=content,
        strategy=strategy,
        chunk_size=chunk_size,
        overlap_ratio=overlap_ratio,
    )

    stats = chunk_manager.get_chunk_stats(chunks)
    logger.info(
        f"[RAGAPI] Chunk complete - num_chunks={stats.get('total_chunks', 0)}, total_tokens={stats.get('total_tokens', 0)}, deduplicated={stats.get('deduplicated', 0)}"
    )

    return {
        "chunks": [c.model_dump() for c in chunks],
        "stats": stats,
    }


@router.post("/index", response_model=dict)
async def index_document(
    request: Request,
    doc_request: dict = Body(...),
):
    """
    将文档 chunks 存入向量数据库

    Args:
        doc_request: {
            "chunks": [{"content": "...", "metadata": {...}}],
            "source": "document_name"
        }

    Returns:
        索引结果统计
    """
    chunks = doc_request.get("chunks", [])
    source = doc_request.get("source", "unknown")

    if not chunks:
        raise HTTPException(status_code=400, detail="No chunks provided")

    logger.info(f"[RAGAPI] POST /index - chunks={len(chunks)}, source='{source}'")

    try:
        embedding_service = request.app.state.embedding_service
        vector_store = request.app.state.vector_store

        # 1. 准备文本和元数据
        texts = []
        metadata_list = []
        for i, chunk in enumerate(chunks):
            content = chunk.get("content", "")
            meta = chunk.get("metadata", {})
            meta["source"] = source
            meta["chunk_index"] = i
            texts.append(content)
            metadata_list.append(meta)

        # 2. 生成向量
        logger.info(f"[RAGAPI] Encoding {len(texts)} chunks...")
        vectors = await embedding_service.encode(texts)
        if vectors.ndim == 1:
            vectors = vectors.reshape(1, -1)

        # 3. 创建 VectorRecord 列表
        records = []
        for i, (vector, text, meta) in enumerate(zip(vectors, texts, metadata_list)):
            record = VectorRecord(
                id=f"{source}_{i}_{hash(text) % 10000}",
                vector=vector,
                text=text,
                metadata=meta,
            )
            records.append(record)

        # 4. 存入向量数据库
        result = await vector_store.insert(records)

        logger.info(
            f"[RAGAPI] Index complete - inserted={result.get('inserted', 0)}, "
            f"errors={result.get('errors', 0)}"
        )

        return {
            "success": True,
            "source": source,
            "chunks_indexed": len(records),
            "inserted": result.get("inserted", 0),
            "errors": result.get("errors", 0),
        }

    except Exception as e:
        logger.error(f"[RAGAPI] Index error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"索引失败: {str(e)}")


@router.get("/search")
async def hybrid_search(
    request: Request,
    q: str = Query(..., description="查询文本"),
    top_k: int = Query(10, ge=1, le=100, description="返回结果数量"),
    vector_top_k: int = Query(50, ge=1, le=200, description="向量召回数量"),
    text_top_k: int = Query(50, ge=1, le=200, description="文本召回数量"),
    enable_rerank: bool = Query(True, description="是否启用重排"),
):
    """
    混合检索与重排接口

    返回统一结构:
    [
      {
        "doc_id": "...",
        "score": 0.95,
        "content": "...",
        "source": "...",
        "rerank_score": 0.95,
        "vector_score": 0.88,
        "text_score": 0.0,
        "metadata": {}
      }
    ]
    """
    logger.info(
        f"[RAGAPI] GET /search - q='{q}', top_k={top_k}, vector_top_k={vector_top_k}, text_top_k={text_top_k}, enable_rerank={enable_rerank}"
    )

    try:
        hybrid_search_pipeline = request.app.state.hybrid_search
        results = await hybrid_search_pipeline.search(
            query=q,
            top_k=top_k,
            vector_top_k=vector_top_k,
            text_top_k=text_top_k,
            enable_rerank=enable_rerank,
        )
        return {
            "query": q,
            "total": len(results),
            "results": [r.to_dict() for r in results],
        }
    except Exception as e:
        logger.error(f"[RAGAPI] Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check(request: Request):
    try:
        hybrid_search_pipeline = request.app.state.hybrid_search
        status = await hybrid_search_pipeline.health_check()
        status["service"] = "rag"
        return status
    except Exception:
        return {"status": "healthy", "service": "rag"}
