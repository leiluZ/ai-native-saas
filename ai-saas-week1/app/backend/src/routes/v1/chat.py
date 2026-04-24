"""聊天路由"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis
from uuid import uuid4
from datetime import datetime
from schemas.common import ResponseBase
from schemas.chat import ChatMessageRequest, ChatMessageResponse, ChatHistoryResponse
from dependencies import get_db, get_redis

router = APIRouter(prefix="/chat", tags=["聊天"])

session_store = {}

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
