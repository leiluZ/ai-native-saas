"""聊天路由"""

import logging
from uuid import uuid4
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
import redis.asyncio as redis
from langchain_core.messages import HumanMessage

from app.schemas.common import ResponseBase
from app.schemas.chat import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatHistoryResponse,
    AgentRequest,
    AgentResponse,
    ApprovalRequest,
    ApprovalResponse,
)
from app.dependencies import get_db, get_redis
from app.agents.chat_agent import run_agent, generate_summary
from app.agents.langgraph_human_in_loop import (
    checkpoint_manager,
    build_human_in_loop_graph,
)
from app.utils.session_memory import SessionMemoryManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["聊天"])


@router.post(
    "/agent", summary="调用 LangChain Agent", response_model=ResponseBase[AgentResponse]
)
async def chat_with_agent(
    request: Request,
    agent_request: AgentRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
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
        await memory_manager.add_message(
            user_id, session_id, agent_request.prompt, "user"
        )

        # 保存助手响应
        session_id, should_summarize = await memory_manager.add_message(
            user_id, session_id, response_content, "assistant"
        )

        # 如果需要摘要压缩
        if should_summarize:
            history_text = await memory_manager._get_full_history(session_id)
            summary = await generate_summary(history_text)
            await memory_manager.update_summary(session_id, summary)

        response = AgentResponse(
            prompt=agent_request.prompt,
            response=response_content,
            timestamp=datetime.now(),
        )

        result = ResponseBase(
            code=200, message="success", data=response, request_id=request_id
        )
        result.extra = {"session_id": session_id}
        return result

    except Exception as e:
        return ResponseBase(code=500, message=str(e), data=None, request_id=request_id)


@router.post(
    "/message", summary="发送聊天消息", response_model=ResponseBase[ChatMessageResponse]
)
async def send_message(
    fastapi_request: Request,
    request: ChatMessageRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
):
    request_id = fastapi_request.state.request_id
    session_id = request.session_id or str(uuid4())

    memory_manager = SessionMemoryManager(db, redis_client)

    # 保存用户消息
    await memory_manager.add_message(
        request.user_id, session_id, request.message, "user"
    )

    # 生成 AI 响应
    ai_response = ChatMessageResponse(
        message_id=str(uuid4()),
        user_id=request.user_id,
        content=f"AI收到您的消息: {request.message}",
        role="assistant",
        session_id=session_id,
        created_at=datetime.now(),
    )

    # 保存 AI 响应
    await memory_manager.add_message(
        request.user_id, session_id, ai_response.content, "assistant"
    )

    return ResponseBase(
        code=200, message="success", data=ai_response, request_id=request_id
    )


@router.get(
    "/history/{session_id}",
    summary="获取聊天历史",
    response_model=ResponseBase[ChatHistoryResponse],
)
async def get_chat_history(
    request: Request,
    session_id: str,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
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
                created_at=datetime.fromisoformat(m["created_at"]),
            )
            for m in history
        ]

        chat_history = ChatHistoryResponse(session_id=session_id, messages=messages)
        return ResponseBase(
            code=200, message="success", data=chat_history, request_id=request_id
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/approve",
    summary="人工审批接口",
    description="用于审批 LangGraph Human-in-the-Loop 中断的任务",
    response_model=ResponseBase[ApprovalResponse],
)
async def approve_task(
    request: Request,
    approval_request: ApprovalRequest,
):
    """
    人工审批接口 - 使用 LangGraph Checkpoint 机制

    当 LangGraph 执行过程中置信度 < 0.7 时，会中断执行等待人工审批。

    新的审批流程：
    1. 调用此接口提交审批结果
    2. 接口会更新 checkpoint 状态并恢复图执行
    3. 返回最终执行结果

    - approved=True: 使用原始结果继续执行
    - approved=False: 使用修改后的结果继续执行（如果提供了 modified_result）

    Args:
        request: FastAPI 请求对象
        approval_request: 审批请求，包含 thread_id, approved, modified_result

    Returns:
        审批结果信息
    """
    request_id = request.state.request_id
    thread_id = approval_request.thread_id

    build_human_in_loop_graph()

    pending_state = checkpoint_manager.get_pending_state(thread_id)

    if not pending_state:
        raise HTTPException(
            status_code=404,
            detail=f"未找到 thread_id={thread_id} 的待审批任务，或任务已处理",
        )

    checkpoint_manager.update_approval(
        thread_id=thread_id,
        approved=approval_request.approved,
        modified_result=approval_request.modified_result,
    )

    result = await checkpoint_manager.resume_and_get_result(thread_id)

    if result:
        final_message = result.get("messages", [])[-1]
        response_content = (
            final_message.content
            if hasattr(final_message, "content")
            else str(final_message)
        )
        confidence = result.get("confidence", pending_state["confidence"])
        checkpoint_manager.clear_thread(thread_id)
        logger.info(f"[ApproveAPI] Thread {thread_id} completed, checkpoint cleared")
    else:
        response_content = "[审批后执行出错，checkpoint 保留以便重试]"
        confidence = pending_state["confidence"]
        logger.warning(
            f"[ApproveAPI] Thread {thread_id} resume failed, checkpoint NOT cleared"
        )

    response = ApprovalResponse(
        thread_id=thread_id,
        approved=approval_request.approved,
        original_result=pending_state["original_result"],
        modified_result=approval_request.modified_result,
        confidence=confidence,
        status="approved" if approval_request.approved else "rejected",
    )

    logger.info(
        f"[ApproveAPI] Thread {thread_id} approved={approval_request.approved}, response='{response_content}'"
    )

    result_base = ResponseBase(
        code=200, message="审批成功", data=response, request_id=request_id
    )
    result_base.extra = {"response": response_content}
    return result_base


