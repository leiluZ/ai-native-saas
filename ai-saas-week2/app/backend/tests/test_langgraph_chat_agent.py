"""
测试 LangGraph 状态机聊天代理

覆盖所有节点和边的测试用例：
- analyze_node: 解析用户输入
- tool_node: 调用工具
- response_node: 生成响应
- memory_node: 保存对话历史
- 条件边: should_call_tool
"""

import pytest
from langchain_core.messages import HumanMessage, AIMessage

from app.agents.langgraph_chat_agent import (
    AgentState,
    analyze_node,
    tool_node,
    response_node,
    memory_node,
    should_call_tool,
    build_langgraph_integration,
    run_langgraph,
)


class TestAnalyzeNode:
    """测试分析节点"""

    def test_analyze_weather_request(self):
        """测试分析天气请求"""
        state: AgentState = {
            "messages": [HumanMessage(content="北京天气怎么样")],
            "user_input": "北京天气怎么样",
            "needs_tool": False,
            "tool_name": "",
            "tool_args": {},
            "tool_result": "",
            "final_response": "",
            "conversation_history": [],
            "total_tokens": 0,
            "needs_summarization": False,
        }
        result = analyze_node(state)
        assert result["needs_tool"] == True
        assert result["tool_name"] == "get_weather"
        assert result["tool_args"]["location"] == "北京"

    def test_analyze_time_request(self):
        """测试分析时间请求"""
        state: AgentState = {
            "messages": [HumanMessage(content="现在几点了")],
            "user_input": "现在几点了",
            "needs_tool": False,
            "tool_name": "",
            "tool_args": {},
            "tool_result": "",
            "final_response": "",
            "conversation_history": [],
            "total_tokens": 0,
            "needs_summarization": False,
        }
        result = analyze_node(state)
        assert result["needs_tool"] == True
        assert result["tool_name"] == "get_current_time"

    def test_analyze_calc_request(self):
        """测试分析计算请求"""
        state: AgentState = {
            "messages": [HumanMessage(content="计算 2+2")],
            "user_input": "计算 2+2",
            "needs_tool": False,
            "tool_name": "",
            "tool_args": {},
            "tool_result": "",
            "final_response": "",
            "conversation_history": [],
            "total_tokens": 0,
            "needs_summarization": False,
        }
        result = analyze_node(state)
        assert result["needs_tool"] == True
        assert result["tool_name"] == "calculate"
        assert result["tool_args"]["expression"] == "2+2"

    def test_analyze_no_tool_needed(self):
        """测试不需要工具的请求"""
        state: AgentState = {
            "messages": [HumanMessage(content="你好")],
            "user_input": "你好",
            "needs_tool": False,
            "tool_name": "",
            "tool_args": {},
            "tool_result": "",
            "final_response": "",
            "conversation_history": [],
            "total_tokens": 0,
            "needs_summarization": False,
        }
        result = analyze_node(state)
        assert result["needs_tool"] == False
        assert result["tool_name"] == ""


class TestToolNode:
    """测试工具节点"""

    def test_tool_node_calculate(self):
        """测试计算工具调用"""
        state: AgentState = {
            "messages": [],
            "user_input": "计算 1+1",
            "needs_tool": True,
            "tool_name": "calculate",
            "tool_args": {"expression": "1+1"},
            "tool_result": "",
            "final_response": "",
            "conversation_history": [],
            "total_tokens": 0,
            "needs_summarization": False,
        }
        result = tool_node(state)
        assert "计算结果" in result["tool_result"]

    def test_tool_node_weather(self):
        """测试天气工具调用"""
        state: AgentState = {
            "messages": [],
            "user_input": "北京天气",
            "needs_tool": True,
            "tool_name": "get_weather",
            "tool_args": {"location": "Beijing"},
            "tool_result": "",
            "final_response": "",
            "conversation_history": [],
            "total_tokens": 0,
            "needs_summarization": False,
        }
        result = tool_node(state)
        assert result["tool_result"] != ""

    def test_tool_node_time(self):
        """测试时间工具调用"""
        state: AgentState = {
            "messages": [],
            "user_input": "现在时间",
            "needs_tool": True,
            "tool_name": "get_current_time",
            "tool_args": {"timezone": "Asia/Shanghai"},
            "tool_result": "",
            "final_response": "",
            "conversation_history": [],
            "total_tokens": 0,
            "needs_summarization": False,
        }
        result = tool_node(state)
        assert result["tool_result"] != ""

    def test_tool_node_invalid_tool(self):
        """测试调用未注册的工具"""
        state: AgentState = {
            "messages": [],
            "user_input": "测试",
            "needs_tool": True,
            "tool_name": "invalid_tool",
            "tool_args": {},
            "tool_result": "",
            "final_response": "",
            "conversation_history": [],
            "total_tokens": 0,
            "needs_summarization": False,
        }
        result = tool_node(state)
        assert "未注册" in result["tool_result"]


