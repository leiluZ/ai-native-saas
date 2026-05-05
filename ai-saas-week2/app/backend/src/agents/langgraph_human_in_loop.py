"""
LangGraph Human-in-the-Loop 机制 - Day 2

本模块展示如何在 LangGraph 中实现 Human-in-the-Loop：
- ApprovalNode: 当置信度 < 0.7 时返回 Command(goto=END) 暂停图执行
- MemorySaver: 状态持久化
- Command(goto=END): LangGraph 原生的暂停/恢复机制
- /api/v1/chat/approve: 审批接口
"""

import logging
from typing import TypedDict, Annotated, Sequence, Literal, Optional, Dict, Any
from langgraph.graph import StateGraph, END, START
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.checkpoint.memory import MemorySaver
import operator
import re

logger = logging.getLogger(__name__)

_global_checkpointer = None


def _get_checkpointer():
    """获取全局 checkpointer 实例，确保所有图实例共享同一个 checkpointer"""
    global _global_checkpointer
    if _global_checkpointer is None:
        _global_checkpointer = MemorySaver()
    return _global_checkpointer


class AgentState(TypedDict):
    """Agent 状态 schema，包含 human-in-the-loop 相关字段"""

    messages: Annotated[Sequence[BaseMessage], operator.add]
    route: str
    tool_name: str
    tool_input: str
    confidence: float
    needs_approval: bool
    approved: bool
    pending_approval: bool
    modified_result: Optional[str]
    original_result: Optional[str]


def calculate_confidence(result: str, tool_name: str) -> float:
    """
    计算结果置信度

    基于以下规则计算置信度：
    - 结果非空: +0.3
    - 无错误关键词: +0.3
    - 结果格式正确: +0.2
    - 工具执行成功: +0.2

    Args:
        result: 工具执行结果
        tool_name: 工具名称

    Returns:
        置信度分数 (0.0 - 1.0)
    """
    confidence = 0.0

    if result and len(result) > 0:
        confidence += 0.3

    error_keywords = ["错误", "error", "失败", "failed", "未找到", "not found", "异常"]
    if not any(keyword in result.lower() for keyword in error_keywords):
        confidence += 0.3

    if tool_name == "get_weather":
        if any(unit in result for unit in ["°C", "°F", "℃", "温度"]):
            confidence += 0.2
    elif tool_name == "get_current_time":
        if any(unit in result for unit in [":", "时", "分", "AM", "PM"]):
            confidence += 0.2
    elif tool_name == "calculate":
        if re.search(r"[\d]", result):
            confidence += 0.2

    confidence += 0.2

    return min(confidence, 1.0)


def router_node(state: AgentState) -> AgentState:
    """
    路由节点 - 分析用户输入，决定路由到哪个工具

    Args:
        state: 当前状态

    Returns:
        更新后的状态
    """
    messages = state.get("messages", [])
    if not messages:
        return {
            "route": "general",
            "tool_name": "",
            "tool_input": "",
            "confidence": 1.0,
            "needs_approval": False,
            "approved": False,
            "modified_result": None,
            "original_result": None,
        }

    last_message = messages[-1]
    user_input = last_message.content if hasattr(last_message, "content") else ""

    route = "general"
    tool_name = ""
    tool_input = ""

    user_lower = user_input.lower()

    if any(kw in user_lower for kw in ["天气", "weather", "温度", "climate"]):
        route = "weather"
        tool_name = "get_weather"
        location = user_input
        for kw in ["天气", "weather", "的", "怎么样", "?"]:
            location = location.replace(kw, "").strip()
        tool_input = location if location else "Beijing"
    elif any(kw in user_lower for kw in ["时间", "time", "几点", "现在"]):
        route = "time"
        tool_name = "get_current_time"
        tool_input = "Asia/Shanghai"
    elif any(
        kw in user_lower for kw in ["计算", "calc", "+", "-", "*", "/", "=", "多少"]
    ):
        route = "calc"
        tool_name = "calculate"
        calc_expr = user_input
        for kw in ["计算", "calc", "多少", "是"]:
            calc_expr = calc_expr.replace(kw, "").strip()
        calc_expr = re.sub(r"[^0-9+\-*/().]", "", calc_expr)
        tool_input = calc_expr if calc_expr else "2+2"
    else:
        route = "general"
        tool_name = ""
        tool_input = ""

    logger.info(
        f"[RouterNode] user_input='{user_input}' -> route='{route}', tool_name='{tool_name}', tool_input='{tool_input}'"
    )

    return {
        "route": route,
        "tool_name": tool_name,
        "tool_input": tool_input,
        "confidence": 1.0,
        "needs_approval": False,
        "approved": False,
        "pending_approval": False,
        "modified_result": None,
        "original_result": None,
    }


