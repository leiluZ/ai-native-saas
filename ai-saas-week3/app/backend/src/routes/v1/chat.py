"""聊天路由"""

import logging
from uuid import uuid4
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from src.schemas.common import ResponseBase
from src.schemas.chat import (
    ChatMessageResponse,
    ChatHistoryResponse,
    AgentRequest,
    AgentResponse,
    ApprovalRequest,
    ApprovalResponse,
    SessionHistoryResponse,
    SessionHistoryItem,
)
from src.dependencies import get_db, get_redis
from src.agents.chat_agent import run_agent, generate_summary
from src.agents.langgraph_chat_agent import (
    run_langgraph,
    update_approval,
    get_approval_status,
    get_session_info,
    get_execution_trace,
    generate_mermaid_sequence,
)
from src.agents.langgraph_rag_agent import (
    run_rag_agent,
    run_rag_agent_stream,
    get_rag_session_info,
    get_execution_trace as get_rag_execution_trace,
)
from src.utils.session_memory import SessionMemoryManager
from src.utils.circuit_breaker import global_circuit_breaker, CircuitBreakerError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["聊天"])


@router.post(
    "/langgraph/execute",
    summary="使用 LangGraph 执行聊天",
    description="使用 LangGraph 状态机执行聊天，支持 Human-in-the-Loop 审批和熔断器保护",
    response_model=ResponseBase,
)
async def chat_with_langgraph(
    request: Request,
    agent_request: AgentRequest,
):
    """
    使用 LangGraph 状态机执行聊天（带 Human-in-the-Loop 审批）

    状态机流程：
    START → analyze → [tool if needed] → approval → [response or END] → memory → END

    当置信度 < 0.7 时会触发人工审批中断。

    Args:
        request: FastAPI 请求对象
        agent_request: 聊天请求

    Returns:
        包含响应内容和会话信息的结果
    """
    request_id = request.state.request_id
    thread_id = agent_request.session_id or str(uuid4())

    logger.info(
        f"[ChatAPI] POST /langgraph/execute - prompt='{agent_request.prompt}', thread_id='{thread_id}'"
    )

    try:
        result = await run_langgraph(agent_request.prompt, thread_id)

        final_response = result.get("final_response", "")
        total_tokens = result.get("total_tokens", 0)
        needs_summarization = result.get("needs_summarization", False)
        needs_approval = result.get("needs_approval", False)
        pending_approval = result.get("pending_approval", False)
        confidence = result.get("confidence", 1.0)
        original_result = result.get("original_result", "")

        logger.info(
            f"[ChatAPI] LangGraph result: response='{final_response}', confidence={confidence:.2f}, needs_approval={needs_approval}"
        )

        # 如果有待审批，返回 202 状态
        if pending_approval:
            return ResponseBase(
                code=202,
                message="需要人工审批",
                data={
                    "prompt": agent_request.prompt,
                    "response": final_response,
                    "session_id": thread_id,
                    "confidence": confidence,
                    "original_result": original_result,
                },
                extra={
                    "needsApproval": True,
                    "threadId": thread_id,
                    "confidence": confidence,
                },
                request_id=request_id,
            )

        return ResponseBase(
            code=200,
            message="success",
            data={
                "prompt": agent_request.prompt,
                "response": final_response,
                "session_id": thread_id,
                "total_tokens": total_tokens,
                "needs_summarization": needs_summarization,
                "confidence": confidence,
            },
            request_id=request_id,
        )

    except CircuitBreakerError as e:
        logger.error(f"[ChatAPI] LangGraph circuit breaker error: {str(e)}")
        return ResponseBase(
            code=503,
            message="服务暂时不可用，请稍后重试",
            data=None,
            request_id=request_id,
            extra={"circuit_state": global_circuit_breaker.state_str},
        )
    except Exception as e:
        logger.error(f"[ChatAPI] LangGraph error: {str(e)}")
        return ResponseBase(
            code=500,
            message=f"执行失败: {str(e)}",
            data=None,
            request_id=request_id,
        )


