"""通用响应模型"""
from pydantic import BaseModel, Field
from typing import Generic, TypeVar, Optional

T = TypeVar("T")


class ResponseBase(BaseModel, Generic[T]):
    code: int = Field(200, description="状态码")
    message: str = Field("success", description="提示信息")
    data: Optional[T] = Field(None, description="响应数据")

    model_config = {"json_schema_extra": {"examples": [{"code": 200, "message": "success", "data": {}}]}}


class ErrorResponse(BaseModel):
    code: int = Field(400, description="错误码")
    message: str = Field("error", description="错误信息")
    detail: Optional[str] = Field(None, description="详细错误信息")

    model_config = {"json_schema_extra": {"examples": [{"code": 400, "message": "Bad Request", "detail": "Invalid parameter"}]}}