def executor_node(state: AgentState) -> AgentState:
    """
    执行器节点 - 执行路由决定的工具

    Args:
        state: 当前状态

    Returns:
        更新后的状态
    """
    from app.agents.tool_registry import tool_registry

    route = state.get("route", "general")
    tool_name = state.get("tool_name", "")
    tool_input = state.get("tool_input", "")
    messages = state.get("messages", [])

    result_message = ""

    if route == "general":
        response = f"我收到了你的消息: {messages[-1].content if messages else '无内容'}"
        result_message = response
    elif tool_name and tool_registry.has_tool(tool_name):
        try:
            result = tool_registry.invoke_tool(
                tool_name,
                (
                    {"expression": tool_input}
                    if route == "calc"
                    else (
                        {"location": tool_input}
                        if route == "weather"
                        else {"timezone": tool_input}
                    )
                ),
            )
            result_message = result
        except Exception as e:
            result_message = f"执行错误: {str(e)}"
    else:
        result_message = f"未找到工具: {tool_name}"

    confidence = calculate_confidence(result_message, tool_name)

    logger.info(
        f"[ExecutorNode] route='{route}', tool_name='{tool_name}', tool_input='{tool_input}' -> result='{result_message}', confidence={confidence:.2f}"
    )

    return {
        "messages": [AIMessage(content=result_message)],
        "confidence": confidence,
        "original_result": result_message,
    }


def approval_node(state: AgentState) -> AgentState:
    """
    审批节点 - 当置信度 < 0.7 时暂停，等待人工审批

    LangGraph 原生机制：
    - 返回状态字典让图继续执行
    - 当 pending_approval=True 时，下一个节点由条件边决定
    - 使用 MemorySaver 保存状态

    Args:
        state: 当前状态

    Returns:
        更新后的状态
    """
    confidence = state.get("confidence", 1.0)
    pending_approval = state.get("pending_approval", False)

    logger.info(
        f"[ApprovalNode] confidence={confidence:.2f}, pending_approval={pending_approval}, threshold=0.7"
    )

    if confidence < 0.7:
        if not pending_approval:
            logger.info("[ApprovalNode] Low confidence, setting pending_approval=True")
            return {
                **state,
                "pending_approval": True,
                "needs_approval": True,
                "approved": False,
            }
        else:
            logger.info(
                "[ApprovalNode] Already pending approval, checking if approved..."
            )
            approved = state.get("approved", False)
            if approved:
                logger.info("[ApprovalNode] User approved, proceeding to reviewer")
                return {**state, "pending_approval": False}
            else:
                logger.info("[ApprovalNode] User rejected, still waiting")
                return {**state}

    logger.info("[ApprovalNode] High confidence, proceeding directly to reviewer")
    return {**state, "pending_approval": False}


def reviewer_node(state: AgentState) -> AgentState:
    """
    审查节点 - 基于人工审批决定最终结果

    LangGraph 原生 checkpoint 机制：
    - 状态存储在 MemorySaver checkpointer 中
    - 外部通过 get_state/update_state 管理审批

    Args:
        state: 当前状态

    Returns:
        更新后的状态
    """
    messages = state.get("messages", [])
    approved = state.get("approved", False)
    modified_result = state.get("modified_result", None)
    original_result = state.get("original_result", "")
    pending_approval = state.get("pending_approval", False)

    if not messages:
        return {"approved": False, "pending_approval": False}

    if approved and modified_result:
        final_result = modified_result
    else:
        final_result = original_result

    if approved:
        logger.info(f"[ReviewerNode] User approved, final_result='{final_result}'")
        return {
            "messages": [AIMessage(content=f"[已人工审批] {final_result}")],
            "pending_approval": False,
        }
    elif pending_approval:
        logger.info(
            f"[ReviewerNode] Still pending approval, returning original_result='{final_result}'"
        )
        return {
            "messages": [AIMessage(content=f"[等待人工审批] {final_result}")],
            "pending_approval": True,
        }
    else:
        logger.info(
            f"[ReviewerNode] Auto approved (high confidence), final_result='{final_result}'"
        )
        return {
            "messages": [AIMessage(content=final_result)],
            "pending_approval": False,
        }


