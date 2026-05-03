"""
LangGraph Router -> Executor -> Reviewer 协作链 - Day 2

本模块展示 LangGraph 的多节点协作：
- RouterNode: 路由判断（weather/time/calc/general）
- ExecutorNode: 执行工具
- ReviewerNode: 结果审查与重试
- conditional_edges: 条件边实现路由
"""
from typing import TypedDict, Annotated, Sequence
from typing import Literal
from langgraph.graph import StateGraph, END, START
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
import operator

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.agents.tool_registry import tool_registry


class AgentState(TypedDict):
    """Agent 状态 schema"""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    route: str
    tool_name: str
    tool_input: str
    approved: bool


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
        return {"route": "general", "tool_name": "", "tool_input": "", "approved": False}

    last_message = messages[-1]
    user_input = last_message.content if hasattr(last_message, 'content') else ""

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
    elif any(kw in user_lower for kw in ["计算", "calc", "+", "-", "*", "/", "=", "多少"]):
        route = "calc"
        tool_name = "calculate"
        calc_expr = user_input
        for kw in ["计算", "calc", "多少", "是"]:
            calc_expr = calc_expr.replace(kw, "").strip()
        import re
        calc_expr = re.sub(r'[^0-9+\-*/().]', '', calc_expr)
        tool_input = calc_expr if calc_expr else "2+2"
    else:
        route = "general"
        tool_name = ""
        tool_input = ""

    return {
        "route": route,
        "tool_name": tool_name,
        "tool_input": tool_input,
        "approved": False
    }


def executor_node(state: AgentState) -> AgentState:
    """
    执行器节点 - 执行路由决定的工具

    Args:
        state: 当前状态

    Returns:
        更新后的状态
    """
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
            result = tool_registry.invoke_tool(tool_name, {"expression": tool_input} if route == "calc" else {"location": tool_input} if route == "weather" else {"timezone": tool_input})
            result_message = result
        except Exception as e:
            result_message = f"执行错误: {str(e)}"
    else:
        result_message = f"未找到工具: {tool_name}"

    return {"messages": [AIMessage(content=result_message)]}


def reviewer_node(state: AgentState) -> AgentState:
    """
    审查节点 - 检查结果是否合理

    规则: 结果长度必须 > 5 字符

    Args:
        state: 当前状态

    Returns:
        更新后的状态
    """
    messages = state.get("messages", [])

    if not messages:
        return {"approved": False}

    last_result = messages[-1].content if hasattr(messages[-1], 'content') else str(messages[-1])

    approved = len(last_result) > 5
    return {"approved": approved}


def route_decision(state: AgentState) -> Literal["executor", "reviewer"]:
    """
    条件边函数 - 决定下一步

    Args:
        state: 当前状态

    Returns:
        下一个节点名称
    """
    if state.get("route") == "general":
        return "reviewer"
    return "executor"


def review_decision(state: AgentState) -> Literal["executor", END]:
    """
    审查决策边 - 决定是否通过

    Args:
        state: 当前状态

    Returns:
        END 结束，或重新执行 executor
    """
    if state.get("approved", False):
        return END
    return END


def build_collaboration_graph() -> StateGraph:
    """
    构建协作链图

    Returns:
        编译好的 StateGraph
    """
    graph = StateGraph(AgentState)

    graph.add_node("router", router_node)
    graph.add_node("executor", executor_node)
    graph.add_node("reviewer", reviewer_node)

    graph.add_edge(START, "router")

    graph.add_conditional_edges(
        "router",
        route_decision,
        {
            "executor": "executor",
            "reviewer": "reviewer"
        }
    )

    graph.add_conditional_edges(
        "reviewer",
        review_decision,
        {
            "executor": "executor",
            END: END
        }
    )

    graph.add_edge("executor", "reviewer")

    return graph.compile()


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
    COND1 -->|general| REVIEWER[reviewer<br/>审查节点]
    EXECUTOR --> REVIEWER
    REVIEWER -->|retry decision| COND2{条件判断}
    COND2 -->|retry <= 2| EXECUTOR
    COND2 -->|retry > 2| END([结束])
```"""


async def execute_example():
    """执行示例"""
    print("=== LangGraph Router -> Executor -> Reviewer 示例 ===\n")

    print("1. 图结构:")
    print(get_graph_diagram())

    print("\n2. 创建图...")
    app = build_collaboration_graph()

    test_cases = [
        ("北京的天气怎么样？", "天气查询"),
        ("现在几点了？", "时间查询"),
        ("计算 2+3*4", "计算查询"),
        ("你好！", "通用查询"),
    ]

    for user_input, description in test_cases:
        print(f"\n3. 测试 [{description}]: {user_input}")
        result = app.invoke({
            "messages": [HumanMessage(content=user_input)],
            "route": "",
            "tool_name": "",
            "tool_input": "",
            "approved": False
        })
        print(f"   路由: {result.get('route')}")
        print(f"   审核通过: {result.get('approved')}")
        print(f"   最终回复: {result['messages'][-1].content}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(execute_example())
