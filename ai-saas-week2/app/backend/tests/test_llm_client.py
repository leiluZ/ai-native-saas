"""LLM 客户端测试"""
import pytest
import os
from unittest.mock import MagicMock, patch
from app.agents.llm_client import LLMClient, get_llm


class TestLLMClient:
    """LLM 客户端测试类"""

    def test_get_llm_with_ollama_model(self, monkeypatch):
        """测试使用 Ollama 模型"""
        monkeypatch.setenv("OLLAMA_MODEL", "mistral")
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")

        with patch('langchain_ollama.ChatOllama') as mock_chat_ollama:
            mock_instance = MagicMock()
            mock_chat_ollama.return_value = mock_instance

            result = LLMClient.get_llm()

            mock_chat_ollama.assert_called_once_with(
                model="mistral",
                temperature=0.7,
                base_url="http://localhost:11434"
            )
            assert result == mock_instance

    def test_get_llm_with_openai(self, monkeypatch):
        """测试使用 OpenAI"""
        monkeypatch.delenv("OLLAMA_MODEL", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setenv("OPENAI_MODEL", "gpt-4")
        monkeypatch.setenv("OPENAI_BASE_URL", "https://api.example.com/v1")

        with patch('langchain_openai.ChatOpenAI') as mock_chat_openai:
            mock_instance = MagicMock()
            mock_chat_openai.return_value = mock_instance

            result = LLMClient.get_llm()

            mock_chat_openai.assert_called_once_with(
                model="gpt-4",
                api_key="sk-test-key",
                temperature=0.7,
                base_url="https://api.example.com/v1"
            )
            assert result == mock_instance

    def test_get_llm_without_api_key(self, monkeypatch):
        """测试未配置任何 API key 的情况"""
        monkeypatch.delenv("OLLAMA_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        with pytest.raises(ValueError) as exc_info:
            LLMClient.get_llm()

        assert "必须设置 OLLAMA_MODEL 或 OPENAI_API_KEY 环境变量" in str(exc_info.value)

    def test_get_llm_default_openai_model(self, monkeypatch):
        """测试 OpenAI 默认模型"""
        monkeypatch.delenv("OLLAMA_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")

        with patch('langchain_openai.ChatOpenAI') as mock_chat_openai:
            mock_chat_openai.return_value = MagicMock()

            LLMClient.get_llm()

            mock_chat_openai.assert_called_once_with(
                model="gpt-3.5-turbo",
                api_key="sk-test-key",
                temperature=0.7,
                base_url=None
            )

    def test_get_llm_import_error_ollama(self, monkeypatch):
        """测试 Ollama 导入失败"""
        monkeypatch.setenv("OLLAMA_MODEL", "mistral")

        with patch.dict('sys.modules', {'langchain_ollama': None}):
            with pytest.raises(ImportError) as exc_info:
                LLMClient.get_llm()

            assert "langchain-ollama 未安装" in str(exc_info.value)

    def test_get_llm_import_error_openai(self, monkeypatch):
        """测试 OpenAI 导入失败"""
        monkeypatch.delenv("OLLAMA_MODEL", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")

        with patch.dict('sys.modules', {'langchain_openai': None}):
            with pytest.raises(ImportError) as exc_info:
                LLMClient.get_llm()

            assert "langchain-openai 未安装" in str(exc_info.value)

    def test_get_llm_convenience_function(self, monkeypatch):
        """测试便捷函数 get_llm"""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")

        with patch('app.agents.llm_client.LLMClient.get_llm') as mock_get_llm:
            mock_instance = MagicMock()
            mock_get_llm.return_value = mock_instance

            result = get_llm()

            mock_get_llm.assert_called_once()
            assert result == mock_instance
