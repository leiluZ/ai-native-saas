"""网关端到端集成测试

覆盖 CORS、限流、鉴权、完整业务流程、并发、错误传播等场景。
使用 TestClient 模拟真实 HTTP 请求，无需启动 Docker。
"""

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from gateway.main import app
from gateway.registry import ModelEntry, ModelStatus, model_registry


@pytest.fixture(autouse=True)
def reset_registry(clean_registry):
    clean_registry.register(
        ModelEntry(
            name="test-model",
            provider="vllm",
            endpoint="http://localhost:8000",
            api_key="sk-backend-key",
            priority=1,
            status=ModelStatus.HEALTHY,
        )
    )
    clean_registry.register(
        ModelEntry(
            name="fallback-model",
            provider="ollama",
            endpoint="http://localhost:11434",
            priority=2,
            status=ModelStatus.HEALTHY,
        )
    )
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth():
    return {"Authorization": "Bearer sk-gateway-default-key"}


@pytest.fixture
def chat_body():
    return {
        "model": "test-model",
        "messages": [{"role": "user", "content": "Hello"}],
        "temperature": 0.7,
        "max_tokens": 100,
    }


@pytest.fixture
def stream_body():
    return {
        "model": "test-model",
        "messages": [{"role": "user", "content": "Tell me a story"}],
        "stream": True,
    }


@pytest.fixture
def tools_body():
    return {
        "model": "test-model",
        "messages": [{"role": "user", "content": "Weather in Beijing?"}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get current weather",
                    "parameters": {
                        "type": "object",
                        "properties": {"location": {"type": "string"}},
                        "required": ["location"],
                    },
                },
            }
        ],
    }


@pytest.fixture
def embeddings_body():
    return {"model": "test-model", "input": ["Hello world", "How are you?"]}


@pytest.fixture
def mock_upstream_chat():
    return {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1677652288,
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hello! How can I help you today?"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
    }


@pytest.fixture
def mock_upstream_tool_calls():
    return {
        "id": "chatcmpl-456",
        "object": "chat.completion",
        "created": 1677652289,
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_abc123",
                            "type": "function",
                            "function": {
                                "name": "get_weather",
                                "arguments": '{"location": "Beijing"}',
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 20, "completion_tokens": 15, "total_tokens": 35},
    }


@pytest.fixture
def mock_upstream_embeddings():
    return {
        "object": "list",
        "data": [
            {"object": "embedding", "index": 0, "embedding": [0.01, 0.02, 0.03, 0.04, 0.05]},
            {"object": "embedding", "index": 1, "embedding": [0.06, 0.07, 0.08, 0.09, 0.10]},
        ],
        "model": "test-model",
        "usage": {"prompt_tokens": 6, "total_tokens": 6},
    }


@pytest.fixture
def mock_upstream_models():
    return {
        "object": "list",
        "data": [
            {
                "id": "test-model",
                "object": "model",
                "created": 1677652288,
                "owned_by": "vllm",
            }
        ],
    }


class TestCORS:
    def test_preflight_allowed_origin(self, client):
        response = client.options(
            "/v1/chat/completions",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Authorization, Content-Type",
                "Authorization": "Bearer sk-gateway-default-key",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "*"
        assert "POST" in response.headers["access-control-allow-methods"]

    def test_preflight_any_origin(self, client):
        origins = [
            "http://localhost:3000",
            "https://example.com",
            "http://192.168.1.1:8080",
            "null",
        ]
        for origin in origins:
            response = client.options(
                "/v1/models",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "GET",
                    "Authorization": "Bearer sk-gateway-default-key",
                },
            )
            assert response.status_code == 200
            assert response.headers["access-control-allow-origin"] == "*"

    def test_preflight_allowed_methods(self, client):
        methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
        for method in methods:
            response = client.options(
                "/v1/models",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": method,
                    "Authorization": "Bearer sk-gateway-default-key",
                },
            )
            assert response.status_code == 200

    def test_preflight_allowed_headers(self, client):
        response = client.options(
            "/v1/chat/completions",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Authorization, Content-Type, X-Request-ID, X-Custom-Header",
                "Authorization": "Bearer sk-gateway-default-key",
            },
        )
        assert response.status_code == 200

    def test_preflight_credentials_not_allowed_with_wildcard(self, client):
        response = client.options(
            "/v1/chat/completions",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Authorization": "Bearer sk-gateway-default-key",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-credentials") != "true"

    def test_cors_headers_on_normal_response(self, client, auth):
        response = client.get(
            "/v1/models",
            headers={**auth, "Origin": "http://localhost:3000"},
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "*"

    def test_cors_headers_on_error_response(self, client):
        response = client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "Hi"}]},
            headers={
                "Origin": "http://localhost:3000",
                "Authorization": "Bearer sk-gateway-default-key",
            },
        )
        assert response.status_code == 400
        assert response.headers["access-control-allow-origin"] == "*"


