"""代理路由模块测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.agents.agent_router import AgentRouter


class TestAgentRouter:
    """代理路由器测试类"""

    def test_init_default(self, mock_llm):
        """测试默认初始化"""
        router = AgentRouter(llm=mock_llm)

        assert router._llm == mock_llm
        assert router._tool_registry is not None
        assert router._memory_manager is not None

    def test_parse_tool_call_basic(self, mock_llm):
        """测试解析基本工具调用"""
        router = AgentRouter(llm=mock_llm)

        text = 'get_weather("Beijing")'
        tool_name, args = router.parse_tool_call(text)

        assert tool_name == "get_weather"
        assert args == {"location": "Beijing"}

    def test_parse_tool_call_with_colon(self, mock_llm):
        """测试解析带冒号的工具调用"""
        router = AgentRouter(llm=mock_llm)

        text = 'get_weather(location="Shanghai")'
        tool_name, args = router.parse_tool_call(text)

        assert tool_name == "get_weather"
        assert args == {"location": "Shanghai"}

    def test_parse_tool_call_json_format(self, mock_llm):
        """测试解析 JSON 格式的工具调用"""
        router = AgentRouter(llm=mock_llm)

        text = '{"name": "get_current_time", "arguments": {"timezone": "America/New_York"}}'
        tool_name, args = router.parse_tool_call(text)

        assert tool_name == "get_current_time"
        assert args == {"timezone": "America/New_York"}

    def test_parse_tool_call_no_match(self, mock_llm):
        """测试无法解析的情况"""
        router = AgentRouter(llm=mock_llm)

        text = "Just a normal response without tool call"
        tool_name, args = router.parse_tool_call(text)

        assert tool_name is None
        assert args is None

    def test_parse_tool_call_invalid_tool(self, mock_llm):
        """测试解析不存在的工具"""
        router = AgentRouter(llm=mock_llm)

        text = 'nonexistent_tool("test")'
        tool_name, args = router.parse_tool_call(text)

        assert tool_name is None
        assert args is None

    def test_parse_tool_call_calculate(self, mock_llm):
        """测试解析计算工具调用"""
        router = AgentRouter(llm=mock_llm)

        text = 'calculate("2 + 3")'
        tool_name, args = router.parse_tool_call(text)

        assert tool_name == "calculate"
        assert args == {"expression": "2 + 3"}

    def test_build_system_prompt_without_memory(self, mock_llm):
        """测试构建不带记忆的系统提示词"""
        router = AgentRouter(llm=mock_llm)

        prompt = router._build_system_prompt()

        assert "乐于助人的助手" in prompt
        assert "get_weather" in prompt
        assert "get_current_time" in prompt
        assert "calculate" in prompt

    def test_build_system_prompt_with_memory(self, mock_llm):
        """测试构建带记忆的系统提示词"""
        router = AgentRouter(llm=mock_llm)

        memory_context = {
            "summary": "用户询问了天气",
            "recent_turns": [{"role": "user", "content": "北京天气"}]
        }

        prompt = router._build_system_prompt(memory_context)

        assert "对话摘要" in prompt
        assert "用户询问了天气" in prompt
        assert "最近对话" in prompt
        assert "北京天气" in prompt

    @pytest.mark.asyncio
    async def test_run_basic_response(self, mock_llm):
        """测试基本响应"""
        router = AgentRouter(llm=mock_llm)

        response = await router.run("Hello")

        assert response == "测试响应"
        mock_llm.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_with_tool_call(self, mock_llm_with_tool_call):
        """测试工具调用"""
        router = AgentRouter(llm=mock_llm_with_tool_call)

        response = await router.run("What's the weather in Beijing?")

        # 应该执行工具并返回结果
        assert "晴" in response or "Beijing" in response or "天气" in response

    @pytest.mark.asyncio
    async def test_run_error_handling(self):
        """测试错误处理"""
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM error"))

        router = AgentRouter(llm=mock_llm)

        response = await router.run("Hello")

        assert "遇到错误" in response
        assert "LLM error" in response

    @pytest.mark.asyncio
    async def test_run_with_memory_context(self, mock_llm):
        """测试带记忆上下文的运行"""
        router = AgentRouter(llm=mock_llm)

        memory_context = {
            "summary": "之前的对话摘要",
            "recent_turns": [{"role": "user", "content": "Hi"}]
        }

        response = await router.run("Hello", memory_context)

        assert response == "测试响应"
        # 验证 LLM 被调用
        mock_llm.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_with_memory(self, mock_llm):
        """测试使用记忆管理器的运行"""
        router = AgentRouter(llm=mock_llm)

        response = await router.run_with_memory("Hello")

        assert response == "测试响应"
        # 验证记忆被更新
        assert router._memory_manager.total_turns == 2  # user + assistant
        assert router._memory_manager.recent_turns[0]["content"] == "Hello"
        assert router._memory_manager.recent_turns[1]["content"] == "测试响应"

    def test_get_tool_description(self, mock_llm):
        """测试获取工具描述"""
        router = AgentRouter(llm=mock_llm)

        desc = router._get_tool_description("get_weather")

        assert desc == "获取城市天气"

    def test_get_tool_description_unknown(self, mock_llm):
        """测试获取未知工具描述"""
        router = AgentRouter(llm=mock_llm)

        desc = router._get_tool_description("unknown_tool")

        assert desc == "unknown_tool"