@router.get(
    "/approval/{thread_id}",
    summary="查询审批状态",
    description="查询指定线程的审批状态和详情",
    response_model=ResponseBase[ApprovalResponse],
)
async def get_approval_status(
    request: Request,
    thread_id: str,
):
    """
    查询审批状态 - 使用 LangGraph Checkpoint 机制

    通过 checkpoint 获取当前状态来判断审批状态。

    Args:
        request: FastAPI 请求对象
        thread_id: 线程ID

    Returns:
        审批状态信息
    """
    request_id = request.state.request_id

    build_human_in_loop_graph()
    pending_state = checkpoint_manager.get_pending_state(thread_id)

    if not pending_state:
        raise HTTPException(
            status_code=404,
            detail=f"未找到 thread_id={thread_id} 的待审批任务",
        )

    status = "pending"
    if pending_state["approved"]:
        status = "approved"
    elif pending_state.get("modified_result"):
        status = "rejected"

    response = ApprovalResponse(
        thread_id=thread_id,
        approved=pending_state["approved"],
        original_result=pending_state["original_result"],
        modified_result=pending_state.get("modified_result"),
        confidence=pending_state["confidence"],
        status=status,
    )

    return ResponseBase(
        code=200, message="success", data=response, request_id=request_id
    )


class SessionHistoryItem(BaseModel):
    role: str
    content: str
    timestamp: str


class SessionHistoryResponse(BaseModel):
    thread_id: str
    conversation_history: list[SessionHistoryItem]
    total_tokens: int
    needs_summarization: bool
    pending_approval: bool
    confidence: float


@router.get(
    "/sessions/{thread_id}/history",
    summary="查询会话历史",
    description="查询指定线程的会话历史和状态信息",
    response_model=ResponseBase[SessionHistoryResponse],
)
async def get_session_history(
    request: Request,
    thread_id: str,
):
    """
    查询会话历史 - 使用 LangGraph Checkpoint 机制

    通过 checkpoint 获取会话历史和状态信息。

    Args:
        request: FastAPI 请求对象
        thread_id: 线程ID

    Returns:
        会话历史信息
    """
    request_id = request.state.request_id

    build_human_in_loop_graph()
    session_info = checkpoint_manager.get_session_info(thread_id)

    history_items = []
    total_tokens = 0
    needs_summarization = False
    pending_approval = False
    confidence = 1.0

    if session_info:
        history_items = [
            SessionHistoryItem(
                role=item["role"],
                content=item["content"],
                timestamp=item["timestamp"],
            )
            for item in session_info.get("conversation_history", [])
        ]
        total_tokens = session_info.get("total_tokens", 0)
        needs_summarization = session_info.get("needs_summarization", False)
        pending_approval = session_info.get("pending_approval", False)
        confidence = session_info.get("confidence", 1.0)

    response = SessionHistoryResponse(
        thread_id=thread_id,
        conversation_history=history_items,
        total_tokens=total_tokens,
        needs_summarization=needs_summarization,
        pending_approval=pending_approval,
        confidence=confidence,
    )

    return ResponseBase(
        code=200, message="success", data=response, request_id=request_id
    )