class TestRateLimiting:
    def test_rate_limit_headers_present(self, client, auth):
        response = client.get("/v1/models", headers=auth)
        assert response.status_code == 200
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Limit" in response.headers
        assert response.headers["X-RateLimit-Limit"] == "60"

    def test_rate_limit_decrements(self, client, auth):
        response1 = client.get("/v1/models", headers=auth)
        remaining1 = int(response1.headers["X-RateLimit-Remaining"])

        response2 = client.get("/v1/models", headers=auth)
        remaining2 = int(response2.headers["X-RateLimit-Remaining"])

        assert remaining2 == remaining1 - 1

    def test_rate_limit_exhaustion(self, client, auth):
        from gateway.middleware import rate_limiter

        limiter = rate_limiter
        limiter._clients.clear()

        for i in range(60):
            response = client.get("/v1/models", headers=auth)
            assert response.status_code == 200, f"Request {i} should succeed"

        response = client.get("/v1/models", headers=auth)
        assert response.status_code == 429
        data = response.json()
        assert data["error"]["type"] == "rate_limit_error"
        assert "Rate limit exceeded" in data["error"]["message"]

    def test_rate_limit_different_ips_independent(self, client):
        from gateway.middleware import rate_limiter

        limiter = rate_limiter
        limiter._clients.clear()

        for _ in range(5):
            response = client.get(
                "/v1/models",
                headers={
                    "Authorization": "Bearer sk-gateway-default-key",
                    "X-Forwarded-For": "10.0.0.1",
                },
            )
            assert response.status_code == 200

        response = client.get(
            "/v1/models",
            headers={
                "Authorization": "Bearer sk-gateway-default-key",
                "X-Forwarded-For": "10.0.0.2",
            },
        )
        assert response.status_code == 200

    def test_rate_limit_excluded_paths(self, client):
        from gateway.middleware import rate_limiter

        limiter = rate_limiter
        limiter._clients.clear()

        for _ in range(100):
            response = client.get("/health")
            assert response.status_code == 200

    def test_rate_limit_429_response_format(self, client, auth):
        from gateway.middleware import rate_limiter

        limiter = rate_limiter
        limiter._clients.clear()

        for _ in range(60):
            client.get("/v1/models", headers=auth)

        response = client.get("/v1/models", headers=auth)
        assert response.status_code == 429
        data = response.json()
        assert "error" in data
        assert data["error"]["type"] == "rate_limit_error"
        assert data["error"]["code"] == 429


