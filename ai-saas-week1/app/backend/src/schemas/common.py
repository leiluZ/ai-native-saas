"""通用响应模型"""
from pydantic import BaseModel, Field
from typing import Generic, TypeVar, Optional

T = TypeVar("T")


class ResponseBase(BaseModel, Generic[T]):
    code: int = Field(200, description="状态码")
    message: str = Field("success", description="提示信息")
    data: Optional[T] = Field(None, description="响应数据")
    request_id: Optional[str] = Field(None, description="请求ID，用于日志追踪")

    model_config = {"json_schema_extra": {"examples": [{"code": 200, "message": "success", "data": {}, "request_id": "abc123"}]}}


class ErrorResponse(BaseModel):
    code: int = Field(400, description="错误码")
    message: str = Field("error", description="错误信息")
    detail: Optional[str] = Field(None, description="详细错误信息")
    request_id: Optional[str] = Field(None, description="请求ID，用于日志追踪")

    model_config = {"json_schema_extra": {"examples": [{"code": 400, "message": "Bad Request", "detail": "Invalid parameter", "request_id": "abc123"}]}}
