"""代理模块单元测试"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from gateway.proxy import (
    ProxyError,
    proxy_chat_completions,
    proxy_chat_completions_stream,
    proxy_list_models,
    proxy_embeddings,
    resolve_model,
    _build_backend_url,
    _build_headers,
)
from gateway.registry import ModelEntry, ModelStatus


class TestBuildBackendUrl:
    def test_basic_url(self):
        result = _build_backend_url("http://localhost:8000", "/v1/chat/completions")
        assert result == "http://localhost:8000/v1/chat/completions"

    def test_trailing_slash(self):
        result = _build_backend_url("http://localhost:8000/", "/v1/models")
        assert result == "http://localhost:8000/v1/models"

    def test_no_trailing_slash(self):
        result = _build_backend_url("http://localhost:8000", "/v1/embeddings")
        assert result == "http://localhost:8000/v1/embeddings"


class TestBuildHeaders:
    def test_with_api_key(self):
        headers = _build_headers("sk-test-key")
        assert headers["Authorization"] == "Bearer sk-test-key"
        assert headers["Content-Type"] == "application/json"

    def test_without_api_key(self):
        headers = _build_headers(None)
        assert "Authorization" not in headers
        assert headers["Content-Type"] == "application/json"

    def test_with_request_id(self):
        headers = _build_headers("sk-key", "req-123")
        assert headers["X-Request-ID"] == "req-123"


class TestResolveModel:
    def test_resolve_existing_model(self, populated_registry):
        entry, error = resolve_model("test-model", {"model": "test-model"})
        assert error is None
        assert entry is not None
        assert entry.name == "test-model"

    def test_resolve_from_body(self, populated_registry):
        entry, error = resolve_model(None, {"model": "test-model"})
        assert error is None
        assert entry is not None
        assert entry.name == "test-model"

    def test_resolve_missing_model(self, populated_registry):
        entry, error = resolve_model(None, {})
        assert entry is None
        assert error is not None
        assert "required" in error.lower()

    def test_resolve_unhealthy_fallback(self, populated_registry):
        entry, error = resolve_model("unhealthy-model", {"model": "unhealthy-model"})
        assert error is None
        assert entry is not None
        assert entry.name == "test-model"

    def test_resolve_nonexistent(self, populated_registry):
        entry, error = resolve_model("nonexistent-model", {"model": "nonexistent-model"})
        assert entry is not None
        assert error is None
        assert entry.name == "test-model"


class TestProxyChatCompletions:
    @pytest.mark.asyncio
    async def test_success(self, gateway_model_entry, chat_request_body, mock_chat_response):
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_http_response = MagicMock()
            mock_http_response.json.return_value = mock_chat_response
            mock_http_response.raise_for_status = MagicMock()
            mock_instance.post.return_value = mock_http_response

            result = await proxy_chat_completions(gateway_model_entry, chat_request_body, "req-123")
            assert result == mock_chat_response
            assert result["choices"][0]["message"]["content"] == "Hello! How can I help you today?"

    @pytest.mark.asyncio
    async def test_with_tool_calls(self, gateway_model_entry, chat_request_body_with_tools, mock_chat_response_with_tool_calls):
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_http_response = MagicMock()
            mock_http_response.json.return_value = mock_chat_response_with_tool_calls
            mock_http_response.raise_for_status = MagicMock()
            mock_instance.post.return_value = mock_http_response

            result = await proxy_chat_completions(gateway_model_entry, chat_request_body_with_tools, "req-456")
            assert result == mock_chat_response_with_tool_calls
            tool_calls = result["choices"][0]["message"]["tool_calls"]
            assert len(tool_calls) == 1
            assert tool_calls[0]["function"]["name"] == "get_weather"
            assert tool_calls[0]["function"]["arguments"] == '{"location": "Beijing"}'

    @pytest.mark.asyncio
    async def test_upstream_error(self, gateway_model_entry, chat_request_body):
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Server error", request=MagicMock(), response=mock_response
            )
            mock_instance.post.return_value = mock_response

            with pytest.raises(ProxyError) as exc_info:
                await proxy_chat_completions(gateway_model_entry, chat_request_body)
            assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_timeout_retry(self, gateway_model_entry, chat_request_body, mock_chat_response):
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.TimeoutException("Timeout")
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_chat_response
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.post = mock_post

            result = await proxy_chat_completions(gateway_model_entry, chat_request_body)
            assert result == mock_chat_response
            assert call_count == 3


class TestProxyChatCompletionsStream:
    @pytest.mark.asyncio
    async def test_stream_success(self, gateway_model_entry, chat_request_body_stream):
        stream_lines = [
            'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant","content":""},"finish_reason":null}]}',
            'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}',
            'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":" world"},"finish_reason":null}]}',
            'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}',
        ]

        class MockStreamResponse:
            status_code = 200

            async def aiter_lines(self):
                for line in stream_lines:
                    yield line

        class MockStreamContextManager:
            async def __aenter__(self):
                return MockStreamResponse()

            async def __aexit__(self, *args):
                pass

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.stream = MagicMock(return_value=MockStreamContextManager())

            lines = []
            async for line in proxy_chat_completions_stream(gateway_model_entry, chat_request_body_stream, "req-789"):
                lines.append(line)

            assert len(lines) == 4
            assert lines[0] == stream_lines[0]
            assert lines[-1] == stream_lines[-1]

    @pytest.mark.asyncio
    async def test_stream_with_tool_calls(self, gateway_model_entry):
        body = {
            "model": "test-model",
            "messages": [{"role": "user", "content": "Weather in Beijing?"}],
            "tools": [{"type": "function", "function": {"name": "get_weather", "parameters": {"type": "object", "properties": {"location": {"type": "string"}}}}}],
            "stream": True,
        }

        stream_lines = [
            'data: {"id":"chatcmpl-456","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant","content":null,"tool_calls":[{"index":0,"id":"call_abc","type":"function","function":{"name":"get_weather","arguments":""}}]},"finish_reason":null}]}',
            'data: {"id":"chatcmpl-456","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\\"location\\":\\"Beijing\\"}"}}]},"finish_reason":null}]}',
            'data: {"id":"chatcmpl-456","object":"chat.completion.chunk","choices":[{"index":0,"delta":{},"finish_reason":"tool_calls"}]}',
        ]

        class MockStreamResponse:
            status_code = 200

            async def aiter_lines(self):
                for line in stream_lines:
                    yield line

        class MockStreamContextManager:
            async def __aenter__(self):
                return MockStreamResponse()

            async def __aexit__(self, *args):
                pass

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.stream = MagicMock(return_value=MockStreamContextManager())

            lines = []
            async for line in proxy_chat_completions_stream(gateway_model_entry, body):
                lines.append(line)

            assert len(lines) == 3

    @pytest.mark.asyncio
    async def test_stream_upstream_error(self, gateway_model_entry, chat_request_body_stream):
        class MockErrorResponse:
            status_code = 500

            async def aiter_lines(self):
                yield '{"error": "Internal server error"}'

            async def aiter_text(self):
                yield '{"error": "Internal server error"}'

        class MockStreamContextManager:
            async def __aenter__(self):
                return MockErrorResponse()

            async def __aexit__(self, *args):
                pass

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.stream = MagicMock(return_value=MockStreamContextManager())

            with pytest.raises(ProxyError) as exc_info:
                async for _ in proxy_chat_completions_stream(gateway_model_entry, chat_request_body_stream):
                    pass
            assert exc_info.value.status_code == 500


class TestProxyListModels:
    @pytest.mark.asyncio
    async def test_success(self, gateway_model_entry, mock_models_response):
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_http_response = MagicMock()
            mock_http_response.json.return_value = mock_models_response
            mock_http_response.raise_for_status = MagicMock()
            mock_instance.get.return_value = mock_http_response

            result = await proxy_list_models(gateway_model_entry, "req-123")
            assert result == mock_models_response
            assert result["object"] == "list"
            assert len(result["data"]) == 1


class TestProxyEmbeddings:
    @pytest.mark.asyncio
    async def test_success(self, gateway_model_entry, embeddings_request_body, mock_embeddings_response):
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_http_response = MagicMock()
            mock_http_response.json.return_value = mock_embeddings_response
            mock_http_response.raise_for_status = MagicMock()
            mock_instance.post.return_value = mock_http_response

            result = await proxy_embeddings(gateway_model_entry, embeddings_request_body, "req-123")
            assert result == mock_embeddings_response
            assert len(result["data"]) == 1
            assert len(result["data"][0]["embedding"]) == 5

    @pytest.mark.asyncio
    async def test_upstream_error(self, gateway_model_entry, embeddings_request_body):
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_response = MagicMock()
            mock_response.status_code = 503
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Service unavailable", request=MagicMock(), response=mock_response
            )
            mock_instance.post.return_value = mock_response

            with pytest.raises(ProxyError) as exc_info:
                await proxy_embeddings(gateway_model_entry, embeddings_request_body)
            assert exc_info.value.status_code == 503


class TestProxyError:
    def test_proxy_error_creation(self):
        error = ProxyError(502, "Bad gateway", "upstream_error")
        assert error.status_code == 502
        assert error.message == "Bad gateway"
        assert error.error_type == "upstream_error"
        assert str(error) == "Bad gateway"
