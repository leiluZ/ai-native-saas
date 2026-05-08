"""代理路由模块 - 核心代理逻辑"""

from typing import Optional, Dict, Any, Tuple
from langchain_core.language_models import BaseChatModel
from .llm_client import get_llm
from .tool_registry import tool_registry, ToolRegistry
from .memory_manager import MemoryManager
import re
import json


class AgentRouter:
    """代理路由器 - 负责解析工具调用和路由请求"""

    def __init__(
        self,
        llm: Optional[BaseChatModel] = None,
        tool_reg: Optional[ToolRegistry] = None,
        memory_manager: Optional[MemoryManager] = None,
    ):
        """
        初始化代理路由器

        Args:
            llm: LLM 实例（可选）
            tool_reg: 工具注册表（可选）
            memory_manager: 记忆管理器（可选）
        """
        self._llm = llm or get_llm()
        self._tool_registry = tool_reg or tool_registry
        self._memory_manager = memory_manager or MemoryManager(llm=self._llm)

    @property
    def memory_manager(self) -> MemoryManager:
        """获取记忆管理器"""
        return self._memory_manager

    def parse_tool_call(
        self, text: str
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """
        从文本中解析工具调用

        Args:
            text: 包含工具调用的文本

        Returns:
            Tuple[Optional[str], Optional[Dict[str, Any]]]: (工具名称, 参数)，如果未找到返回 (None, None)
        """
        # 首先尝试 JSON 格式解析
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and "name" in parsed:
                tool_name = parsed["name"]
                args = parsed.get("arguments", {})
                if tool_name and self._tool_registry.has_tool(tool_name):
                    return tool_name, args
        except (json.JSONDecodeError, ValueError):
            pass

        # 尝试正则表达式解析
        patterns = [
            r"(\w+)\s*\(\s*([^)]+)\s*\)",
            r'"(\w+)"\s*:\s*\{[^}]*"arguments"[^}]*\{[^}]*"([^"]+)"[^}]*\}[^}]*\}',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                tool_name = match.group(1) if match.lastindex >= 1 else None
                args_str = match.group(2) if match.lastindex >= 2 else "{}"

                if tool_name and self._tool_registry.has_tool(tool_name):
                    args = self._parse_tool_args(tool_name, args_str)
                    if args:
                        return tool_name, args

        return None, None

    def _parse_tool_args(
        self, tool_name: str, args_str: str
    ) -> Optional[Dict[str, Any]]:
        """
        解析工具参数

        Args:
            tool_name: 工具名称
            args_str: 参数字符串

        Returns:
            Optional[Dict[str, Any]]: 解析后的参数字典
        """
        args: Dict[str, Any] = {}

        if tool_name == "get_weather":
            loc_match = re.search(
                r'["\']?location["\']?\s*:\s*["\']([^"\']+)["\']', args_str
            )
            if loc_match:
                args = {"location": loc_match.group(1)}
            else:
                simple_match = re.search(r'["\']([^"\']+)["\']', args_str)
                if simple_match:
                    args = {"location": simple_match.group(1)}

        elif tool_name == "get_current_time":
            tz_match = re.search(
                r'["\']?timezone["\']?\s*:\s*["\']([^"\']+)["\']', args_str
            )
            if tz_match:
                args = {"timezone": tz_match.group(1)}

        elif tool_name == "calculate":
            expr_match = re.search(
                r'["\']?expression["\']?\s*:\s*["\']([^"\']+)["\']', args_str
            )
            if expr_match:
                args = {"expression": expr_match.group(1)}
            else:
                simple_match = re.search(r'["\']([^"\']+)["\']', args_str)
                if simple_match:
                    args = {"expression": simple_match.group(1)}

        return args if args else None

    def _build_system_prompt(
        self, memory_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        构建系统提示词

        Args:
            memory_context: 记忆上下文（可选）

        Returns:
            str: 完整的系统提示词
        """
        # 构建记忆部分
        memory_section = ""
        if memory_context:
            summary = memory_context.get("summary", "")
            recent_turns = memory_context.get("recent_turns", [])

            if summary:
                memory_section += f"对话摘要：\n{summary}\n\n"

            if recent_turns:
                recent_turns_str = "\n".join(
                    [f"{turn['role']}: {turn['content']}" for turn in recent_turns]
                )
                memory_section += f"最近对话：\n{recent_turns_str}\n\n"

        # 构建工具列表
        tools_list = "\n".join(
            [
                f"- {tool_name}: {self._get_tool_description(tool_name)}"
                for tool_name in self._tool_registry.list_tools()
            ]
        )

        return f"""你是一个乐于助人的助手。当用户询问天气、时间或计算问题时，你必须调用相应的工具。

{memory_section}可用工具：
{tools_list}

指令：
1. 如果用户询问天气，调用 get_weather(location)
2. 如果用户询问时间，调用 get_current_time(timezone)
3. 如果用户询问数学问题，调用 calculate(expression)
4. 获取工具结果后，提供最终答案

重要：必须实际调用工具，不要只是描述你会做什么。"""

    def _get_tool_description(self, tool_name: str) -> str:
        """
        获取工具描述

        Args:
            tool_name: 工具名称

        Returns:
            str: 工具描述
        """
        descriptions = {
            "get_weather": "获取城市天气",
            "get_current_time": "获取当前时间（默认：Asia/Shanghai）",
            "calculate": "执行数学计算",
        }
        return descriptions.get(tool_name, tool_name)

    async def run(
        self, prompt: str, memory_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        运行代理

        Args:
            prompt: 用户输入
            memory_context: 记忆上下文（可选）

        Returns:
            str: 代理响应
        """
        try:
            # 构建完整提示词
            system_prompt = self._build_system_prompt(memory_context)
            full_prompt = f"{system_prompt}\n\n用户：{prompt}"

            # 调用 LLM
            response = await self._llm.ainvoke(full_prompt)
            response_text = (
                response.content if hasattr(response, "content") else str(response)
            )

            # 解析工具调用
            tool_name, args = self.parse_tool_call(response_text)

            # 如果有工具调用，执行工具
            if tool_name:
                try:
                    tool_result = self._tool_registry.invoke_tool(tool_name, args or {})
                    return tool_result
                except Exception as e:
                    return f"工具执行错误: {str(e)}"

            return response_text

        except Exception as e:
            return f"抱歉，执行过程中遇到错误: {str(e)}。请稍后重试。"

    async def run_with_memory(self, prompt: str) -> str:
        """
        运行代理并使用记忆

        Args:
            prompt: 用户输入

        Returns:
            str: 代理响应
        """
        # 获取当前记忆上下文
        memory_context = self._memory_manager.get_memory_context()

        # 运行代理
        response = await self.run(prompt, memory_context)

        # 添加对话到记忆
        self._memory_manager.add_turn("user", prompt)
        self._memory_manager.add_turn("assistant", response)

        # 检查是否需要压缩
        await self._memory_manager.check_and_compress()

        return response
