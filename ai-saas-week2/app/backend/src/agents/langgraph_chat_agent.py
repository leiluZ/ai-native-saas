"""
LangGraph Integration - Week2 Demo

将组件整合到 LangGraph 状态机中：
- llm_client: LLM 调用
- tool_registry: 工具注册和调用
- memory_manager: 对话记忆管理

集成 Human-in-the-Loop 审批机制：
- 置信度 < 0.7 时需要人工审批
- 使用条件边实现中断/恢复

节点设计：
- analyze_node: 解析用户输入，判断是否需要工具
- tool_node: 调用工具执行（带熔断器保护）
- approval_node: 审批节点，判断是否需要人工介入
- response_node: 生成最终回复
- memory_node: 保存对话历史，检查 token 预算

状态机流程：
START → analyze → [tool if needed] → approval → [response or END] → memory → END
"""

import logging
import re
from datetime import datetime
from typing import TypedDict, Annotated, Sequence, Literal, Optional, Dict, Any
from langgraph.graph import StateGraph, END, START
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.checkpoint.memory import MemorySaver
import operator

from .llm_client import get_llm
from .tool_registry import tool_registry
from app.utils.circuit_breaker import global_circuit_breaker, CircuitBreakerError

logger = logging.getLogger(__name__)

# 全局 checkpointer
_global_checkpointer = None


def _get_checkpointer():
    """获取全局 checkpointer 实例"""
    global _global_checkpointer
    if _global_checkpointer is None:
        _global_checkpointer = MemorySaver()
    return _global_checkpointer


CONFIDENCE_THRESHOLD = 0.7


class AgentState(TypedDict):
    """LangGraph 状态 schema，包含 Human-in-the-Loop 审批字段"""

    messages: Annotated[Sequence[BaseMessage], operator.add]
    user_input: str
    needs_tool: bool
    tool_name: str
    tool_args: Dict[str, Any]
    tool_result: str
    confidence: float
    needs_approval: bool
    approved: bool
    pending_approval: bool
    modified_result: Optional[str]
    original_result: Optional[str]
    final_response: str
    conversation_history: list[dict]
    total_tokens: int
    needs_summarization: bool


def calculate_confidence(result: str, tool_name: str) -> float:
    """
    计算结果置信度 (0.0 - 1.0)

    基于以下规则计算置信度：
    - 结果非空: +0.3
    - 无错误关键词: +0.3
    - 结果格式正确: +0.2
    - 基础分: +0.2
    """
    confidence = 0.0

    # 结果非空
    if result and len(result) > 0:
        confidence += 0.3

    # 无错误关键词
    error_keywords = ["错误", "error", "失败", "failed", "未找到", "not found", "异常"]
    if not any(keyword in result.lower() for keyword in error_keywords):
        confidence += 0.3

    # 结果格式正确
    if tool_name == "get_weather":
        if any(unit in result for unit in ["°C", "°F", "℃", "温度"]):
            confidence += 0.2
    elif tool_name == "get_current_time":
        if any(unit in result for unit in [":", "时", "分", "AM", "PM"]):
            confidence += 0.2
    elif tool_name == "calculate":
        if re.search(r"[\d]", result):
            confidence += 0.2
    else:
        confidence += 0.2

    # 基础分
    confidence += 0.2

    return min(confidence, 1.0)


