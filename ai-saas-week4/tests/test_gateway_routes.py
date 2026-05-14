"""路由单元测试"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.main import app
from gateway.registry import ModelEntry, ModelStatus, model_registry


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer sk-gateway-default-key"}


class TestHealthRoute:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["gateway"] == "running"
        assert "models" in data
        assert "healthy_models" in data
        assert "total_models" in data

    def test_health_check_no_auth_required(self, client):
        response = client.get("/health")
        assert response.status_code == 200


class TestModelsRoute:
    def test_list_models(self, client, auth_headers):
        response = client.get("/v1/models", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "list"
        assert "data" in data

    def test_list_models_no_auth(self, client):
        response = client.get("/v1/models")
        assert response.status_code == 401

    def test_retrieve_model(self, client, auth_headers):
        model_registry.register(
            ModelEntry(
                name="my-model",
                provider="test",
                endpoint="http://localhost:8000",
                status=ModelStatus.HEALTHY,
            )
        )
        response = client.get("/v1/models/my-model", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "my-model"
        assert data["owned_by"] == "test"

    def test_retrieve_model_not_found(self, client, auth_headers):
        response = client.get("/v1/models/nonexistent-model", headers=auth_headers)
        assert response.status_code == 404


class TestChatCompletionsRoute:
    def test_chat_completions_success(self, client, auth_headers, mock_chat_response):
        model_registry._models.clear()
        model_registry.register(
            ModelEntry(
                name="test-model",
                provider="vllm",
                endpoint="http://localhost:8000",
                status=ModelStatus.HEALTHY,
            )
        )

        with patch("gateway.routes.chat.proxy_chat_completions") as mock_proxy:
            mock_proxy.return_value = mock_chat_response

            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "test-model",
                    "messages": [{"role": "user", "content": "Hello"}],
                },
                headers=auth_headers,
            )
            assert response.status_code == 200
            data = response.json()
            assert data["choices"][0]["message"]["content"] == "Hello! How can I help you today?"

    def test_chat_completions_with_tools(self, client, auth_headers, mock_chat_response_with_tool_calls):
        model_registry._models.clear()
        model_registry.register(
            ModelEntry(
                name="test-model",
                provider="vllm",
                endpoint="http://localhost:8000",
                status=ModelStatus.HEALTHY,
            )
        )

        with patch("gateway.routes.chat.proxy_chat_completions") as mock_proxy:
            mock_proxy.return_value = mock_chat_response_with_tool_calls

            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "test-model",
                    "messages": [{"role": "user", "content": "Weather in Beijing?"}],
                    "tools": [
                        {
                            "type": "function",
                            "function": {
                                "name": "get_weather",
                                "parameters": {
                                    "type": "object",
                                    "properties": {"location": {"type": "string"}},
                                    "required": ["location"],
                                },
                            },
                        }
                    ],
                },
                headers=auth_headers,
            )
            assert response.status_code == 200
            data = response.json()
            tool_calls = data["choices"][0]["message"]["tool_calls"]
            assert len(tool_calls) == 1
            assert tool_calls[0]["function"]["name"] == "get_weather"

    def test_chat_completions_stream(self, client, auth_headers):
        model_registry._models.clear()
        model_registry.register(
            ModelEntry(
                name="test-model",
                provider="vllm",
                endpoint="http://localhost:8000",
                status=ModelStatus.HEALTHY,
            )
        )

        async def mock_stream(entry, body, request_id):
            yield 'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant","content":""},"finish_reason":null}]}'
            yield 'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}'
            yield 'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}'

        with patch("gateway.routes.chat.proxy_chat_completions_stream", side_effect=mock_stream):
            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "test-model",
                    "messages": [{"role": "user", "content": "Hello"}],
                    "stream": True,
                },
                headers=auth_headers,
            )
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]
            content = response.text
            assert "data: [DONE]" in content
            assert "Hello" in content

    def test_chat_completions_no_model(self, client, auth_headers):
        model_registry._models.clear()
        response = client.post(
            "/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
            },
            headers=auth_headers,
        )
        assert response.status_code == 400

    def test_chat_completions_invalid_json(self, client, auth_headers):
        response = client.post(
            "/v1/chat/completions",
            content="not json",
            headers={**auth_headers, "Content-Type": "application/json"},
        )
        assert response.status_code == 400

    def test_chat_completions_no_auth(self, client):
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        assert response.status_code == 401


class TestEmbeddingsRoute:
    def test_embeddings_success(self, client, auth_headers, mock_embeddings_response):
        model_registry._models.clear()
        model_registry.register(
            ModelEntry(
                name="test-model",
                provider="vllm",
                endpoint="http://localhost:8000",
                status=ModelStatus.HEALTHY,
            )
        )

        with patch("gateway.routes.embeddings.proxy_embeddings") as mock_proxy:
            mock_proxy.return_value = mock_embeddings_response

            response = client.post(
                "/v1/embeddings",
                json={
                    "model": "test-model",
                    "input": "Hello world",
                },
                headers=auth_headers,
            )
            assert response.status_code == 200
            data = response.json()
            assert len(data["data"]) == 1
            assert len(data["data"][0]["embedding"]) == 5

    def test_embeddings_no_model(self, client, auth_headers):
        model_registry._models.clear()
        response = client.post(
            "/v1/embeddings",
            json={"input": "Hello"},
            headers=auth_headers,
        )
        assert response.status_code == 400

    def test_embeddings_no_auth(self, client):
        response = client.post(
            "/v1/embeddings",
            json={
                "model": "test-model",
                "input": "Hello",
            },
        )
        assert response.status_code == 401


class TestRootRoute:
    def test_root(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "OpenAI Compatible API Gateway"
        assert "docs" in data
