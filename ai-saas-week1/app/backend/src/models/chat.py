"""聊天消息模型"""
from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from . import Base


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=False)
    session_id = Column(String, nullable=False, index=True)
    content = Column(Text, nullable=False)
    role = Column(String, nullable=False)  # user or assistant
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<ChatMessage(id={self.id}, user_id={self.user_id}, role={self.role})>"
