"""
Chat Agent - 主入口模块（向后兼容）

此模块保留原有接口，内部使用拆分后的子模块实现。
"""

from typing import Optional
from .llm_client import get_llm
from .tool_registry import get_weather, get_current_time, calculate, tool_registry
from .memory_manager import MemoryManager
from .agent_router import AgentRouter


tools_map = {
    "get_weather": get_weather,
    "get_current_time": get_current_time,
    "calculate": calculate,
}


async def run_agent(prompt: str, memory_context: Optional[dict] = None) -> str:
    """
    运行代理（保留原有接口）

    Args:
        prompt: 用户输入
        memory_context: 记忆上下文（可选）

    Returns:
        str: 代理响应
    """
    router = AgentRouter()
    return await router.run(prompt, memory_context)


async def generate_summary(history_text: str) -> str:
    """
    生成对话历史摘要（保留原有接口）

    Args:
        history_text: 对话历史文本

    Returns:
        str: 生成的摘要
    """
    memory_manager = MemoryManager()
    return await memory_manager.generate_summary(history_text)


# 导出模块
__all__ = [
    "get_llm",
    "get_weather",
    "get_current_time",
    "calculate",
    "tools_map",
    "tool_registry",
    "MemoryManager",
    "AgentRouter",
    "run_agent",
    "generate_summary",
]
