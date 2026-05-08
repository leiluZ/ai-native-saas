"""Human-in-the-Loop 测试"""

from src.agents.langgraph_human_in_loop import (
    calculate_confidence,
    router_node,
    approval_node,
    reviewer_node,
)
from langchain_core.messages import HumanMessage, AIMessage


class TestCalculateConfidence:
    """置信度计算测试"""

    def test_high_confidence_weather(self):
        """测试天气结果的高置信度"""
        result = "当前温度: 25°C, 天气晴朗"
        confidence = calculate_confidence(result, "get_weather")
        assert confidence >= 0.7

    def test_high_confidence_time(self):
        """测试时间结果的高置信度"""
        result = "当前时间: 14:30:25, Asia/Shanghai"
        confidence = calculate_confidence(result, "get_current_time")
        assert confidence >= 0.7

    def test_high_confidence_calc(self):
        """测试计算结果的高置信度"""
        result = "计算结果: 42"
        confidence = calculate_confidence(result, "calculate")
        assert confidence >= 0.7

    def test_low_confidence_invalid(self):
        """测试无效结果的低置信度"""
        result = "xyzabc123"
        confidence = calculate_confidence(result, "get_weather")
        assert confidence < 0.7

    def test_low_confidence_error(self):
        """测试错误结果的低置信度"""
        result = "执行错误: location not found"
        confidence = calculate_confidence(result, "get_weather")
        assert confidence < 0.7


class TestRouterNode:
    """路由节点测试"""

    def test_router_weather(self):
        """测试天气路由"""
        state = {"messages": [HumanMessage(content="北京天气怎么样")]}
        result = router_node(state)
        assert result["route"] == "weather"
        assert result["tool_name"] == "get_weather"

    def test_router_time(self):
        """测试时间路由"""
        state = {"messages": [HumanMessage(content="现在几点了")]}
        result = router_node(state)
        assert result["route"] == "time"
        assert result["tool_name"] == "get_current_time"

    def test_router_calc(self):
        """测试计算路由"""
        state = {"messages": [HumanMessage(content="计算 2+2 等于多少")]}
        result = router_node(state)
        assert result["route"] == "calc"
        assert result["tool_name"] == "calculate"

    def test_router_general(self):
        """测试通用路由"""
        state = {"messages": [HumanMessage(content="你好")]}
        result = router_node(state)
        assert result["route"] == "general"

    def test_router_empty_messages(self):
        """测试空消息"""
        state = {"messages": []}
        result = router_node(state)
        assert result["route"] == "general"


class TestApprovalNode:
    """审批节点测试"""

    def test_approval_low_confidence(self):
        """测试低置信度触发中断"""
        state = {
            "confidence": 0.5,
            "messages": [AIMessage(content="result")],
            "original_result": "result",
            "pending_approval": False,
        }
        result = approval_node(state)
        assert result["pending_approval"] is True
        assert result["needs_approval"] is True
        assert result["approved"] is False

    def test_approval_high_confidence(self):
        """测试高置信度直接通过"""
        state = {
            "confidence": 0.9,
            "messages": [AIMessage(content="result")],
            "original_result": "result",
        }
        result = approval_node(state)
        assert result["pending_approval"] is False


class TestReviewerNode:
    """审查节点测试"""

    def test_reviewer_approved_with_modification(self):
        """测试批准并使用修改结果"""
        state = {
            "messages": [AIMessage(content="original")],
            "approved": True,
            "modified_result": "modified",
            "original_result": "original",
            "pending_approval": False,
        }
        result = reviewer_node(state)
        assert "[已人工审批]" in result["messages"][-1].content
        assert "modified" in result["messages"][-1].content

    def test_reviewer_not_approved(self):
        """测试未批准使用原始结果"""
        state = {
            "messages": [AIMessage(content="original")],
            "approved": False,
            "modified_result": "modified",
            "original_result": "original",
            "pending_approval": False,
        }
        result = reviewer_node(state)
        assert "original" in result["messages"][-1].content

    def test_reviewer_empty_messages(self):
        """测试空消息"""
        state = {"messages": []}
        result = reviewer_node(state)
        assert result["approved"] is False