class TestResponseNode:
    """测试响应节点"""

    def test_response_with_tool_result(self):
        """测试使用工具结果生成响应"""
        state: AgentState = {
            "messages": [],
            "user_input": "计算 1+1",
            "needs_tool": True,
            "tool_name": "calculate",
            "tool_args": {},
            "tool_result": "计算结果: 2",
            "final_response": "",
            "conversation_history": [],
            "total_tokens": 0,
            "needs_summarization": False,
        }
        result = response_node(state)
        assert "根据查询结果" in result["final_response"]

    def test_response_without_tool(self):
        """测试直接响应用户"""
        state: AgentState = {
            "messages": [],
            "user_input": "你好",
            "needs_tool": False,
            "tool_name": "",
            "tool_args": {},
            "tool_result": "",
            "final_response": "",
            "conversation_history": [],
            "total_tokens": 0,
            "needs_summarization": False,
        }
        result = response_node(state)
        assert "收到了你的消息" in result["final_response"]


class TestMemoryNode:
    """测试记忆节点"""

    def test_memory_node_saves_history(self):
        """测试保存对话历史"""
        state: AgentState = {
            "messages": [],
            "user_input": "你好",
            "needs_tool": False,
            "tool_name": "",
            "tool_args": {},
            "tool_result": "",
            "final_response": "你好！",
            "conversation_history": [],
            "total_tokens": 0,
            "needs_summarization": False,
        }
        result = memory_node(state)
        assert len(result["conversation_history"]) == 2
        assert result["conversation_history"][0]["role"] == "user"
        assert result["conversation_history"][1]["role"] == "assistant"

    def test_memory_node_token_count(self):
        """测试 token 计数"""
        state: AgentState = {
            "messages": [],
            "user_input": "Hello",
            "needs_tool": False,
            "tool_name": "",
            "tool_args": {},
            "tool_result": "",
            "final_response": "Hi!",
            "conversation_history": [],
            "total_tokens": 0,
            "needs_summarization": False,
        }
        result = memory_node(state)
        assert result["total_tokens"] == len("Hello") + len("Hi!")

    def test_memory_node_needs_summarization(self):
        """测试需要摘要的情况"""
        state: AgentState = {
            "messages": [],
            "user_input": "a" * 5000,
            "needs_tool": False,
            "tool_name": "",
            "tool_args": {},
            "tool_result": "",
            "final_response": "a" * 5000,
            "conversation_history": [],
            "total_tokens": 0,
            "needs_summarization": False,
        }
        result = memory_node(state)
        assert result["needs_summarization"] == True


class TestConditionalEdges:
    """测试条件边"""

    def test_should_call_tool_needs_tool(self):
        """测试需要工具时返回 tool"""
        state: AgentState = {
            "needs_tool": True,
            "messages": [],
            "user_input": "",
            "tool_name": "",
            "tool_args": {},
            "tool_result": "",
            "final_response": "",
            "conversation_history": [],
            "total_tokens": 0,
            "needs_summarization": False,
        }
        result = should_call_tool(state)
        assert result == "tool"

    def test_should_call_tool_no_tool(self):
        """测试不需要工具时返回 response"""
        state: AgentState = {
            "needs_tool": False,
            "messages": [],
            "user_input": "",
            "tool_name": "",
            "tool_args": {},
            "tool_result": "",
            "final_response": "",
            "conversation_history": [],
            "total_tokens": 0,
            "needs_summarization": False,
        }
        result = should_call_tool(state)
        assert result == "response"


class TestGraphBuilding:
    """测试图构建"""

    def test_build_graph(self):
        """测试构建状态机"""
        graph = build_langgraph_integration()
        assert graph is not None
        assert hasattr(graph, "invoke")

    @pytest.mark.asyncio
    async def test_run_graph_with_tool(self):
        """测试运行状态机（需要工具）"""
        result = await run_langgraph("计算 1+1", "test-thread")
        assert "final_response" in result
        assert "conversation_history" in result
        assert "total_tokens" in result

    @pytest.mark.asyncio
    async def test_run_graph_without_tool(self):
        """测试运行状态机（不需要工具）"""
        result = await run_langgraph("你好", "test-thread-2")
        assert "final_response" in result
        assert "收到了你的消息" in result["final_response"]
