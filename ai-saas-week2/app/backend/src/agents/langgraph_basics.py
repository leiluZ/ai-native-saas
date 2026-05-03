"""
LangGraph 基础示例 - Day 1

本模块展示 LangGraph 的核心概念：
- State Schema (AgentState)
- Nodes (greet_node, process_node, respond_node)
- Edges (连接节点的边)
- 状态机编译与执行
"""

from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END, START
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
import operator


class AgentState(TypedDict):
    """Agent 状态 schema"""

    messages: Annotated[Sequence[BaseMessage], operator.add]
    next_action: str
    session_id: str


def greet_node(state: AgentState) -> AgentState:
    """
    问候节点 - 返回欢迎消息

    Args:
        state: 当前状态

    Returns:
        更新后的状态
    """
    greeting = AIMessage(content="你好！我是 LangGraph 助手。有什么我可以帮助你的吗？")
    return {"messages": [greeting], "next_action": "process"}


def process_node(state: AgentState) -> AgentState:
    """
    处理节点 - 处理用户输入

    Args:
        state: 当前状态

    Returns:
        更新后的状态
    """
    messages = state.get("messages", [])
    if not messages:
        return {"messages": [], "next_action": "respond"}

    last_message = messages[-1]
    user_input = (
        last_message.content if hasattr(last_message, "content") else str(last_message)
    )

    processed = f"已处理: {user_input}"
    return {"messages": [AIMessage(content=processed)], "next_action": "respond"}


def respond_node(state: AgentState) -> AgentState:
    """
    响应节点 - 生成最终响应

    Args:
        state: 当前状态

    Returns:
        更新后的状态
    """
    messages = state.get("messages", [])
    if not messages:
        return {"messages": [], "next_action": END}

    last_message = messages[-1]
    content = (
        last_message.content if hasattr(last_message, "content") else str(last_message)
    )

    response = AIMessage(content=f"最终回复: {content}")
    return {"messages": [response], "next_action": END}


def should_continue(state: AgentState) -> str:
    """
    条件边函数 - 决定下一步

    Args:
        state: 当前状态

    Returns:
        下一个节点名称或 END
    """
    return state.get("next_action", END)


def build_graph() -> StateGraph:
    """
    构建状态机图

    Returns:
        编译好的 StateGraph
    """
    graph = StateGraph(AgentState)

    graph.add_node("greet", greet_node)
    graph.add_node("process", process_node)
    graph.add_node("respond", respond_node)

    graph.add_edge(START, "greet")
    graph.add_conditional_edges(
        "greet", should_continue, {"process": "process", "respond": "respond", END: END}
    )
    graph.add_conditional_edges(
        "process", should_continue, {"respond": "respond", END: END}
    )
    graph.add_edge("respond", END)

    return graph.compile()


def get_graph_diagram() -> str:
    """
    获取 Mermaid 格式的图

    Returns:
        Mermaid 图代码
    """
    return """```mermaid
graph TD
    START([开始]) --> GREET[ greet_node<br/>问候节点]
    GREET -->|next_action| COND1{条件判断}
    COND1 -->|process| PROCESS[ process_node<br/>处理节点]
    COND1 -->|respond| RESPOND[ respond_node<br/>响应节点]
    COND1 -->|END| END1([结束])
    PROCESS --> COND2{条件判断}
    COND2 -->|respond| RESPOND
    RESPOND --> END1
```"""


if __name__ == "__main__":
    print("=== LangGraph 基础示例 ===\n")

    print("1. 图结构:")
    print(get_graph_diagram())

    print("\n2. 创建图...")
    app = build_graph()

    print("\n3. 执行图...")
    result = app.invoke(
        {
            "messages": [HumanMessage(content="你好")],
            "next_action": "",
            "session_id": "test-session-1",
        }
    )

    print("\n4. 执行结果:")
    for msg in result.get("messages", []):
        print(f"  - {msg.type}: {msg.content}")

    print("\n5. 图配置:")
    print(f"  - 节点: {list(app.nodes.keys())}")
