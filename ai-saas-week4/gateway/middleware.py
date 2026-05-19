"""网关中间件 - API Key 校验、IP 限流、Tracing ID、超时重试"""

import asyncio
import logging
import time
from collections import defaultdict
from typing import Callable
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from gateway.config import settings
from gateway.metrics import get_metrics_middleware

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clients: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def is_allowed(self, client_ip: str) -> bool:
        async with self._lock:
            now = time.time()
            window_start = now - self.window_seconds
            self._clients[client_ip] = [
                t for t in self._clients[client_ip] if t > window_start
            ]
            if len(self._clients[client_ip]) >= self.max_requests:
                return False
            self._clients[client_ip].append(now)
            return True

    async def get_remaining(self, client_ip: str) -> int:
        async with self._lock:
            now = time.time()
            window_start = now - self.window_seconds
            self._clients[client_ip] = [
                t for t in self._clients[client_ip] if t > window_start
            ]
            return max(0, self.max_requests - len(self._clients[client_ip]))


rate_limiter = RateLimiter(
    max_requests=settings.rate_limit_per_minute,
    window_seconds=settings.rate_limit_window_seconds,
)


class TracingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        request.state.request_id = request_id
        request.state.start_time = time.time()

        metrics_mw = get_metrics_middleware()
        endpoint = request.url.path
        method = request.method

        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={"request_id": request_id},
        )

        response = await call_next(request)

        elapsed_ms = (time.time() - request.state.start_time) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.2f}"

        metrics_mw.record_request_end(
            request_id=request_id,
            endpoint=endpoint,
            method=method,
            status_code=response.status_code,
        )

        logger.info(
            f"Request completed: {request.method} {request.url.path} - {response.status_code} ({elapsed_ms:.2f}ms)",
            extra={"request_id": request_id},
        )

        return response


class ApiKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, api_key: str, exclude_paths: list[str] = None):
        super().__init__(app)
        self.api_key = api_key
        self.exclude_paths = exclude_paths or ["/health", "/docs", "/openapi.json", "/redoc"]

    def _is_excluded(self, path: str) -> bool:
        for p in self.exclude_paths:
            if p == "/":
                if path == "/":
                    return True
            elif path.startswith(p):
                return True
        return False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if self._is_excluded(request.url.path):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "message": "Missing or invalid Authorization header. Expected: Bearer <api_key>",
                        "type": "authentication_error",
                        "code": 401,
                    }
                },
            )

        token = auth_header[len("Bearer "):]
        if token != self.api_key:
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "message": "Invalid API key",
                        "type": "authentication_error",
                        "code": 403,
                    }
                },
            )

        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limiter: RateLimiter, exclude_paths: list[str] = None):
        super().__init__(app)
        self.limiter = limiter
        self.exclude_paths = exclude_paths or ["/health", "/docs", "/openapi.json", "/redoc"]

    def _is_excluded(self, path: str) -> bool:
        for p in self.exclude_paths:
            if p == "/":
                if path == "/":
                    return True
            elif path.startswith(p):
                return True
        return False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if self._is_excluded(request.url.path):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        allowed = await self.limiter.is_allowed(client_ip)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "message": "Rate limit exceeded. Please try again later.",
                        "type": "rate_limit_error",
                        "code": 429,
                    }
                },
            )

        response = await call_next(request)
        remaining = await self.limiter.get_remaining(client_ip)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Limit"] = str(self.limiter.max_requests)
        return response


def setup_middleware(app: FastAPI, api_key: str = None, exclude_paths: list[str] = None):
    if api_key is None:
        api_key = settings.gateway_api_key
    if exclude_paths is None:
        exclude_paths = ["/health", "/docs", "/openapi.json", "/redoc"]

    app.add_middleware(
        TracingMiddleware,
    )
    app.add_middleware(
        ApiKeyMiddleware,
        api_key=api_key,
        exclude_paths=exclude_paths,
    )
    app.add_middleware(
        RateLimitMiddleware,
        limiter=rate_limiter,
        exclude_paths=exclude_paths,
    )
