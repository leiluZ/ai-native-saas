"""聊天路由"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis
from uuid import uuid4
from datetime import datetime
from app.schemas.common import ResponseBase
from app.schemas.chat import ChatMessageRequest, ChatMessageResponse, ChatHistoryResponse, AgentRequest, AgentResponse
from app.dependencies import get_db, get_redis
from app.agents.chat_agent import run_agent, generate_summary
from app.utils.session_memory import SessionMemoryManager

router = APIRouter(prefix="/chat", tags=["聊天"])


@router.post("/agent", summary="调用 LangChain Agent", response_model=ResponseBase[AgentResponse])
async def chat_with_agent(
    request: Request,
    agent_request: AgentRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """
    使用 LangChain Agent 处理用户请求，支持会话记忆。

    Agent 可以调用以下工具：
    - get_weather: 获取天气信息
    - get_current_time: 获取当前时间
    - calculate: 执行数学计算

    Args:
        agent_request: 包含用户输入、session_id 和 user_id 的请求对象

    Returns:
        Agent 的响应结果，包含 session_id 用于后续对话
    """
    request_id = request.state.request_id

    try:
        # 创建会话记忆管理器
        memory_manager = SessionMemoryManager(db, redis_client)

        # 生成或使用 session_id
        session_id = agent_request.session_id or str(uuid4())
        user_id = agent_request.user_id or "default_user"

        # 获取会话记忆上下文
        memory_context = await memory_manager.get_memory_context(session_id)

        # 调用 Agent（注入会话记忆）
        response_content = await run_agent(agent_request.prompt, memory_context)

        # 保存用户消息
        await memory_manager.add_message(user_id, session_id, agent_request.prompt, "user")

        # 保存助手响应
        session_id, should_summarize = await memory_manager.add_message(user_id, session_id, response_content, "assistant")

        # 如果需要摘要压缩
        if should_summarize:
            history_text = await memory_manager._get_full_history(session_id)
            summary = await generate_summary(history_text)
            await memory_manager.update_summary(session_id, summary)

        response = AgentResponse(
            prompt=agent_request.prompt,
            response=response_content,
            timestamp=datetime.now()
        )

        result = ResponseBase(code=200, message="success", data=response, request_id=request_id)
        result.extra = {"session_id": session_id}
        return result

    except Exception as e:
        return ResponseBase(code=500, message=str(e), data=None, request_id=request_id)


@router.post("/message", summary="发送聊天消息", response_model=ResponseBase[ChatMessageResponse])
async def send_message(
    fastapi_request: Request,
    request: ChatMessageRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    request_id = fastapi_request.state.request_id
    session_id = request.session_id or str(uuid4())

    memory_manager = SessionMemoryManager(db, redis_client)

    # 保存用户消息
    await memory_manager.add_message(request.user_id, session_id, request.message, "user")

    # 生成 AI 响应
    ai_response = ChatMessageResponse(
        message_id=str(uuid4()),
        user_id=request.user_id,
        content=f"AI收到您的消息: {request.message}",
        role="assistant",
        session_id=session_id,
        created_at=datetime.now()
    )

    # 保存 AI 响应
    await memory_manager.add_message(request.user_id, session_id, ai_response.content, "assistant")

    return ResponseBase(code=200, message="success", data=ai_response, request_id=request_id)


@router.get("/history/{session_id}", summary="获取聊天历史", response_model=ResponseBase[ChatHistoryResponse])
async def get_chat_history(
    request: Request,
    session_id: str,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
):
    """获取指定会话的完整聊天历史"""
    request_id = request.state.request_id

    memory_manager = SessionMemoryManager(db, redis_client)

    try:
        history = await memory_manager.get_history(session_id)

        if not history:
            raise HTTPException(status_code=404, detail="会话不存在或无消息")

        messages = [
            ChatMessageResponse(
                message_id=m["message_id"],
                user_id=m["user_id"],
                content=m["content"],
                role=m["role"],
                session_id=m["session_id"],
                created_at=datetime.fromisoformat(m["created_at"])
            )
            for m in history
        ]

        chat_history = ChatHistoryResponse(session_id=session_id, messages=messages)
        return ResponseBase(code=200, message="success", data=chat_history, request_id=request_id)

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
