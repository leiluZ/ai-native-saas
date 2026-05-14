"""网关主应用集成测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from gateway.main import app, register_default_models
from gateway.registry import ModelEntry, ModelStatus, model_registry


class TestGatewayApp:
    def test_app_creation(self):
        assert app.title == "OpenAI Compatible API Gateway"
        assert app.version == "1.0.0"

    def test_openapi_schema(self):
        client = TestClient(app)
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "/v1/chat/completions" in schema["paths"]
        assert "/v1/models" in schema["paths"]
        assert "/v1/embeddings" in schema["paths"]
        assert "/health" in schema["paths"]

    def test_docs_available(self):
        client = TestClient(app)
        response = client.get("/docs")
        assert response.status_code == 200

    def test_register_default_models(self):
        model_registry._models.clear()
        register_default_models()
        models = model_registry.list_models()
        assert len(models) == 3
        names = {m.name for m in models}
        assert "gpt-3.5-turbo" in names
        assert "vllm-local" in names
        assert "ollama-local" in names

    def test_cors_headers(self):
        client = TestClient(app)
        response = client.options(
            "/v1/models",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Authorization": "Bearer sk-gateway-default-key",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-credentials") != "true"

    def test_tracing_id_in_response(self):
        client = TestClient(app)
        response = client.get("/health")
        assert "X-Request-ID" in response.headers
        assert "X-Response-Time-Ms" in response.headers

    def test_rate_limit_headers(self):
        client = TestClient(app)
        response = client.get(
            "/v1/models",
            headers={"Authorization": "Bearer sk-gateway-default-key"},
        )
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Limit" in response.headers


class TestGatewayEndToEnd:
    def test_full_chat_flow(self):
        model_registry._models.clear()
        model_registry.register(
            ModelEntry(
                name="test-model",
                provider="vllm",
                endpoint="http://localhost:8000",
                status=ModelStatus.HEALTHY,
            )
        )

        mock_response = {
            "id": "chatcmpl-e2e",
            "object": "chat.completion",
            "created": 1677652288,
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "E2E test response",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }

        with patch("gateway.routes.chat.proxy_chat_completions") as mock_proxy:
            mock_proxy.return_value = mock_response

            client = TestClient(app)
            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "test-model",
                    "messages": [
                        {"role": "system", "content": "You are helpful."},
                        {"role": "user", "content": "Hi"},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 100,
                },
                headers={
                    "Authorization": "Bearer sk-gateway-default-key",
                    "X-Request-ID": "e2e-test-123",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["choices"][0]["message"]["content"] == "E2E test response"
            assert response.headers["X-Request-ID"] == "e2e-test-123"

    def test_full_embeddings_flow(self):
        model_registry._models.clear()
        model_registry.register(
            ModelEntry(
                name="embed-model",
                provider="vllm",
                endpoint="http://localhost:8000",
                status=ModelStatus.HEALTHY,
            )
        )

        mock_response = {
            "object": "list",
            "data": [
                {
                    "object": "embedding",
                    "index": 0,
                    "embedding": [0.01, 0.02, 0.03],
                }
            ],
            "model": "embed-model",
            "usage": {"prompt_tokens": 3, "total_tokens": 3},
        }

        with patch("gateway.routes.embeddings.proxy_embeddings") as mock_proxy:
            mock_proxy.return_value = mock_response

            client = TestClient(app)
            response = client.post(
                "/v1/embeddings",
                json={
                    "model": "embed-model",
                    "input": ["Hello", "World"],
                },
                headers={"Authorization": "Bearer sk-gateway-default-key"},
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["data"]) == 1

    def test_model_degradation_fallback(self):
        model_registry._models.clear()
        model_registry.register(
            ModelEntry(
                name="primary-model",
                provider="vllm",
                endpoint="http://localhost:8000",
                priority=1,
                status=ModelStatus.UNHEALTHY,
            )
        )
        model_registry.register(
            ModelEntry(
                name="fallback-model",
                provider="ollama",
                endpoint="http://localhost:11434",
                priority=2,
                status=ModelStatus.HEALTHY,
            )
        )

        mock_response = {
            "id": "chatcmpl-fallback",
            "object": "chat.completion",
            "created": 1677652288,
            "model": "fallback-model",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Fallback response",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        }

        with patch("gateway.routes.chat.proxy_chat_completions") as mock_proxy:
            mock_proxy.return_value = mock_response

            client = TestClient(app)
            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "primary-model",
                    "messages": [{"role": "user", "content": "Test"}],
                },
                headers={"Authorization": "Bearer sk-gateway-default-key"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["model"] == "fallback-model"