def analyze_node(state: AgentState) -> AgentState:
    """
    分析节点 - 解析用户输入，判断是否需要调用工具
    """
    messages = state.get("messages", [])
    user_input = state.get("user_input", "")

    if not messages:
        return {
            "needs_tool": False,
            "tool_name": "",
            "tool_args": {},
        }

    last_message = messages[-1]
    user_input = (
        last_message.content if hasattr(last_message, "content") else user_input
    )

    logger.info(f"[AnalyzeNode] user_input='{user_input}'")

    user_lower = user_input.lower()
    needs_tool = False
    tool_name = ""
    tool_args = {}

    if any(kw in user_lower for kw in ["天气", "weather", "温度", "climate"]):
        needs_tool = True
        tool_name = "get_weather"
        location = user_input
        for kw in ["天气", "weather", "的", "怎么样", "?"]:
            location = location.replace(kw, "").strip()
        tool_args = {"location": location if location else "Beijing"}
    elif any(kw in user_lower for kw in ["时间", "time", "几点", "现在"]):
        needs_tool = True
        tool_name = "get_current_time"
        tool_args = {"timezone": "Asia/Shanghai"}
    elif any(
        kw in user_lower for kw in ["计算", "calc", "+", "-", "*", "/", "=", "多少"]
    ):
        needs_tool = True
        tool_name = "calculate"
        calc_expr = user_input
        for kw in ["计算", "calc", "多少", "是"]:
            calc_expr = calc_expr.replace(kw, "").strip()
        calc_expr = re.sub(r"[^0-9+\-*/().]", "", calc_expr)
        tool_args = {"expression": calc_expr if calc_expr else "2+2"}

    logger.info(
        f"[AnalyzeNode] needs_tool={needs_tool}, tool_name='{tool_name}', tool_args={tool_args}"
    )

    return {
        "user_input": user_input,
        "needs_tool": needs_tool,
        "tool_name": tool_name,
        "tool_args": tool_args,
    }


async def tool_node(state: AgentState) -> AgentState:
    """
    工具节点 - 调用 tool_registry 执行工具（带熔断器保护）
    """
    tool_name = state.get("tool_name", "")
    tool_args = state.get("tool_args", {})

    logger.info(f"[ToolNode] tool_name='{tool_name}', tool_args={tool_args}")

    result = ""
    confidence = 0.0

    try:
        if tool_registry.has_tool(tool_name):

            async def invoke_tool():
                return tool_registry.invoke_tool(tool_name, tool_args)

            result = await global_circuit_breaker.call(invoke_tool)
        else:
            result = f"工具 {tool_name} 未注册"
            confidence = 0.3
    except CircuitBreakerError as e:
        result = "服务暂时不可用，请稍后重试"
        confidence = 0.1
        logger.error(f"[ToolNode] Circuit breaker error: {str(e)}")
    except Exception as e:
        result = f"工具调用失败: {str(e)}"
        confidence = 0.2
        logger.error(f"[ToolNode] Tool invocation error: {str(e)}")

    if confidence == 0.0:
        confidence = calculate_confidence(result, tool_name)

    logger.info(f"[ToolNode] result='{result}', confidence={confidence:.2f}")

    return {
        "tool_result": result,
        "confidence": confidence,
        "original_result": result,
        "messages": [AIMessage(content=f"工具执行结果: {result}")],
    }


def approval_node(state: AgentState) -> AgentState:
    """
    审批节点 - 判断是否需要人工审批

    当置信度 < 0.7 时设置 pending_approval=True，触发中断
    """
    confidence = state.get("confidence", 1.0)
    original_result = state.get("original_result", "")
    needs_tool = state.get("needs_tool", False)

    # 如果不需要工具，直接通过
    if not needs_tool:
        return {
            "needs_approval": False,
            "pending_approval": False,
            "approved": True,
        }

    needs_approval = confidence < CONFIDENCE_THRESHOLD
    pending_approval = needs_approval and not state.get("approved", False)

    logger.info(
        f"[ApprovalNode] confidence={confidence:.2f}, threshold={CONFIDENCE_THRESHOLD}, needs_approval={needs_approval}, pending_approval={pending_approval}"
    )

    if needs_approval and not pending_approval:
        logger.info("[ApprovalNode] High confidence, proceeding directly to response")

    return {
        "needs_approval": needs_approval,
        "pending_approval": pending_approval,
        "approved": state.get("approved", False),
        "original_result": original_result,
        "confidence": confidence,
    }


