"""聊天相关模型"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


class ChatMessageRequest(BaseModel):
    user_id: str = Field(..., description="用户ID")
    message: str = Field(..., description="消息内容", max_length=4096)
    session_id: Optional[str] = Field(None, description="会话ID")


class ChatMessageResponse(BaseModel):
    message_id: str = Field(..., description="消息ID")
    user_id: str = Field(..., description="用户ID")
    content: str = Field(..., description="消息内容")
    role: str = Field(..., description="角色: user/assistant")
    session_id: str = Field(..., description="会话ID")
    created_at: datetime = Field(..., description="创建时间")


class ChatHistoryResponse(BaseModel):
    session_id: str = Field(..., description="会话ID")
    messages: List[ChatMessageResponse] = Field(..., description="消息列表")


class AgentRequest(BaseModel):
    """LangChain Agent 请求模型"""
    prompt: str = Field(..., description="用户输入的提示词", max_length=4096)
    session_id: Optional[str] = Field(None, description="会话ID")
    user_id: Optional[str] = Field("default_user", description="用户ID")


class AgentResponse(BaseModel):
    """LangChain Agent 响应模型"""
    prompt: str = Field(..., description="用户输入的提示词")
    response: str = Field(..., description="Agent 返回的响应")
    timestamp: datetime = Field(..., description="响应时间")
