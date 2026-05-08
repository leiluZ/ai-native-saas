from typing import List, Optional, Literal
from fastapi import APIRouter, File, UploadFile, HTTPException
from pathlib import Path
import shutil
import tempfile

from src.rag import DocumentParser, ChunkManager, ParsedDocument, ChunkResult

router = APIRouter(prefix="/rag", tags=["RAG"])

parser = DocumentParser()
chunk_manager = ChunkManager()


@router.post("/parse", response_model=dict)
async def parse_documents(
    files: List[UploadFile] = File(...),
    chunk_size: Optional[int] = 512,
    overlap_ratio: Optional[float] = 0.15,
    chunk_strategy: Literal["fixed", "recursive", "header_aware"] = "recursive"
):
    """解析上传的文档并进行分块"""
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            file_paths = []

            # 保存上传的文件
            for file in files:
                file_path = Path(temp_dir) / file.filename
                with open(file_path, 'wb') as f:
                    shutil.copyfileobj(file.file, f)
                file_paths.append(str(file_path))

            # 解析文档
            results = await parser.parse_files(file_paths)

            # 分块处理
            for doc in results['success']:
                chunks = chunk_manager.chunk_document(
                    doc['content'],
                    source=doc['metadata']['source'],
                    strategy=chunk_strategy,
                    chunk_size=chunk_size,
                    overlap_ratio=overlap_ratio
                )
                doc['chunks'] = [chunk.dict() for chunk in chunks]
                doc['chunk_stats'] = chunk_manager.get_chunk_stats(chunks)

            return {
                "success_count": len(results['success']),
                "error_count": len(results['errors']),
                "documents": results['success'],
                "errors": results['errors']
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chunk", response_model=dict)
async def chunk_text(
    content: str,
    source: str = "",
    chunk_size: Optional[int] = 512,
    overlap_ratio: Optional[float] = 0.15,
    strategy: Literal["fixed", "recursive", "header_aware"] = "recursive"
):
    """对文本进行分块"""
    try:
        chunks = chunk_manager.chunk_document(
            content,
            source=source,
            strategy=strategy,
            chunk_size=chunk_size,
            overlap_ratio=overlap_ratio
        )

        stats = chunk_manager.get_chunk_stats(chunks)

        return {
            "total_chunks": len(chunks),
            "stats": stats,
            "chunks": [chunk.dict() for chunk in chunks]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=dict)
async def rag_health():
    """RAG 服务健康检查"""
    return {
        "status": "healthy",
        "service": "document_parser",
        "chunk_strategies": ["fixed", "recursive", "header_aware"]
    }
