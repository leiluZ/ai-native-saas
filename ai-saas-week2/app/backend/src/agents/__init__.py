"""
Agents Module - 代理模块入口

整合组件与 LangGraph：
- llm_client: LLM 调用
- tool_registry: 工具注册和调用
- memory_manager: 对话记忆管理
- langgraph_chat_agent: LangGraph 状态机实现
"""

# 核心组件
from .llm_client import get_llm
from .tool_registry import tool_registry
from .memory_manager import MemoryManager
from .chat_agent import run_agent

# LangGraph 集成
from .langgraph_chat_agent import (
    AgentState,
    analyze_node,
    tool_node,
    response_node,
    memory_node,
    build_langgraph_integration,
    get_langgraph_graph,
    run_langgraph,
)

__all__ = [
    # 核心组件
    "get_llm",
    "tool_registry",
    "MemoryManager",
    "run_agent",
    # LangGraph
    "AgentState",
    "analyze_node",
    "tool_node",
    "response_node",
    "memory_node",
    "build_langgraph_integration",
    "get_langgraph_graph",
    "run_langgraph",
]