def route_decision(state: AgentState) -> Literal["executor", "reviewer"]:
    """
    条件边函数 - 决定下一步

    Args:
        state: 当前状态

    Returns:
        下一个节点名称
    """
    route = state.get("route", "general")
    next_node = "reviewer" if route == "general" else "executor"
    logger.info(f"[RouteDecision] route='{route}' -> next_node='{next_node}'")
    return next_node


def approval_decision(state: AgentState) -> Literal["reviewer", "__end__"]:
    """
    审批条件边函数 - 决定审批后的下一步

    Args:
        state: 当前状态

    Returns:
        下一个节点名称或 END
    """
    pending_approval = state.get("pending_approval", False)
    approved = state.get("approved", False)

    if pending_approval and not approved:
        logger.info(
            f"[ApprovalDecision] pending_approval={pending_approval}, approved={approved} -> END (等待审批)"
        )
        return "__end__"
    else:
        logger.info(
            f"[ApprovalDecision] pending_approval={pending_approval}, approved={approved} -> reviewer"
        )
        return "reviewer"


def build_human_in_loop_graph() -> StateGraph:
    """
    构建带 Human-in-the-Loop 的协作链图

    Returns:
        编译好的 StateGraph，使用 MemorySaver 检查点
    """
    graph = StateGraph(AgentState)

    graph.add_node("router", router_node)
    graph.add_node("executor", executor_node)
    graph.add_node("approval", approval_node)
    graph.add_node("reviewer", reviewer_node)

    graph.add_edge(START, "router")

    graph.add_conditional_edges(
        "router", route_decision, {"executor": "executor", "reviewer": "reviewer"}
    )

    graph.add_edge("executor", "approval")

    graph.add_conditional_edges(
        "approval", approval_decision, {"reviewer": "reviewer", "__end__": END}
    )

    graph.add_edge("reviewer", END)

    checkpointer = _get_checkpointer()
    compiled_graph = graph.compile(checkpointer=checkpointer)

    checkpoint_manager.graph = compiled_graph

    return compiled_graph