def reviewer_node(state: AgentState) -> AgentState:
    """
    审查节点 - 人工审批后的处理

    使用审批结果（原始结果或修改后的结果）
    """
    approved = state.get("approved", False)
    original_result = state.get("original_result", "")
    modified_result = state.get("modified_result", "")

    logger.info(
        f"[ReviewerNode] approved={approved}, modified_result='{modified_result}'"
    )

    final_result = (
        modified_result if (not approved and modified_result) else original_result
    )

    return {
        "final_response": f"[已审批] {final_result}",
        "messages": [AIMessage(content=f"[已审批] {final_result}")],
        "pending_approval": False,
    }


async def response_node(state: AgentState) -> AgentState:
    """
    响应节点 - 生成最终回复

    根据工具执行结果或调用 LLM 直接响应用户。
    """
    user_input = state.get("user_input", "")
    needs_tool = state.get("needs_tool", False)
    tool_result = state.get("tool_result", "")
    original_result = state.get("original_result", "")
    approved = state.get("approved", False)
    pending_approval = state.get("pending_approval", False)
    conversation_history = state.get("conversation_history", [])

    logger.info(
        f"[ResponseNode] needs_tool={needs_tool}, tool_result='{tool_result}', approved={approved}, pending_approval={pending_approval}"
    )

    # 如果有待审批且未审批，返回审批提示
    if pending_approval and not approved:
        confidence = state.get("confidence", 0.0)
        final_response = (
            f"[等待人工审批] 置信度={confidence:.2f} 原始结果: {original_result}"
        )
    elif needs_tool and tool_result:
        # 直接返回工具结果，不调用 LLM
        final_response = tool_result
    else:
        # 直接调用 LLM 生成响应
        final_response = await _generate_response_with_llm(
            user_input, "", conversation_history
        )

    logger.info(f"[ResponseNode] final_response='{final_response}'")

    return {
        "final_response": final_response,
        "messages": [AIMessage(content=final_response)],
    }


async def _generate_response_with_llm(
    user_input: str, tool_result: str = "", conversation_history: list = None
) -> str:
    """
    调用 LLM 生成自然语言响应

    Args:
        user_input: 用户输入
        tool_result: 工具执行结果（可选）
        conversation_history: 对话历史（可选）

    Returns:
        LLM 生成的响应
    """
    conversation_history = conversation_history or []

    # 构建历史上下文
    history_context = ""
    if conversation_history:
        history_items = []
        for item in conversation_history[-5:]:  # 只取最近5条
            role = "用户" if item["role"] == "user" else "助手"
            history_items.append(f"{role}: {item['content']}")
        history_context = "\n".join(history_items) + "\n\n"

    # 构建提示词
    if tool_result:
        system_prompt = f"""你是一个乐于助人的助手。根据以下工具执行结果，用自然、友好的语言回答用户的问题。

工具执行结果：
{tool_result}

请基于上述结果进行总结和回复。"""
    else:
        system_prompt = (
            """你是一个乐于助人的助手。请用自然、友好的语言回答用户的问题。"""
        )

    full_prompt = f"{system_prompt}\n\n{history_context}用户：{user_input}"

    try:
        llm = get_llm()
        response = await llm.ainvoke(full_prompt)
        return response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        logger.error(f"[ResponseNode] LLM invocation error: {str(e)}")
        if tool_result:
            return f"根据查询结果：\n{tool_result}"
        return f"我收到了你的消息: {user_input}"


TOKEN_THRESHOLD = 8000


def memory_node(state: AgentState) -> AgentState:
    """
    记忆节点 - 保存对话历史，检查 token 预算
    """
    conversation_history = state.get("conversation_history", [])
    total_tokens = state.get("total_tokens", 0)
    user_input = state.get("user_input", "")
    final_response = state.get("final_response", "")

    # 添加当前对话到历史
    if user_input and final_response:
        conversation_history.append(
            {
                "role": "user",
                "content": user_input,
                "timestamp": datetime.now().isoformat(),
            }
        )
        conversation_history.append(
            {
                "role": "assistant",
                "content": final_response,
                "timestamp": datetime.now().isoformat(),
            }
        )

    # 计算 token 数量（简化计算）
    total_tokens += len(user_input) + len(final_response)

    # 检查是否需要摘要
    needs_summarization = total_tokens > TOKEN_THRESHOLD

    logger.info(
        f"[MemoryNode] history_len={len(conversation_history)}, total_tokens={total_tokens}, needs_summarization={needs_summarization}"
    )

    return {
        "conversation_history": conversation_history,
        "total_tokens": total_tokens,
        "needs_summarization": needs_summarization,
    }


