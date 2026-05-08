from fastapi import APIRouter, File, UploadFile, HTTPException
import shutil
import tempfile

from src.rag import DocumentParser, ChunkManager

router = APIRouter(prefix="/rag", tags=["RAG"])

parser = DocumentParser()
chunk_manager = ChunkManager()


@router.post("/parse", response_model=dict)
async def parse_document(file: UploadFile = File(...)):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=file.filename) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        result = await parser.parse_file(tmp_path)
        return {"content": result.content, "metadata": result.metadata}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chunk", response_model=dict)
async def chunk_document(request: dict):
    content = request.get("content", "")
    strategy = request.get("strategy", "recursive")
    chunk_size = request.get("chunk_size", 512)
    overlap_ratio = request.get("overlap_ratio", 0.15)

    chunks = chunk_manager.chunk_document(
        content=content,
        strategy=strategy,
        chunk_size=chunk_size,
        overlap_ratio=overlap_ratio,
    )

    return {
        "chunks": [c.dict() for c in chunks],
        "stats": chunk_manager.get_chunk_stats(chunks),
    }


@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "rag"}
