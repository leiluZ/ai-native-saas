from typing import Dict, Any
from pydantic import BaseModel, Field


class ParsedDocument(BaseModel):
    content: str = Field(..., description="清洗后的文档内容")
    metadata: Dict[str, Any] = Field(..., description="文档元数据")

    class Config:
        extra = "allow"


class ChunkResult(BaseModel):
    chunk_id: str = Field(..., description="分块唯一ID")
    content: str = Field(..., description="分块内容")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="分块元数据")
    chunk_index: int = Field(..., description="分块索引")
    total_chunks: int = Field(..., description="总分块数")
    token_count: int = Field(..., description="Token数量")


class ParseError(BaseModel):
    file_path: str = Field(..., description="文件路径")
    error: str = Field(..., description="错误信息")
    timestamp: str = Field(..., description="时间戳")


class ChunkRequest(BaseModel):
    content: str = Field(..., description="待分块文本")
    strategy: str = Field(default="recursive", description="分块策略")
    chunk_size: int = Field(default=512, description="分块大小")
    overlap_ratio: float = Field(default=0.15, description="重叠比例")
