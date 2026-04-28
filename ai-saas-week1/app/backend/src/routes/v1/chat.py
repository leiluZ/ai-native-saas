"""聊天路由"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis
from uuid import uuid4
from datetime import datetime
from app.schemas.common import ResponseBase
from app.schemas.chat import ChatMessageRequest, ChatMessageResponse, ChatHistoryResponse, AgentRequest, AgentResponse
from app.dependencies import get_db, get_redis
from app.agents.chat_agent import run_agent

router = APIRouter(prefix="/chat", tags=["聊天"])

session_store = {}

@router.post("/agent", summary="调用 LangChain Agent", response_model=ResponseBase[AgentResponse])
async def chat_with_agent(request: Request, agent_request: AgentRequest):
    """
    使用 LangChain Agent 处理用户请求。

    Agent 可以调用以下工具：
    - get_weather: 获取天气信息
    - get_current_time: 获取当前时间
    - calculate: 执行数学计算

    Args:
        agent_request: 包含用户输入的请求对象

    Returns:
        Agent 的响应结果
    """
    request_id = request.state.request_id
    try:
        response_content = await run_agent(agent_request.prompt)
        response = AgentResponse(
            prompt=agent_request.prompt,
            response=response_content,
            timestamp=datetime.now()
        )
        return ResponseBase(code=200, message="success", data=response, request_id=request_id)
    except Exception as e:
        return ResponseBase(code=500, message=str(e), data=None, request_id=request_id)

@router.post("/message", summary="发送聊天消息", response_model=ResponseBase[ChatMessageResponse])
async def send_message(fastapi_request: Request, request: ChatMessageRequest, db: AsyncSession = Depends(get_db), redis_client: redis.Redis = Depends(get_redis)):
    request_id = fastapi_request.state.request_id
    session_id = request.session_id or str(uuid4())
    ai_response = ChatMessageResponse(
        message_id=str(uuid4()),
        user_id=request.user_id,
        content=f"AI收到您的消息: {request.message}",
        role="assistant",
        session_id=session_id,
        created_at=datetime.now()
    )
    if session_id not in session_store:
        session_store[session_id] = []
    session_store[session_id].append({
        "user_id": request.user_id,
        "message": request.message,
        "timestamp": datetime.now().isoformat()
    })
    try:
        await redis_client.hset(f"session:{session_id}", mapping={"user_id": request.user_id, "last_active": datetime.now().isoformat()})
    except Exception:
        pass
    return ResponseBase(code=200, message="success", data=ai_response, request_id=request_id)

@router.get("/history/{session_id}", summary="获取聊天历史", response_model=ResponseBase[ChatHistoryResponse])
async def get_chat_history(request: Request, session_id: str, redis_client: redis.Redis = Depends(get_redis)):
    request_id = request.state.request_id
    if session_id not in session_store:
        try:
            session_data = await redis_client.hgetall(f"session:{session_id}")
            if not session_data:
                raise HTTPException(status_code=404, detail="会话不存在")
        except Exception:
            raise HTTPException(status_code=404, detail="会话不存在")
    history = ChatHistoryResponse(session_id=session_id, messages=[])
    return ResponseBase(code=200, message="success", data=history, request_id=request_id)
