"""
Agents Module - 代理模块入口

整合组件与 LangGraph：
- llm_client: LLM 调用
- tool_registry: 工具注册和调用
- memory_manager: 对话记忆管理
- langgraph_chat_agent: LangGraph 状态机实现
- langgraph_rag_agent: RAG 增强的 LangGraph Agent
- rag_tool: RAG 搜索工具
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

# RAG Agent
from .langgraph_rag_agent import (
    RAGAgentState,
    build_rag_agent_graph,
    get_rag_agent_graph,
    run_rag_agent,
    run_rag_agent_stream,
    get_rag_session_info,
    get_execution_trace as get_rag_execution_trace,
    clear_execution_trace as clear_rag_execution_trace,
)

# RAG Tool
from .rag_tool import (
    rag_search_tool,
    RagSearchInput,
    RagSearchResult,
    RagSearchResponse,
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
    # RAG Agent
    "RAGAgentState",
    "build_rag_agent_graph",
    "get_rag_agent_graph",
    "run_rag_agent",
    "run_rag_agent_stream",
    "get_rag_session_info",
    "get_rag_execution_trace",
    "clear_rag_execution_trace",
    # RAG Tool
    "rag_search_tool",
    "RagSearchInput",
    "RagSearchResult",
    "RagSearchResponse",
]
