import logging
from typing import List
from fastapi import APIRouter, File, UploadFile, HTTPException, Form
import shutil
import tempfile

from src.rag import DocumentParser, ChunkManager

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
                        "chunks": [c.dict() for c in chunks],
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
async def chunk_document(request: dict):
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
        "chunks": [c.dict() for c in chunks],
        "stats": stats,
    }


@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "rag"}
