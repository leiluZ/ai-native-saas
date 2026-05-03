"""会话记忆管理器"""

from typing import List, Optional, Tuple, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
import redis.asyncio as redis
from datetime import datetime
from uuid import uuid4
from app.models.chat import ChatMessage, ChatSession

# Token 估算常量（基于经验值）
TOKEN_THRESHOLD = 8000
REDIS_TTL = 30 * 60  # 30分钟


class SessionMemoryManager:
    """会话记忆管理器"""

    def __init__(self, db: AsyncSession, redis_client: redis.Redis):
        self.db = db
        self.redis_client = redis_client

    async def _count_tokens(self, text: str) -> int:
        """估算文本的 token 数量（简化版）"""
        # 粗略估算：1 token ≈ 4 字符
        return len(text) // 4

    async def _get_session_summary(self, session_id: str) -> Optional[str]:
        """获取会话摘要"""
        result = await self.db.execute(
            select(ChatSession.summary).where(ChatSession.session_id == session_id)
        )
        row = result.first()
        return row[0] if row else None

    async def _update_session_summary(self, session_id: str, summary: str):
        """更新会话摘要"""
        await self.db.execute(
            update(ChatSession)
            .where(ChatSession.session_id == session_id)
            .values(summary=summary, updated_at=datetime.now())
        )
        await self.db.commit()

    async def _update_session_tokens(self, session_id: str, tokens_added: int):
        """更新会话总 token 数"""
        await self.db.execute(
            update(ChatSession)
            .where(ChatSession.session_id == session_id)
            .values(total_tokens=ChatSession.total_tokens + tokens_added)
        )
        await self.db.commit()

    async def _get_total_tokens(self, session_id: str) -> int:
        """获取会话总 token 数"""
        result = await self.db.execute(
            select(ChatSession.total_tokens).where(ChatSession.session_id == session_id)
        )
        row = result.first()
        return row[0] if row else 0

    async def _get_recent_turns(
        self, session_id: str, max_turns: int = 5
    ) -> List[dict]:
        """获取最近的对话回合"""
        result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(max_turns * 2)  # 每个回合包含用户和助手消息
        )
        messages = result.scalars().all()
        # 按时间排序（升序）
        messages = sorted(messages, key=lambda m: m.created_at)
        return [{"role": m.role, "content": m.content} for m in messages]

    async def _get_full_history(self, session_id: str) -> str:
        """获取完整对话历史文本"""
        result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
        )
        messages = result.scalars().all()
        history_lines = []
        for msg in messages:
            history_lines.append(f"{msg.role}: {msg.content}")
        return "\n".join(history_lines)

    async def _create_session(
        self, user_id: str, session_id: Optional[str] = None
    ) -> str:
        """创建新会话"""
        if not session_id:
            session_id = str(uuid4())
        new_session = ChatSession(
            user_id=user_id, session_id=session_id, summary=None, total_tokens=0
        )
        self.db.add(new_session)
        await self.db.commit()
        return session_id

    async def _ensure_session_exists(self, user_id: str, session_id: str):
        """确保会话存在"""
        result = await self.db.execute(
            select(ChatSession).where(ChatSession.session_id == session_id)
        )
        if not result.scalar_one_or_none():
            await self._create_session(user_id, session_id)

    async def add_message(
        self, user_id: str, session_id: str, content: str, role: str
    ) -> Tuple[str, bool]:
        """
        添加消息到会话

        Returns:
            (session_id, should_summarize): 会话ID和是否需要触发摘要压缩
        """
        # 确保会话存在
        await self._ensure_session_exists(user_id, session_id)

        # 创建消息
        new_message = ChatMessage(
            user_id=user_id,
            session_id=session_id,
            content=content,
            role=role,
            created_at=datetime.now(),
        )
        self.db.add(new_message)
        await self.db.commit()

        # 更新 Redis TTL
        await self.redis_client.hset(
            f"session:{session_id}",
            mapping={"user_id": user_id, "last_active": datetime.now().isoformat()},
        )
        await self.redis_client.expire(f"session:{session_id}", REDIS_TTL)

        # 计算新增 token 并更新总数
        tokens_added = await self._count_tokens(content)
        await self._update_session_tokens(session_id, tokens_added)

        # 检查是否需要摘要压缩
        total_tokens = await self._get_total_tokens(session_id)
        should_summarize = total_tokens > TOKEN_THRESHOLD

        return session_id, should_summarize

    async def get_memory_context(self, session_id: str) -> Dict[str, any]:
        """
        获取会话记忆上下文，用于注入到 Agent system prompt

        Returns:
            {
                "summary": str | None,
                "recent_turns": list,
                "total_tokens": int
            }
        """
        summary = await self._get_session_summary(session_id)
        recent_turns = await self._get_recent_turns(session_id)
        total_tokens = await self._get_total_tokens(session_id)

        return {
            "summary": summary,
            "recent_turns": recent_turns,
            "total_tokens": total_tokens,
        }

    async def get_history(self, session_id: str) -> List[dict]:
        """获取完整会话历史"""
        result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
        )
        messages = result.scalars().all()
        return [
            {
                "message_id": str(m.id),
                "user_id": m.user_id,
                "content": m.content,
                "role": m.role,
                "session_id": m.session_id,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ]

    async def summarize_history(self, session_id: str) -> str:
        """生成对话历史摘要"""
        full_history = await self._get_full_history(session_id)
        summary_prompt = f"""将以下对话历史压缩为 3 句话摘要，保留用户意图与关键事实：

{full_history}

摘要："""
        return summary_prompt

    async def update_summary(self, session_id: str, summary: str):
        """更新会话摘要"""
        await self._update_session_summary(session_id, summary)

    async def delete_session(self, session_id: str):
        """删除会话"""
        # 删除消息
        await self.db.execute(
            ChatMessage.__table__.delete().where(ChatMessage.session_id == session_id)
        )
        # 删除会话记录
        await self.db.execute(
            ChatSession.__table__.delete().where(ChatSession.session_id == session_id)
        )
        # 删除 Redis 缓存
        await self.redis_client.delete(f"session:{session_id}")
        await self.db.commit()
