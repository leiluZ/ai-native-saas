"""Human-in-the-Loop 测试"""

from src.agents.langgraph_human_in_loop import (
    HumanInLoopManager,
    calculate_confidence,
    router_node,
    approval_node,
    reviewer_node,
)
from langchain_core.messages import HumanMessage, AIMessage


class TestHumanInLoopManager:
    """HumanInLoopManager 测试"""

    def test_add_pending_approval(self):
        """测试添加待审批任务"""
        manager = HumanInLoopManager()
        manager.add_pending_approval(
            thread_id="test-123",
            messages=[HumanMessage(content="test")],
            original_result="result",
            confidence=0.5,
        )

        info = manager.get_pending_approval("test-123")
        assert info is not None
        assert info["original_result"] == "result"
        assert info["confidence"] == 0.5
        assert info["approved"] is False

    def test_approve_true(self):
        """测试批准操作"""
        manager = HumanInLoopManager()
        manager.add_pending_approval(
            thread_id="test-123",
            messages=[HumanMessage(content="test")],
            original_result="result",
            confidence=0.5,
        )

        result = manager.approve(thread_id="test-123", approved=True)
        assert result is True
        assert manager.is_approved("test-123") is True

    def test_approve_false_with_modified(self):
        """测试拒绝操作并提供修改结果"""
        manager = HumanInLoopManager()
        manager.add_pending_approval(
            thread_id="test-123",
            messages=[HumanMessage(content="test")],
            original_result="result",
            confidence=0.5,
        )

        result = manager.approve(
            thread_id="test-123",
            approved=False,
            modified_result="modified_result",
        )
        assert result is True

        info = manager.get_approval_info("test-123")
        assert info["approved"] is False
        assert info["modified_result"] == "modified_result"

    def test_approve_nonexistent(self):
        """测试审批不存在的任务"""
        manager = HumanInLoopManager()
        result = manager.approve(thread_id="nonexistent", approved=True)
        assert result is False

    def test_remove_pending(self):
        """测试移除待审批任务"""
        manager = HumanInLoopManager()
        manager.add_pending_approval(
            thread_id="test-123",
            messages=[],
            original_result="result",
            confidence=0.5,
        )

        assert manager.remove_pending("test-123") is True
        assert manager.get_pending_approval("test-123") is None


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
        }
        result = approval_node(state)
        assert result.goto == "reviewer"
        assert result.resume["approved"] is False
        assert result.resume["needs_approval"] is True

    def test_approval_high_confidence(self):
        """测试高置信度直接通过"""
        state = {
            "confidence": 0.9,
            "messages": [AIMessage(content="result")],
            "original_result": "result",
        }
        result = approval_node(state)
        assert result.goto == "reviewer"
        assert result.resume is None


class TestReviewerNode:
    """审查节点测试"""

    def test_reviewer_approved_with_modification(self):
        """测试批准并使用修改结果"""
        state = {
            "messages": [AIMessage(content="original")],
            "approved": True,
            "modified_result": "modified",
            "original_result": "original",
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
        }
        result = reviewer_node(state)
        assert result["messages"][-1].content == "original"

    def test_reviewer_empty_messages(self):
        """测试空消息"""
        state = {"messages": []}
        result = reviewer_node(state)
        assert result["approved"] is False
