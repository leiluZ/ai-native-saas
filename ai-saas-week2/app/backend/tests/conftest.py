"""pytest 配置文件 - 定义共享 fixtures"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from langchain_core.language_models import BaseChatModel


@pytest.fixture
def mock_llm():
    """创建一个模拟的 LLM 实例"""
    mock = MagicMock(spec=BaseChatModel)
    mock.ainvoke = AsyncMock(return_value=MagicMock(content="测试响应"))
    return mock


@pytest.fixture
def mock_llm_with_tool_call():
    """创建一个模拟的 LLM 实例，返回工具调用"""
    mock = MagicMock(spec=BaseChatModel)
    mock.ainvoke = AsyncMock(return_value=MagicMock(content='{"name": "get_weather", "arguments": {"location": "Beijing"}}'))
    return mock


@pytest.fixture
def mock_llm_for_summary():
    """创建一个模拟的 LLM 实例，用于摘要生成"""
    mock = MagicMock(spec=BaseChatModel)
    mock.ainvoke = AsyncMock(return_value=MagicMock(content="这是一个摘要"))
    return mock
