from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ParsedDocument(BaseModel):
    content: str = Field(..., description="清洗后的文档内容")
    metadata: Dict[str, Any] = Field(..., description="文档元数据")

    class Config:
        extra = "allow"


class ParseError(BaseModel):
    file_path: str = Field(..., description="失败的文件路径")
    error_message: str = Field(..., description="错误信息")
    error_type: str = Field(..., description="错误类型")
    timestamp: str = Field(..., description="错误发生时间")


class ChunkResult(BaseModel):
    chunk_id: str = Field(..., description="分块唯一标识")
    content: str = Field(..., description="分块内容")
    metadata: Dict[str, Any] = Field(..., description="分块元数据")
    chunk_index: int = Field(..., description="分块索引")
    total_chunks: int = Field(..., description="总分块数")
    token_count: int = Field(..., description="Token 数量")
