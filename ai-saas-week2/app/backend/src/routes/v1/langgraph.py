"""
LangGraph 路由 - 提供 LangGraph 协作链 API

集成 langgraph_collaboration 模块作为 API 端点
"""
from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime
from uuid import uuid4

from app.schemas.common import ResponseBase
from app.agents.langgraph_collaboration import build_collaboration_graph
from langchain_core.messages import HumanMessage

router = APIRouter(prefix="/langgraph", tags=["LangGraph"])


class LangGraphRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class LangGraphResponse(BaseModel):
    response: str
    route: str
    approved: bool
    session_id: str
    timestamp: datetime


_collaboration_graph = None


def get_graph():
    global _collaboration_graph
    if _collaboration_graph is None:
        _collaboration_graph = build_collaboration_graph()
    return _collaboration_graph


@router.post("/chat", summary="LangGraph 协作链对话", response_model=ResponseBase[LangGraphResponse])
async def langgraph_chat(
    request: Request,
    langgraph_request: LangGraphRequest
):
    """
    使用 LangGraph Router -> Executor -> Reviewer 协作链处理消息

    支持的路由：
    - weather: 天气查询（如"北京天气怎么样"）
    - time: 时间查询（如"现在几点了"）
    - calc: 计算查询（如"计算 2+3*4"）
    - general: 通用对话

    Args:
        langgraph_request: 包含消息和可选 session_id

    Returns:
        路由结果和 AI 响应
    """
    session_id = langgraph_request.session_id or str(uuid4())

    app = get_graph()
    result = app.invoke({
        "messages": [HumanMessage(content=langgraph_request.message)],
        "route": "",
        "tool_name": "",
        "tool_input": "",
        "approved": False
    })

    response = LangGraphResponse(
        response=result["messages"][-1].content,
        route=result.get("route", ""),
        approved=result.get("approved", False),
        session_id=session_id,
        timestamp=datetime.now()
    )

    return ResponseBase(code=200, message="success", data=response)


@router.get("/routes", summary="支持的路由类型")
async def get_routes():
    """返回支持的路由类型列表"""
    return ResponseBase(
        code=200,
        message="success",
        data={
            "routes": [
                {"name": "weather", "description": "天气查询", "example": "北京天气怎么样？"},
                {"name": "time", "description": "时间查询", "example": "现在几点了？"},
                {"name": "calc", "description": "数学计算", "example": "计算 2+3*4"},
                {"name": "general", "description": "通用对话", "example": "你好！"},
            ]
        }
    )