@router.post(
    "/langgraph/human-in-loop",
    summary="使用 Human-in-the-Loop 执行聊天",
    description="通过 LangGraph 执行聊天，支持人工审批中断",
    response_model=ResponseBase,
)
async def chat_with_human_in_loop(
    request: Request,
    agent_request: AgentRequest,
):
    """
    使用 Human-in-the-Loop 机制执行聊天 - LangGraph Checkpoint 版本

    当置信度 < 0.7 时会自动中断，等待人工审批。
    使用 MemorySaver + interrupt_before 实现状态持久化和中断。

    新的流程：
    1. 调用此接口启动图执行
    2. 如果置信度 < 0.7，图会在 approval 节点前中断
    3. 返回 202 状态，提示需要审批
    4. 调用 /approve 接口进行审批
    5. 审批接口会恢复图执行并返回最终结果

    Args:
        request: FastAPI 请求对象
        agent_request: 聊天请求

    Returns:
        包含响应内容和 thread_id 的结果
    """
    request_id = request.state.request_id
    thread_id = agent_request.session_id or str(uuid4())

    logger.info(
        f"[ChatAPI] POST /langgraph/human-in-loop - prompt='{agent_request.prompt}', thread_id='{thread_id}'"
    )

    try:
        graph = build_human_in_loop_graph()
        config = {"configurable": {"thread_id": thread_id}}

        existing_history = checkpoint_manager.get_conversation_history(thread_id)
        existing_tokens = 0
        session_info = checkpoint_manager.get_session_info(thread_id)
        if session_info:
            existing_tokens = session_info.get("total_tokens", 0)

        logger.info(
            f"[ChatAPI] Invoking graph with thread_id='{thread_id}', existing_history_len={len(existing_history)}"
        )
        result = await graph.ainvoke(
            {
                "messages": [HumanMessage(content=agent_request.prompt)],
                "conversation_history": existing_history,
                "total_tokens": existing_tokens,
            },
            config,
        )
        logger.info(f"[ChatAPI] Graph result: {result}")

        final_message = result.get("messages", [])[-1]
        response_content = (
            final_message.content
            if hasattr(final_message, "content")
            else str(final_message)
        )

        confidence = result.get("confidence", 1.0)
        pending_approval = result.get("pending_approval", False)
        original_result = result.get("original_result", response_content)

        if pending_approval:
            response = AgentResponse(
                prompt=agent_request.prompt,
                response=f"[等待人工审批] 置信度={confidence:.2f}\n原始结果: {original_result}",
                timestamp=datetime.now(),
            )
            result_base = ResponseBase(
                code=202,
                message="需要人工审批",
                data=response,
                request_id=request_id,
            )
            result_base.extra = {
                "threadId": thread_id,
                "confidence": confidence,
                "needsApproval": True,
            }
            logger.info(
                f"[ChatAPI] Returning 202 (needs approval) - confidence={confidence:.2f}"
            )
            return result_base

        response = AgentResponse(
            prompt=agent_request.prompt,
            response=response_content,
            timestamp=datetime.now(),
        )

        result_base = ResponseBase(
            code=200,
            message="success",
            data=response,
            request_id=request_id,
        )
        result_base.extra = {
            "threadId": thread_id,
            "confidence": confidence,
            "needsApproval": False,
        }
        logger.info(
            f"[ChatAPI] Returning 200 (success) - response='{response_content}'"
        )
        return result_base

    except Exception as e:
        logger.error(f"[ChatAPI] Error: {e}")
        return ResponseBase(
            code=500,
            message=str(e),
            data=None,
            request_id=request_id,
        )