@router.post(
    "/langgraph/approve",
    summary="审批 LangGraph 请求",
    description="对 LangGraph 状态机的待审批请求进行审批",
    response_model=ResponseBase,
)
async def approve_langgraph(
    request: Request,
    approval_request: ApprovalRequest,
):
    """
    审批 LangGraph 的待审批请求

    Args:
        request: FastAPI 请求对象
        approval_request: 审批请求

    Returns:
        审批后的执行结果
    """
    request_id = request.state.request_id
    thread_id = approval_request.thread_id

    logger.info(
        f"[ChatAPI] POST /langgraph/approve - thread_id='{thread_id}', approved={approval_request.approved}"
    )

    try:
        result = await update_approval(
            thread_id,
            approval_request.approved,
            approval_request.modified_result,
        )

        final_response = result.get("final_response", "")
        total_tokens = result.get("total_tokens", 0)

        logger.info(f"[ChatAPI] LangGraph approve result: response='{final_response}'")

        return ResponseBase(
            code=200,
            message="审批成功",
            data={
                "thread_id": thread_id,
                "response": final_response,
                "total_tokens": total_tokens,
                "approved": approval_request.approved,
                "modified_result": approval_request.modified_result,
            },
            request_id=request_id,
        )

    except Exception as e:
        logger.error(f"[ChatAPI] Week1 approve error: {str(e)}")
        return ResponseBase(
            code=500,
            message=f"审批失败: {str(e)}",
            data=None,
            request_id=request_id,
        )


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


@router.get(
    "/langgraph/approval/{thread_id}",
    summary="查询 LangGraph 审批状态",
    description="查询指定线程的 LangGraph 审批状态和详情",
    response_model=ResponseBase[ApprovalResponse],
)
async def get_langgraph_approval_status_endpoint(
    request: Request,
    thread_id: str,
):
    """
    查询 LangGraph 审批状态

    Args:
        request: FastAPI 请求对象
        thread_id: 线程ID

    Returns:
        审批状态信息
    """
    request_id = request.state.request_id

    pending_state = await get_approval_status(thread_id)

    if not pending_state:
        raise HTTPException(
            status_code=404,
            detail=f"未找到 thread_id={thread_id} 的待审批任务",
        )

    response = ApprovalResponse(
        thread_id=thread_id,
        approved=pending_state["approved"],
        original_result=pending_state["original_result"],
        modified_result=pending_state.get("modified_result"),
        confidence=pending_state["confidence"],
        status=pending_state["status"],
    )

    return ResponseBase(
        code=200, message="success", data=response, request_id=request_id
    )


@router.get(
    "/langgraph/sessions/{thread_id}/history",
    summary="查询 LangGraph 会话历史",
    description="查询指定线程的 LangGraph 会话历史和状态信息",
    response_model=ResponseBase[SessionHistoryResponse],
)
async def get_langgraph_session_history(
    request: Request,
    thread_id: str,
):
    """
    查询 LangGraph 会话历史

    Args:
        request: FastAPI 请求对象
        thread_id: 线程ID

    Returns:
        会话历史信息
    """
    request_id = request.state.request_id

    session_info = await get_session_info(thread_id)

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


@router.get(
    "/circuit/status",
    summary="获取熔断器状态",
    description="获取熔断器的当前状态（OPEN/HALF_OPEN/CLOSED）",
    response_model=ResponseBase,
)
async def get_circuit_status(request: Request):
    """
    获取熔断器状态信息

    Returns:
        熔断器状态详情
    """
    request_id = request.state.request_id

    status = global_circuit_breaker.get_status()

    return ResponseBase(
        code=200,
        message="success",
        data=status,
        request_id=request_id,
    )


@router.post(
    "/circuit/reset",
    summary="重置熔断器",
    description="手动重置熔断器到 CLOSED 状态",
    response_model=ResponseBase,
)
async def reset_circuit(request: Request):
    """
    手动重置熔断器

    Returns:
        重置结果
    """
    request_id = request.state.request_id

    global_circuit_breaker.reset()
    logger.info("[CircuitAPI] Circuit breaker reset manually")

    return ResponseBase(
        code=200,
        message="熔断器已重置",
        data={"state": "CLOSED"},
        request_id=request_id,
    )


@router.get(
    "/langgraph/sessions/{thread_id}/trace",
    summary="获取 LangGraph 执行轨迹",
    description="获取指定线程的 LangGraph 执行轨迹，用于可视化展示",
    response_model=ResponseBase,
)
async def get_langgraph_execution_trace(
    request: Request,
    thread_id: str,
):
    """
    获取 LangGraph 执行轨迹

    轨迹格式: [{node: "analyze", state: {...}, timestamp: "..."}, ...]

    Args:
        request: FastAPI 请求对象
        thread_id: 线程ID

    Returns:
        执行轨迹列表
    """
    request_id = request.state.request_id

    trace = get_execution_trace(thread_id)

    return ResponseBase(code=200, message="success", data=trace, request_id=request_id)


@router.get(
    "/langgraph/sessions/{thread_id}/mermaid",
    summary="获取 Mermaid 序列图",
    description="根据执行轨迹生成 Mermaid 序列图，用于可视化展示执行流程",
    response_model=ResponseBase,
)
async def get_langgraph_mermaid(
    request: Request,
    thread_id: str,
):
    """
    获取 Mermaid 序列图

    Args:
        request: FastAPI 请求对象
        thread_id: 线程ID

    Returns:
        Mermaid 序列图文本
    """
    request_id = request.state.request_id

    trace = get_execution_trace(thread_id)
    mermaid_code = generate_mermaid_sequence(trace)

    return ResponseBase(
        code=200, message="success", data=mermaid_code, request_id=request_id
    )