def should_call_tool(state: AgentState) -> Literal["tool", "approval"]:
    """
    条件边函数 - 决定是否调用工具

    Returns:
        "tool": 需要调用工具
        "approval": 直接进入审批节点（不需要工具）
    """
    needs_tool = state.get("needs_tool", False)
    next_node = "tool" if needs_tool else "approval"
    logger.info(f"[ShouldCallTool] needs_tool={needs_tool} -> next_node='{next_node}'")
    return next_node


def approval_decision(state: AgentState) -> Literal["response", "reviewer", "__end__"]:
    """
    条件边函数 - 审批决策

    Returns:
        "response": 直接执行响应节点（置信度足够或等待审批提示）
        "reviewer": 进入审查节点（已审批）
        "__end__": 结束
    """
    pending_approval = state.get("pending_approval", False)
    approved = state.get("approved", False)

    if pending_approval and not approved:
        # 置信度不足但无人审批时，进入response节点返回等待审批提示
        logger.info(
            f"[ApprovalDecision] pending_approval={pending_approval}, approved={approved} -> response (等待审批提示)"
        )
        return "response"
    elif approved:
        logger.info(
            f"[ApprovalDecision] pending_approval={pending_approval}, approved={approved} -> reviewer"
        )
        return "reviewer"
    else:
        logger.info(
            f"[ApprovalDecision] pending_approval={pending_approval}, approved={approved} -> response"
        )
        return "response"