class TestAuthentication:
    def test_valid_api_key_accepted(self, client, auth):
        response = client.get("/v1/models", headers=auth)
        assert response.status_code == 200

    def test_missing_auth_header(self, client):
        response = client.get("/v1/models")
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["type"] == "authentication_error"

    def test_invalid_api_key(self, client):
        response = client.get(
            "/v1/models",
            headers={"Authorization": "Bearer sk-wrong-key"},
        )
        assert response.status_code == 403
        data = response.json()
        assert data["error"]["type"] == "authentication_error"

    def test_malformed_auth_header(self, client):
        malformed = [
            "Bearer",
            "Basic abc123",
            "Bearer ",
            "",
            "bearer sk-gateway-default-key",
        ]
        for header in malformed:
            response = client.get(
                "/v1/models",
                headers={"Authorization": header} if header else {},
            )
            assert response.status_code in (401, 403), f"Header '{header}' should fail"

    def test_health_endpoint_no_auth(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_docs_no_auth(self, client):
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_no_auth(self, client):
        response = client.get("/openapi.json")
        assert response.status_code == 200

    def test_root_no_auth(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_auth_required_for_chat(self, client):
        response = client.post(
            "/v1/chat/completions",
            json={"model": "test-model", "messages": [{"role": "user", "content": "Hi"}]},
        )
        assert response.status_code == 401

    def test_auth_required_for_embeddings(self, client):
        response = client.post(
            "/v1/embeddings",
            json={"model": "test-model", "input": "Hello"},
        )
        assert response.status_code == 401


class TestChatCompletionsE2E:
    def test_non_streaming_chat(self, client, auth, chat_body, mock_upstream_chat):
        with patch("gateway.routes.chat.proxy_chat_completions") as mock_proxy:
            mock_proxy.return_value = mock_upstream_chat

            response = client.post("/v1/chat/completions", json=chat_body, headers=auth)

            assert response.status_code == 200
            data = response.json()
            assert data["object"] == "chat.completion"
            assert data["model"] == "test-model"
            assert len(data["choices"]) == 1
            assert data["choices"][0]["message"]["role"] == "assistant"
            assert data["choices"][0]["message"]["content"] == "Hello! How can I help you today?"
            assert data["choices"][0]["finish_reason"] == "stop"
            assert "usage" in data

    def test_streaming_chat(self, client, auth, stream_body):
        async def mock_stream(entry, body, request_id):
            yield 'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant","content":""},"finish_reason":null}]}'
            yield 'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}'
            yield 'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":" world"},"finish_reason":null}]}'
            yield 'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}'

        with patch("gateway.routes.chat.proxy_chat_completions_stream", side_effect=mock_stream):
            response = client.post("/v1/chat/completions", json=stream_body, headers=auth)

            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]
            assert "no-cache" in response.headers["cache-control"]
            assert "keep-alive" in response.headers["connection"]
            assert "no" in response.headers["x-accel-buffering"]

            content = response.text
            assert "data: [DONE]" in content
            assert "Hello" in content
            assert "world" in content

    def test_function_calling(self, client, auth, tools_body, mock_upstream_tool_calls):
        with patch("gateway.routes.chat.proxy_chat_completions") as mock_proxy:
            mock_proxy.return_value = mock_upstream_tool_calls

            response = client.post("/v1/chat/completions", json=tools_body, headers=auth)

            assert response.status_code == 200
            data = response.json()
            assert data["choices"][0]["finish_reason"] == "tool_calls"
            tool_calls = data["choices"][0]["message"]["tool_calls"]
            assert len(tool_calls) == 1
            assert tool_calls[0]["type"] == "function"
            assert tool_calls[0]["function"]["name"] == "get_weather"
            assert "Beijing" in tool_calls[0]["function"]["arguments"]

    def test_function_calling_streaming(self, client, auth, tools_body):
        async def mock_stream(entry, body, request_id):
            yield 'data: {"id":"chatcmpl-456","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant","content":null,"tool_calls":[{"index":0,"id":"call_abc","type":"function","function":{"name":"get_weather","arguments":""}}]},"finish_reason":null}]}'
            yield 'data: {"id":"chatcmpl-456","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\\"location\\":\\"Beijing\\"}"}}]},"finish_reason":null}]}'
            yield 'data: {"id":"chatcmpl-456","object":"chat.completion.chunk","choices":[{"index":0,"delta":{},"finish_reason":"tool_calls"}]}'

        with patch("gateway.routes.chat.proxy_chat_completions_stream", side_effect=mock_stream):
            response = client.post(
                "/v1/chat/completions",
                json={**tools_body, "stream": True},
                headers=auth,
            )

            assert response.status_code == 200
            content = response.text
            assert "get_weather" in content
            assert "Beijing" in content
            assert "data: [DONE]" in content

    def test_chat_with_system_message(self, client, auth, mock_upstream_chat):
        with patch("gateway.routes.chat.proxy_chat_completions") as mock_proxy:
            mock_proxy.return_value = mock_upstream_chat

            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "test-model",
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": "Hello"},
                    ],
                },
                headers=auth,
            )
            assert response.status_code == 200

    def test_chat_with_all_parameters(self, client, auth, mock_upstream_chat):
        with patch("gateway.routes.chat.proxy_chat_completions") as mock_proxy:
            mock_proxy.return_value = mock_upstream_chat

            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "test-model",
                    "messages": [{"role": "user", "content": "Hello"}],
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "n": 1,
                    "max_tokens": 500,
                    "presence_penalty": 0.1,
                    "frequency_penalty": 0.1,
                    "user": "user-123",
                },
                headers=auth,
            )
            assert response.status_code == 200

    def test_chat_missing_model(self, client, auth):
        response = client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "Hello"}]},
            headers=auth,
        )
        assert response.status_code == 400
        data = response.json()
        assert data["error"]["type"] == "invalid_request_error"

    def test_chat_invalid_json_body(self, client, auth):
        response = client.post(
            "/v1/chat/completions",
            content="not valid json {{{",
            headers={**auth, "Content-Type": "application/json"},
        )
        assert response.status_code == 400

    def test_chat_upstream_error_propagation(self, client, auth, chat_body):
        from gateway.proxy import ProxyError

        with patch("gateway.routes.chat.proxy_chat_completions") as mock_proxy:
            mock_proxy.side_effect = ProxyError(502, "Upstream unavailable", "upstream_error")

            response = client.post("/v1/chat/completions", json=chat_body, headers=auth)

            assert response.status_code == 502
            data = response.json()
            assert data["error"]["type"] == "upstream_error"
            assert "Upstream unavailable" in data["error"]["message"]

    def test_chat_upstream_error_in_stream(self, client, auth, stream_body):
        from gateway.proxy import ProxyError

        async def mock_stream_error(entry, body, request_id):
            raise ProxyError(503, "Service unavailable", "upstream_error")
            yield

        with patch("gateway.routes.chat.proxy_chat_completions_stream", side_effect=mock_stream_error):
            response = client.post("/v1/chat/completions", json=stream_body, headers=auth)

            assert response.status_code == 200
            content = response.text
            assert "Service unavailable" in content
            assert "data: [DONE]" in content

    def test_chat_tracing_id_propagation(self, client, auth, chat_body, mock_upstream_chat):
        with patch("gateway.routes.chat.proxy_chat_completions") as mock_proxy:
            mock_proxy.return_value = mock_upstream_chat

            response = client.post(
                "/v1/chat/completions",
                json=chat_body,
                headers={**auth, "X-Request-ID": "trace-12345"},
            )

            assert response.status_code == 200
            assert response.headers["X-Request-ID"] == "trace-12345"

    def test_chat_response_time_header(self, client, auth, chat_body, mock_upstream_chat):
        with patch("gateway.routes.chat.proxy_chat_completions") as mock_proxy:
            mock_proxy.return_value = mock_upstream_chat

            response = client.post("/v1/chat/completions", json=chat_body, headers=auth)

            assert response.status_code == 200
            assert "X-Response-Time-Ms" in response.headers
            response_time = float(response.headers["X-Response-Time-Ms"])
            assert response_time >= 0