@router.post(
    "/rag/execute",
    summary="使用 RAG Agent 执行知识检索",
    description="使用 LangGraph RAG Agent 进行知识库检索问答，支持流式输出",
    response_model=ResponseBase,
)
async def chat_with_rag_agent(
    request: Request,
    agent_request: AgentRequest,
):
    """
    使用 RAG Agent 执行知识检索问答

    状态机流程：
    START → analyze → [rag_tool if knowledge] → response → END

    - 知识型问题自动调用 rag_search 工具检索知识库
    - 闲聊/计算问题直接回答
    - 返回结果强制附加引用 ID，缺失引用时标记置信度 low

    Args:
        request: FastAPI 请求对象
        agent_request: 聊天请求

    Returns:
        包含响应内容、引用和置信度的结构化结果
    """
    request_id = request.state.request_id
    thread_id = agent_request.session_id or str(uuid4())

    logger.info(
        f"[ChatAPI] POST /rag/execute - prompt='{agent_request.prompt}', thread_id='{thread_id}'"
    )

    try:
        result = await run_rag_agent(agent_request.prompt, thread_id)

        final_response = result.get("final_response", "")
        rag_confidence = result.get("rag_confidence", "low")
        rag_references = result.get("rag_references", [])

        logger.info(
            f"[ChatAPI] RAG Agent result: confidence={rag_confidence}, references={len(rag_references)}"
        )

        return ResponseBase(
            code=200,
            message="success",
            data={
                "prompt": agent_request.prompt,
                "response": final_response,
                "session_id": thread_id,
                "confidence": rag_confidence,
                "references": rag_references,
            },
            request_id=request_id,
        )

    except Exception as e:
        logger.error(f"[ChatAPI] RAG Agent error: {str(e)}")
        return ResponseBase(
            code=500,
            message=f"RAG Agent 执行失败: {str(e)}",
            data=None,
            request_id=request_id,
        )


@router.post(
    "/rag/execute/stream",
    summary="使用 RAG Agent 流式执行知识检索",
    description="使用 LangGraph RAG Agent 进行流式知识库检索问答",
    response_model=ResponseBase,
)
async def chat_with_rag_agent_stream(
    request: Request,
    agent_request: AgentRequest,
):
    """
    使用 RAG Agent 流式执行知识检索问答

    返回 SSE (Server-Sent Events) 流式响应，每个 chunk 包含节点名称和状态信息。

    Args:
        request: FastAPI 请求对象
        agent_request: 聊天请求

    Returns:
        SSE 流式响应
    """
    from fastapi.responses import StreamingResponse
    import json

    request_id = request.state.request_id
    thread_id = agent_request.session_id or str(uuid4())

    logger.info(
        f"[ChatAPI] POST /rag/execute/stream - prompt='{agent_request.prompt}', thread_id='{thread_id}'"
    )

    async def event_generator():
        try:
            async for chunk in run_rag_agent_stream(agent_request.prompt, thread_id):
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"[ChatAPI] RAG Agent stream error: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Request-ID": request_id,
        },
    )


@router.get(
    "/rag/sessions/{thread_id}",
    summary="查询 RAG Agent 会话信息",
    description="查询指定线程的 RAG Agent 会话状态",
    response_model=ResponseBase,
)
async def get_rag_session(
    request: Request,
    thread_id: str,
):
    """
    查询 RAG Agent 会话信息

    Args:
        request: FastAPI 请求对象
        thread_id: 线程ID

    Returns:
        会话状态信息
    """
    request_id = request.state.request_id

    session_info = await get_rag_session_info(thread_id)

    return ResponseBase(
        code=200, message="success", data=session_info, request_id=request_id
    )


@router.get(
    "/rag/sessions/{thread_id}/trace",
    summary="获取 RAG Agent 执行轨迹",
    description="获取指定线程的 RAG Agent 执行轨迹",
    response_model=ResponseBase,
)
async def get_rag_execution_trace_endpoint(
    request: Request,
    thread_id: str,
):
    """
    获取 RAG Agent 执行轨迹

    Args:
        request: FastAPI 请求对象
        thread_id: 线程ID

    Returns:
        执行轨迹列表
    """
    request_id = request.state.request_id

    trace = get_rag_execution_trace(thread_id)

    return ResponseBase(code=200, message="success", data=trace, request_id=request_id)