class CheckpointManager:
    """
    基于 LangGraph Checkpoint 的审批管理器

    使用 LangGraph 原生的 checkpoint 机制来管理 human-in-the-loop：
    - checkpointer 保存图状态
    - 外部通过 get_state 获取中断状态
    - 外部通过 update_state 更新审批结果
    - 调用 ainvoke(resume_input, config) 恢复执行
    """

    def __init__(self):
        self.graph = None
        self._graph_builder = None

    def set_graph_builder(self, builder_func):
        """设置图构建器"""
        self._graph_builder = builder_func

    def get_graph(self):
        """获取编译好的图"""
        if self.graph is None and self._graph_builder:
            self.graph = self._graph_builder()
        return self.graph

    def is_interrupted(self, thread_id: str) -> bool:
        """
        检查线程是否处于中断状态

        Args:
            thread_id: 线程ID

        Returns:
            是否处于中断状态
        """
        graph = self.get_graph()
        if not graph:
            return False

        config = {"configurable": {"thread_id": thread_id}}
        try:
            state = graph.get_state(config)
            if state and state.tasks:
                for task in state.tasks:
                    if task.state and task.state.get("pending_approval"):
                        return True
        except Exception:
            pass
        return False

    def get_pending_state(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """
        获取待审批的状态

        Args:
            thread_id: 线程ID

        Returns:
            包含状态信息的字典，如果不存在返回 None
        """
        graph = self.get_graph()
        if not graph:
            return None

        config = {"configurable": {"thread_id": thread_id}}
        try:
            state = graph.get_state(config)
            if state and state.values:
                values = state.values
                if (
                    values.get("pending_approval")
                    and values.get("confidence", 1.0) < 0.7
                ):
                    return {
                        "thread_id": thread_id,
                        "messages": values.get("messages", []),
                        "original_result": values.get("original_result", ""),
                        "confidence": values.get("confidence", 0.0),
                        "approved": values.get("approved", False),
                        "modified_result": values.get("modified_result"),
                        "needs_approval": values.get("needs_approval", True),
                    }
        except Exception as e:
            logger.error(f"[CheckpointManager] Error getting state: {e}")
        return None

    def update_approval(
        self,
        thread_id: str,
        approved: bool,
        modified_result: Optional[str] = None,
    ) -> bool:
        """
        更新审批状态（不恢复执行）

        Args:
            thread_id: 线程ID
            approved: 是否批准
            modified_result: 修改后的结果

        Returns:
            是否成功更新
        """
        graph = self.get_graph()
        if not graph:
            return False

        config = {"configurable": {"thread_id": thread_id}}
        updates = {
            "approved": approved,
            "modified_result": modified_result,
        }

        try:
            graph.update_state(config, updates)
            return True
        except Exception as e:
            logger.error(f"[CheckpointManager] Error updating state: {e}")
            return False

    async def resume_and_get_result(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """
        恢复图执行并获取结果

        Args:
            thread_id: 线程ID

        Returns:
            图执行结果
        """
        graph = self.get_graph()
        if not graph:
            return None

        config = {"configurable": {"thread_id": thread_id}}
        try:
            result = await graph.ainvoke(None, config)
            return result
        except Exception as e:
            logger.error(f"[CheckpointManager] Error resuming graph: {e}")
            return None

    def clear_thread(self, thread_id: str) -> bool:
        """
        清除线程状态

        Args:
            thread_id: 线程ID

        Returns:
            是否成功清除
        """
        graph = self.get_graph()
        if not graph or not hasattr(graph, "checkpointer"):
            return False

        try:
            checkpointer = graph.checkpointer
            if hasattr(checkpointer, "store") and thread_id in checkpointer.store:
                del checkpointer.store[thread_id]
                logger.info(
                    f"[CheckpointManager] Cleared checkpoint for thread_id='{thread_id}'"
                )
                return True
        except Exception as e:
            logger.error(f"[CheckpointManager] Error clearing thread: {e}")
        return False

    def is_completed(self, thread_id: str) -> bool:
        """
        检查线程是否已完成（无待处理的 checkpoint）

        Args:
            thread_id: 线程ID

        Returns:
            是否已完成
        """
        graph = self.get_graph()
        if not graph:
            return True

        config = {"configurable": {"thread_id": thread_id}}
        try:
            state = graph.get_state(config)
            if state is None:
                return True
            if state.tasks:
                for task in state.tasks:
                    if task.state and task.state.get("pending_approval"):
                        return False
            return True
        except Exception:
            return True


checkpoint_manager = CheckpointManager()


def get_graph_diagram() -> str:
    """
    获取 Mermaid 格式的图

    Returns:
        Mermaid 图代码
    """
    return """```mermaid
graph TD
    START([开始]) --> ROUTER[router<br/>路由节点]
    ROUTER -->|route decision| COND1{条件判断}
    COND1 -->|weather/time/calc| EXECUTOR[executor<br/>执行器节点]
    COND1 -->|general| APPROVAL{approval<br/>审批节点}
    EXECUTOR --> APPROVAL
    APPROVAL -->|confidence < 0.7| INTERRUPT([中断<br/>等待人工审批])
    INTERRUPT -->|/api/v1/chat/approve| APPROVAL
    APPROVAL -->|confidence >= 0.7| REVIEWER[reviewer<br/>审查节点]
    REVIEWER --> END([结束])
```"""


async def execute_example():
    """执行示例"""
    print("=== LangGraph Human-in-the-Loop 示例 ===\n")

    print("1. 图结构:")
    print(get_graph_diagram())

    print("\n2. 构建图...")
    graph = build_human_in_loop_graph()

    print("\n3. 执行低置信度示例 (置信度 < 0.7)...")
    config = {"configurable": {"thread_id": "test-low-confidence"}}

    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="天气xyzabc123")]}, config
    )
    print(f"   结果: {result.get('messages', [])[-1].content}")
    print(f"   置信度: {result.get('confidence', 0)}")

    print("\n4. 执行高置信度示例 (置信度 >= 0.7)...")
    config = {"configurable": {"thread_id": "test-high-confidence"}}

    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="计算 2+2")]}, config
    )
    print(f"   结果: {result.get('messages', [])[-1].content}")
    print(f"   置信度: {result.get('confidence', 0)}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(execute_example())