class TestEmbeddingsE2E:
    def test_embeddings_single_input(self, client, auth, mock_upstream_embeddings):
        with patch("gateway.routes.embeddings.proxy_embeddings") as mock_proxy:
            mock_proxy.return_value = mock_upstream_embeddings

            response = client.post(
                "/v1/embeddings",
                json={"model": "test-model", "input": "Hello world"},
                headers=auth,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["object"] == "list"
            assert len(data["data"]) == 2
            assert len(data["data"][0]["embedding"]) == 5

    def test_embeddings_multiple_inputs(self, client, auth, mock_upstream_embeddings):
        with patch("gateway.routes.embeddings.proxy_embeddings") as mock_proxy:
            mock_proxy.return_value = mock_upstream_embeddings

            response = client.post(
                "/v1/embeddings",
                json={
                    "model": "test-model",
                    "input": ["Hello world", "How are you?"],
                },
                headers=auth,
            )
            assert response.status_code == 200
            data = response.json()
            assert data["object"] == "list"
            assert len(data["data"]) == 2

    def test_embeddings_missing_model(self, client, auth):
        response = client.post(
            "/v1/embeddings",
            json={"input": "Hello"},
            headers=auth,
        )
        assert response.status_code == 400

    def test_embeddings_upstream_error(self, client, auth):
        from gateway.proxy import ProxyError

        with patch("gateway.routes.embeddings.proxy_embeddings") as mock_proxy:
            mock_proxy.side_effect = ProxyError(500, "Embedding service error", "upstream_error")

            response = client.post(
                "/v1/embeddings",
                json={"model": "test-model", "input": "Hello"},
                headers=auth,
            )

            assert response.status_code == 500
            data = response.json()
            assert data["error"]["type"] == "upstream_error"


class TestModelsE2E:
    def test_list_models(self, client, auth):
        response = client.get("/v1/models", headers=auth)
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "list"
        assert len(data["data"]) >= 2

    def test_retrieve_model(self, client, auth):
        response = client.get("/v1/models/test-model", headers=auth)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test-model"
        assert data["owned_by"] == "vllm"
        assert data["object"] == "model"

    def test_retrieve_model_not_found(self, client, auth):
        response = client.get("/v1/models/nonexistent", headers=auth)
        assert response.status_code == 404

    def test_models_response_format(self, client, auth):
        response = client.get("/v1/models", headers=auth)
        data = response.json()
        for model in data["data"]:
            assert "id" in model
            assert "object" in model
            assert "created" in model
            assert "owned_by" in model


class TestHealthCheckE2E:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["gateway"] == "running"
        assert "models" in data
        assert "healthy_models" in data
        assert "total_models" in data
        assert data["total_models"] >= 2

    def test_health_check_has_tracing(self, client):
        response = client.get("/health")
        assert "X-Request-ID" in response.headers
        assert "X-Response-Time-Ms" in response.headers

    def test_health_check_reflects_model_status(self, client):
        model_registry._models.clear()
        model_registry.register(
            ModelEntry(
                name="healthy-1",
                provider="vllm",
                endpoint="http://localhost:8000",
                status=ModelStatus.HEALTHY,
            )
        )
        model_registry.register(
            ModelEntry(
                name="degraded-1",
                provider="ollama",
                endpoint="http://localhost:11434",
                status=ModelStatus.DEGRADED,
            )
        )
        model_registry.register(
            ModelEntry(
                name="unhealthy-1",
                provider="vllm",
                endpoint="http://localhost:8001",
                status=ModelStatus.UNHEALTHY,
            )
        )

        response = client.get("/health")
        data = response.json()
        assert data["total_models"] == 3
        assert data["healthy_models"] == 2


class TestModelDegradationE2E:
    def test_fallback_when_preferred_unhealthy(self, client, auth, mock_upstream_chat):
        model_registry._models.clear()
        model_registry.register(
            ModelEntry(
                name="primary",
                provider="vllm",
                endpoint="http://localhost:8000",
                priority=1,
                status=ModelStatus.UNHEALTHY,
            )
        )
        model_registry.register(
            ModelEntry(
                name="secondary",
                provider="ollama",
                endpoint="http://localhost:11434",
                priority=2,
                status=ModelStatus.HEALTHY,
            )
        )

        with patch("gateway.routes.chat.proxy_chat_completions") as mock_proxy:
            mock_proxy.return_value = mock_upstream_chat

            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "primary",
                    "messages": [{"role": "user", "content": "Hello"}],
                },
                headers=auth,
            )

            assert response.status_code == 200

    def test_no_healthy_model_available(self, client, auth):
        model_registry._models.clear()
        model_registry.register(
            ModelEntry(
                name="down-1",
                provider="vllm",
                endpoint="http://localhost:8000",
                status=ModelStatus.UNHEALTHY,
            )
        )
        model_registry.register(
            ModelEntry(
                name="down-2",
                provider="ollama",
                endpoint="http://localhost:11434",
                status=ModelStatus.UNHEALTHY,
            )
        )

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "down-1",
                "messages": [{"role": "user", "content": "Hello"}],
            },
            headers=auth,
        )

        assert response.status_code == 400
        data = response.json()
        assert "No healthy model found" in data["error"]["message"]