def build_langgraph_integration() -> StateGraph:
    """
    构建 LangGraph 状态机（带 Human-in-the-Loop）

    状态机结构：
    START → analyze → [tool if needed] → approval → [response or END] → memory → END
    """
    graph = StateGraph(AgentState)

    # 添加节点
    graph.add_node("analyze", analyze_node)
    graph.add_node("tool", tool_node)
    graph.add_node("approval", approval_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("response", response_node)
    graph.add_node("memory", memory_node)

    # 添加边
    graph.add_edge(START, "analyze")
    graph.add_conditional_edges(
        "analyze",
        should_call_tool,
        {
            "tool": "tool",
            "approval": "approval",
        },
    )
    graph.add_edge("tool", "approval")
    graph.add_conditional_edges(
        "approval",
        approval_decision,
        {
            "response": "response",
            "reviewer": "reviewer",
            "__end__": END,
        },
    )
    # reviewer 节点在更新审批后使用，连接到 response
    graph.add_edge("reviewer", "response")
    graph.add_edge("response", "memory")
    graph.add_edge("memory", END)

    # 编译图
    checkpointer = _get_checkpointer()
    compiled_graph = graph.compile(checkpointer=checkpointer)

    logger.info("[LangGraph] Graph compiled successfully with Human-in-the-Loop")
    return compiled_graph


# 全局图实例
_langgraph = None


def get_langgraph_graph():
    """获取 LangGraph 图的单例实例"""
    global _langgraph
    if _langgraph is None:
        _langgraph = build_langgraph_integration()
    return _langgraph


async def run_langgraph(user_input: str, thread_id: str = "default") -> dict:
    """
    运行 LangGraph 状态机

    Args:
        user_input: 用户输入
        thread_id: 会话 ID

    Returns:
        执行结果
    """
    graph = get_langgraph_graph()
    config = {"configurable": {"thread_id": thread_id}}

    # 只传递新输入，LangGraph 会通过 checkpointer 自动恢复之前的状态
    # messages 字段的 operator.add 会自动将新消息添加到历史记录中
    initial_state = {
        "messages": [HumanMessage(content=user_input)],
        "user_input": user_input,
        "approved": False,
        "pending_approval": False,
    }

    result = await graph.ainvoke(initial_state, config)

    return result


async def update_approval(
    thread_id: str, approved: bool, modified_result: str = None
) -> dict:
    """
    更新审批状态

    Args:
        thread_id: 会话 ID
        approved: 是否批准
        modified_result: 修改后的结果（当不批准时使用）

    Returns:
        审批后的结果
    """
    checkpointer = _get_checkpointer()
    config = {"configurable": {"thread_id": thread_id}}

    state = await checkpointer.aget(config)
    if not state or "channel_values" not in state:
        return {"final_response": "会话不存在", "total_tokens": 0}

    checkpoint_data = state["channel_values"]
    original_result = checkpoint_data.get("original_result", "")
    final_result = (
        modified_result if (not approved and modified_result) else original_result
    )

    updates = {
        "approved": approved,
        "pending_approval": False,
        "modified_result": modified_result,
        "final_response": (
            f"[已审批] {final_result}"
            if approved
            else f"[已拒绝] {modified_result or final_result}"
        ),
    }

    graph = get_langgraph_graph()
    graph.update_state(config, updates, as_node="approval")

    return {
        "final_response": (
            f"[已审批] {final_result}"
            if approved
            else f"[已拒绝] {modified_result or final_result}"
        ),
        "total_tokens": checkpoint_data.get("total_tokens", 0),
    }


async def get_approval_status(thread_id: str) -> Optional[dict]:
    """
    查询审批状态

    Args:
        thread_id: 会话 ID

    Returns:
        审批状态信息，如果不存在返回 None
    """
    checkpointer = _get_checkpointer()

    try:
        config = {"configurable": {"thread_id": thread_id}}
        state = await checkpointer.aget(config)

        # MemorySaver 返回的数据结构中，状态值在 'channel_values' 键中
        if not state or "channel_values" not in state:
            return None

        checkpoint_data = state["channel_values"]
        pending_approval = checkpoint_data.get("pending_approval", False)
        approved = checkpoint_data.get("approved", False)
        confidence = checkpoint_data.get("confidence", 1.0)
        original_result = checkpoint_data.get("original_result", "")
        modified_result = checkpoint_data.get("modified_result")

        status = "none"
        if pending_approval:
            status = "pending"
        elif approved:
            status = "approved"
        elif modified_result:
            status = "rejected"

        return {
            "thread_id": thread_id,
            "approved": approved,
            "original_result": original_result,
            "modified_result": modified_result,
            "confidence": confidence,
            "status": status,
            "pending_approval": pending_approval,
        }
    except Exception as e:
        logger.error(f"[LangGraph] Error getting approval status: {str(e)}")
        return None


async def get_session_info(thread_id: str) -> Optional[dict]:
    """
    查询会话信息

    Args:
        thread_id: 会话 ID

    Returns:
        会话信息，包含历史记录和状态
    """
    checkpointer = _get_checkpointer()

    try:
        config = {"configurable": {"thread_id": thread_id}}
        state = await checkpointer.aget(config)

        # MemorySaver 返回的数据结构中，状态值在 'channel_values' 键中
        if not state or "channel_values" not in state:
            return None

        checkpoint_data = state["channel_values"]

        return {
            "thread_id": thread_id,
            "conversation_history": checkpoint_data.get("conversation_history", []),
            "total_tokens": checkpoint_data.get("total_tokens", 0),
            "needs_summarization": checkpoint_data.get("needs_summarization", False),
            "pending_approval": checkpoint_data.get("pending_approval", False),
            "confidence": checkpoint_data.get("confidence", 1.0),
        }
    except Exception as e:
        logger.error(f"[LangGraph] Error getting session info: {str(e)}")
        return None


# 导出
__all__ = [
    "AgentState",
    "calculate_confidence",
    "analyze_node",
    "tool_node",
    "approval_node",
    "reviewer_node",
    "response_node",
    "memory_node",
    "build_langgraph_integration",
    "get_langgraph_graph",
    "run_langgraph",
    "update_approval",
    "get_approval_status",
    "get_session_info",
]
