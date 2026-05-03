"""记忆管理器模块 - 管理会话记忆和摘要"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from .llm_client import get_llm
from langchain_core.language_models import BaseChatModel


class MemoryManager:
    """会话记忆管理器"""

    def __init__(self, llm: Optional[BaseChatModel] = None):
        """
        初始化记忆管理器

        Args:
            llm: LLM 实例，用于生成摘要（可选）
        """
        self._llm = llm or get_llm()
        self._summary: str = ""
        self._recent_turns: List[Dict[str, str]] = []
        self._max_turns: int = 20
        self._summary_token_threshold: int = 8000

    @property
    def summary(self) -> str:
        """获取当前会话摘要"""
        return self._summary

    @property
    def recent_turns(self) -> List[Dict[str, str]]:
        """获取最近对话历史"""
        return self._recent_turns.copy()

    @property
    def total_turns(self) -> int:
        """获取总对话轮数"""
        return len(self._recent_turns)

    def add_turn(self, role: str, content: str) -> None:
        """
        添加对话轮次

        Args:
            role: 角色（user 或 assistant）
            content: 内容
        """
        self._recent_turns.append(
            {"role": role, "content": content, "timestamp": datetime.now().isoformat()}
        )

        # 保持最近的对话轮次
        if len(self._recent_turns) > self._max_turns:
            self._recent_turns = self._recent_turns[-self._max_turns :]

    def get_memory_context(self) -> Dict[str, Any]:
        """
        获取记忆上下文，用于注入到提示词中

        Returns:
            Dict[str, Any]: 包含摘要和最近对话的上下文
        """
        return {"summary": self._summary, "recent_turns": self._recent_turns}

    def clear(self) -> None:
        """清空所有记忆"""
        self._summary = ""
        self._recent_turns = []

    def estimate_tokens(self, text: str) -> int:
        """
        估算文本的 token 数量（粗略估算）

        Args:
            text: 要估算的文本

        Returns:
            int: 估算的 token 数量
        """
        # 粗略估算：1 token ≈ 4 个字符
        return len(text) // 4

    async def generate_summary(self, history_text: str) -> str:
        """
        生成对话历史摘要

        Args:
            history_text: 对话历史文本

        Returns:
            str: 生成的摘要
        """
        summary_prompt = f"""将以下对话历史压缩为 3 句话摘要，保留用户意图与关键事实：

{history_text}

摘要："""

        response = await self._llm.ainvoke(summary_prompt)
        return response.content if hasattr(response, "content") else str(response)

    async def check_and_compress(self) -> bool:
        """
        检查是否需要压缩，并在必要时执行压缩

        Returns:
            bool: 如果执行了压缩返回 True，否则返回 False
        """
        # 计算当前所有历史的 token 数
        all_history = "\n".join(
            [f"{turn['role']}: {turn['content']}" for turn in self._recent_turns]
        )
        total_tokens = self.estimate_tokens(all_history)

        if total_tokens > self._summary_token_threshold:
            await self.compress_memory()
            return True

        return False

    async def compress_memory(self) -> None:
        """
        压缩记忆：生成摘要并保留最近几轮对话
        """
        # 生成摘要
        history_text = "\n".join(
            [f"{turn['role']}: {turn['content']}" for turn in self._recent_turns]
        )
        self._summary = await self.generate_summary(history_text)

        # 保留最近的几轮对话（保留上下文）
        self._recent_turns = self._recent_turns[-5:]

    def to_dict(self) -> Dict[str, Any]:
        """
        序列化为字典

        Returns:
            Dict[str, Any]: 包含摘要和最近对话的字典
        """
        return {
            "summary": self._summary,
            "recent_turns": self._recent_turns,
            "total_turns": self.total_turns,
        }

    @classmethod
    def from_dict(
        cls, data: Dict[str, Any], llm: Optional[BaseChatModel] = None
    ) -> "MemoryManager":
        """
        从字典反序列化

        Args:
            data: 包含摘要和最近对话的字典
            llm: LLM 实例（可选）

        Returns:
            MemoryManager: 恢复的记忆管理器实例
        """
        manager = cls(llm=llm)
        manager._summary = data.get("summary", "")
        manager._recent_turns = data.get("recent_turns", [])
        return manager
