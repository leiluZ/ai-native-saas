"""中间件单元测试"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from gateway.middleware import (
    RateLimiter,
    TracingMiddleware,
    ApiKeyMiddleware,
    RateLimitMiddleware,
    rate_limiter,
)


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_allow_within_limit(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        for _ in range(5):
            assert await limiter.is_allowed("127.0.0.1") is True

    @pytest.mark.asyncio
    async def test_block_exceeding_limit(self):
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            assert await limiter.is_allowed("127.0.0.1") is True
        assert await limiter.is_allowed("127.0.0.1") is False

    @pytest.mark.asyncio
    async def test_different_ips_independent(self):
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        assert await limiter.is_allowed("192.168.1.1") is True
        assert await limiter.is_allowed("192.168.1.1") is True
        assert await limiter.is_allowed("192.168.1.1") is False
        assert await limiter.is_allowed("192.168.1.2") is True

    @pytest.mark.asyncio
    async def test_get_remaining(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        for i in range(3):
            await limiter.is_allowed("127.0.0.1")
        remaining = await limiter.get_remaining("127.0.0.1")
        assert remaining == 2

    @pytest.mark.asyncio
    async def test_get_remaining_new_ip(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        remaining = await limiter.get_remaining("new-ip")
        assert remaining == 5

    @pytest.mark.asyncio
    async def test_window_expiry(self):
        limiter = RateLimiter(max_requests=3, window_seconds=0.01)
        for _ in range(3):
            await limiter.is_allowed("127.0.0.1")
        assert await limiter.is_allowed("127.0.0.1") is False
        await asyncio.sleep(0.02)
        assert await limiter.is_allowed("127.0.0.1") is True


class TestTracingMiddleware:
    def test_adds_request_id_header(self):
        app = FastAPI()
        app.add_middleware(TracingMiddleware)

        @app.get("/test")
        async def test_endpoint(request: Request):
            return {"request_id": request.state.request_id}

        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        assert "X-Response-Time-Ms" in response.headers

    def test_preserves_existing_request_id(self):
        app = FastAPI()
        app.add_middleware(TracingMiddleware)

        @app.get("/test")
        async def test_endpoint(request: Request):
            return {"request_id": request.state.request_id}

        client = TestClient(app)
        response = client.get("/test", headers={"X-Request-ID": "custom-id-123"})
        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == "custom-id-123"

    def test_generates_new_request_id(self):
        app = FastAPI()
        app.add_middleware(TracingMiddleware)

        @app.get("/test")
        async def test_endpoint(request: Request):
            return {"request_id": request.state.request_id}

        client = TestClient(app)
        response = client.get("/test")
        request_id = response.headers["X-Request-ID"]
        assert len(request_id) > 0
        assert "-" in request_id


class TestApiKeyMiddleware:
    def test_valid_api_key(self):
        app = FastAPI()
        app.add_middleware(ApiKeyMiddleware, api_key="sk-valid-key")

        @app.get("/v1/models")
        async def models():
            return {"data": []}

        client = TestClient(app)
        response = client.get("/v1/models", headers={"Authorization": "Bearer sk-valid-key"})
        assert response.status_code == 200

    def test_missing_api_key(self):
        app = FastAPI()
        app.add_middleware(ApiKeyMiddleware, api_key="sk-valid-key")

        @app.get("/v1/models")
        async def models():
            return {"data": []}

        client = TestClient(app)
        response = client.get("/v1/models")
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert data["error"]["type"] == "authentication_error"

    def test_invalid_api_key(self):
        app = FastAPI()
        app.add_middleware(ApiKeyMiddleware, api_key="sk-valid-key")

        @app.get("/v1/models")
        async def models():
            return {"data": []}

        client = TestClient(app)
        response = client.get("/v1/models", headers={"Authorization": "Bearer sk-wrong-key"})
        assert response.status_code == 403
        data = response.json()
        assert data["error"]["type"] == "authentication_error"

    def test_excluded_paths(self):
        app = FastAPI()
        app.add_middleware(ApiKeyMiddleware, api_key="sk-valid-key")

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200

    def test_invalid_auth_header_format(self):
        app = FastAPI()
        app.add_middleware(ApiKeyMiddleware, api_key="sk-valid-key")

        @app.get("/v1/models")
        async def models():
            return {"data": []}

        client = TestClient(app)
        response = client.get("/v1/models", headers={"Authorization": "Basic abc123"})
        assert response.status_code == 401


class TestRateLimitMiddleware:
    def test_within_limit(self):
        app = FastAPI()
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        app.add_middleware(RateLimitMiddleware, limiter=limiter)

        @app.get("/v1/chat/completions")
        async def chat():
            return {"choices": []}

        client = TestClient(app)
        response = client.get("/v1/chat/completions")
        assert response.status_code == 200
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Limit" in response.headers

    def test_rate_limited(self):
        app = FastAPI()
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        app.add_middleware(RateLimitMiddleware, limiter=limiter)

        @app.get("/v1/chat/completions")
        async def chat():
            return {"choices": []}

        client = TestClient(app)
        for _ in range(2):
            response = client.get("/v1/chat/completions")
            assert response.status_code == 200

        response = client.get("/v1/chat/completions")
        assert response.status_code == 429
        data = response.json()
        assert data["error"]["type"] == "rate_limit_error"

    def test_excluded_paths(self):
        app = FastAPI()
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        app.add_middleware(RateLimitMiddleware, limiter=limiter)

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        client = TestClient(app)
        for _ in range(5):
            response = client.get("/health")
            assert response.status_code == 200
