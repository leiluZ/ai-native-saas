"""记忆管理器测试"""
import pytest
from src.agents.memory_manager import MemoryManager


class TestMemoryManager:
    """记忆管理器测试类"""

    def test_init_default(self, mock_llm):
        """测试默认初始化"""
        manager = MemoryManager(llm=mock_llm)

        assert manager.summary == ""
        assert manager.recent_turns == []
        assert manager.total_turns == 0

    def test_add_turn(self, mock_llm):
        """测试添加对话轮次"""
        manager = MemoryManager(llm=mock_llm)

        manager.add_turn("user", "Hello")
        manager.add_turn("assistant", "Hi there!")

        assert manager.total_turns == 2
        assert manager.recent_turns[0]["role"] == "user"
        assert manager.recent_turns[0]["content"] == "Hello"
        assert manager.recent_turns[1]["role"] == "assistant"
        assert manager.recent_turns[1]["content"] == "Hi there!"

    def test_add_turn_with_max_limit(self, mock_llm):
        """测试最大轮次限制"""
        manager = MemoryManager(llm=mock_llm)
        manager._max_turns = 5  # 设置较小的限制

        for i in range(10):
            manager.add_turn("user", f"Message {i}")

        assert manager.total_turns == 5
        assert manager.recent_turns[0]["content"] == "Message 5"

    def test_get_memory_context(self, mock_llm):
        """测试获取记忆上下文"""
        manager = MemoryManager(llm=mock_llm)
        manager._summary = "Test summary"
        manager.add_turn("user", "Hello")

        context = manager.get_memory_context()

        assert context["summary"] == "Test summary"
        assert len(context["recent_turns"]) == 1
        assert context["recent_turns"][0]["content"] == "Hello"

    def test_clear(self, mock_llm):
        """测试清空记忆"""
        manager = MemoryManager(llm=mock_llm)
        manager._summary = "Test summary"
        manager.add_turn("user", "Hello")

        manager.clear()

        assert manager.summary == ""
        assert manager.recent_turns == []
        assert manager.total_turns == 0

    def test_estimate_tokens(self, mock_llm):
        """测试 token 估算"""
        manager = MemoryManager(llm=mock_llm)

        text = "Hello, world!"  # 13 个字符
        tokens = manager.estimate_tokens(text)

        assert tokens == 3  # 13 // 4 = 3

    @pytest.mark.asyncio
    async def test_generate_summary(self, mock_llm_for_summary):
        """测试生成摘要"""
        manager = MemoryManager(llm=mock_llm_for_summary)

        history = "User: Hello\nAssistant: Hi!\nUser: How are you?\nAssistant: I'm fine."
        summary = await manager.generate_summary(history)

        assert summary == "这是一个摘要"
        mock_llm_for_summary.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_and_compress_no_compression(self, mock_llm):
        """测试不需要压缩的情况"""
        manager = MemoryManager(llm=mock_llm)
        manager._summary_token_threshold = 1000

        manager.add_turn("user", "Short message")

        result = await manager.check_and_compress()

        assert result is False
        assert manager.summary == ""

    @pytest.mark.asyncio
    async def test_check_and_compress_with_compression(self, mock_llm_for_summary):
        """测试需要压缩的情况"""
        manager = MemoryManager(llm=mock_llm_for_summary)
        manager._summary_token_threshold = 10  # 设置很小的阈值

        # 添加足够多的内容触发压缩
        manager.add_turn("user", "This is a very long message that should trigger compression")
        manager.add_turn("assistant", "This is a very long response that should also trigger compression")

        result = await manager.check_and_compress()

        assert result is True
        assert manager.summary == "这是一个摘要"
        # 压缩后应该保留最近几轮
        assert len(manager.recent_turns) <= 5

    def test_to_dict(self, mock_llm):
        """测试序列化为字典"""
        manager = MemoryManager(llm=mock_llm)
        manager._summary = "Test summary"
        manager.add_turn("user", "Hello")

        data = manager.to_dict()

        assert data["summary"] == "Test summary"
        assert len(data["recent_turns"]) == 1
        assert data["total_turns"] == 1

    def test_from_dict(self, mock_llm):
        """测试从字典反序列化"""
        data = {
            "summary": "Restored summary",
            "recent_turns": [{"role": "user", "content": "Hello"}]
        }

        manager = MemoryManager.from_dict(data, llm=mock_llm)

        assert manager.summary == "Restored summary"
        assert manager.total_turns == 1
        assert manager.recent_turns[0]["content"] == "Hello"

    def test_from_dict_empty(self, mock_llm):
        """测试从空字典反序列化"""
        data = {}

        manager = MemoryManager.from_dict(data, llm=mock_llm)

        assert manager.summary == ""
        assert manager.total_turns == 0