class TestTracingAndHeaders:
    def test_request_id_generated_when_missing(self, client, auth):
        response = client.get("/v1/models", headers=auth)
        request_id = response.headers["X-Request-ID"]
        assert len(request_id) > 0
        assert "-" in request_id

    def test_request_id_preserved(self, client, auth):
        response = client.get(
            "/v1/models",
            headers={**auth, "X-Request-ID": "my-custom-id"},
        )
        assert response.headers["X-Request-ID"] == "my-custom-id"

    def test_response_time_on_all_endpoints(self, client, auth):
        endpoints = [
            ("GET", "/health", None, {}),
            ("GET", "/v1/models", None, auth),
            ("GET", "/", None, {}),
        ]
        for method, path, body, headers in endpoints:
            if method == "GET":
                response = client.get(path, headers=headers)
            else:
                response = client.post(path, json=body, headers=headers)
            assert "X-Response-Time-Ms" in response.headers, f"Missing on {method} {path}"


class TestConcurrentRequests:
    def test_concurrent_chat_requests(self, client, auth, chat_body, mock_upstream_chat):
        import concurrent.futures

        with patch("gateway.routes.chat.proxy_chat_completions") as mock_proxy:
            mock_proxy.return_value = mock_upstream_chat

            def make_request():
                c = TestClient(app)
                return c.post("/v1/chat/completions", json=chat_body, headers=auth)

            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(make_request) for _ in range(10)]
                results = [f.result() for f in futures]

            for response in results:
                assert response.status_code == 200
                data = response.json()
                assert data["choices"][0]["message"]["content"] is not None

    def test_concurrent_mixed_endpoints(self, client, auth, mock_upstream_chat, mock_upstream_embeddings):
        import concurrent.futures

        with patch("gateway.routes.chat.proxy_chat_completions") as mock_chat:
            mock_chat.return_value = mock_upstream_chat
            with patch("gateway.routes.embeddings.proxy_embeddings") as mock_emb:
                mock_emb.return_value = mock_upstream_embeddings

                def chat_request():
                    c = TestClient(app)
                    return c.post(
                        "/v1/chat/completions",
                        json={"model": "test-model", "messages": [{"role": "user", "content": "Hi"}]},
                        headers=auth,
                    )

                def models_request():
                    c = TestClient(app)
                    return c.get("/v1/models", headers=auth)

                def embeddings_request():
                    c = TestClient(app)
                    return c.post(
                        "/v1/embeddings",
                        json={"model": "test-model", "input": "Hello"},
                        headers=auth,
                    )

                with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
                    futures = []
                    futures.extend([executor.submit(chat_request) for _ in range(3)])
                    futures.extend([executor.submit(models_request) for _ in range(3)])
                    futures.extend([executor.submit(embeddings_request) for _ in range(3)])
                    results = [f.result() for f in futures]

                for response in results:
                    assert response.status_code == 200


class TestErrorResponses:
    def test_404_not_found(self, client, auth):
        response = client.get("/v1/nonexistent-endpoint", headers=auth)
        assert response.status_code == 404

    def test_405_method_not_allowed(self, client, auth):
        response = client.put("/v1/models", headers=auth)
        assert response.status_code == 405

    def test_error_response_format(self, client, auth):
        from gateway.proxy import ProxyError

        with patch("gateway.routes.chat.proxy_chat_completions") as mock_proxy:
            mock_proxy.side_effect = ProxyError(502, "Bad gateway", "upstream_error")

            response = client.post(
                "/v1/chat/completions",
                json={"model": "test-model", "messages": [{"role": "user", "content": "Hi"}]},
                headers=auth,
            )

            data = response.json()
            assert "error" in data
            assert "message" in data["error"]
            assert "type" in data["error"]
            assert "code" in data["error"]


class TestRootEndpoint:
    def test_root_returns_info(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "OpenAI Compatible API Gateway"
        assert data["version"] == "1.0.0"
        assert data["docs"] == "/docs"

    def test_root_has_tracing(self, client):
        response = client.get("/")
        assert "X-Request-ID" in response.headers
        assert "X-Response-Time-Ms" in response.headers
