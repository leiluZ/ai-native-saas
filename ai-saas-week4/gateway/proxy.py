"""OpenAI 兼容代理 - 请求转发、流式处理、指数退避重试"""

import asyncio
import json
import logging
import time
from typing import AsyncGenerator, Optional

import httpx

from gateway.config import settings
from gateway.registry import ModelEntry, model_registry

logger = logging.getLogger(__name__)


class ProxyError(Exception):
    def __init__(self, status_code: int, message: str, error_type: str = "proxy_error"):
        self.status_code = status_code
        self.message = message
        self.error_type = error_type
        super().__init__(message)


def _build_backend_url(endpoint: str, path: str) -> str:
    return f"{endpoint.rstrip('/')}{path}"


def _build_headers(api_key: Optional[str], request_id: Optional[str] = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if request_id:
        headers["X-Request-ID"] = request_id
    return headers


async def _retry_with_backoff(
    func,
    *args,
    max_retries: int = None,
    **kwargs,
):
    if max_retries is None:
        max_retries = settings.max_retries

    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as e:
            last_exception = e
            if attempt < max_retries:
                delay = min(
                    settings.retry_backoff_base * (2 ** attempt),
                    settings.retry_backoff_max,
                )
                logger.warning(
                    f"Request failed (attempt {attempt + 1}/{max_retries + 1}), "
                    f"retrying in {delay:.1f}s: {e}"
                )
                await asyncio.sleep(delay)
            else:
                raise ProxyError(
                    status_code=502,
                    message=f"Upstream request failed after {max_retries + 1} attempts: {e}",
                    error_type="upstream_error",
                ) from e
        except httpx.HTTPStatusError as e:
            raise ProxyError(
                status_code=e.response.status_code,
                message=f"Upstream returned error: {e.response.status_code}",
                error_type="upstream_error",
            ) from e

    if last_exception:
        raise last_exception


async def proxy_chat_completions(
    entry: ModelEntry,
    request_body: dict,
    request_id: Optional[str] = None,
) -> dict:
    url = _build_backend_url(entry.endpoint, "/v1/chat/completions")
    headers = _build_headers(entry.api_key, request_id)

    async def _request():
        async with httpx.AsyncClient(timeout=settings.global_timeout) as client:
            response = await client.post(url, json=request_body, headers=headers)
            response.raise_for_status()
            return response.json()

    return await _retry_with_backoff(_request)


async def proxy_chat_completions_stream(
    entry: ModelEntry,
    request_body: dict,
    request_id: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    url = _build_backend_url(entry.endpoint, "/v1/chat/completions")
    headers = _build_headers(entry.api_key, request_id)
    stream_body = {**request_body, "stream": True}

    last_heartbeat = time.time()

    async def _stream_request():
        async with httpx.AsyncClient(timeout=settings.global_timeout) as client:
            async with client.stream("POST", url, json=stream_body, headers=headers) as response:
                if response.status_code != 200:
                    error_body = ""
                    async for chunk in response.aiter_text():
                        error_body += chunk
                    raise ProxyError(
                        status_code=response.status_code,
                        message=f"Upstream error: {error_body[:500]}",
                        error_type="upstream_error",
                    )

                async for line in response.aiter_lines():
                    yield line

    try:
        async for line in _stream_request():
            yield line
            last_heartbeat = time.time()

            if time.time() - last_heartbeat > settings.heartbeat_interval:
                yield ": heartbeat\n\n"
                last_heartbeat = time.time()
    except ProxyError:
        raise
    except Exception as e:
        logger.error(f"Stream proxy error: {e}")
        raise ProxyError(
            status_code=502,
            message=f"Stream proxy error: {e}",
            error_type="upstream_error",
        )


async def proxy_list_models(
    entry: ModelEntry,
    request_id: Optional[str] = None,
) -> dict:
    url = _build_backend_url(entry.endpoint, "/v1/models")
    headers = _build_headers(entry.api_key, request_id)

    async def _request():
        async with httpx.AsyncClient(timeout=settings.global_timeout) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()

    return await _retry_with_backoff(_request)


async def proxy_embeddings(
    entry: ModelEntry,
    request_body: dict,
    request_id: Optional[str] = None,
) -> dict:
    url = _build_backend_url(entry.endpoint, "/v1/embeddings")
    headers = _build_headers(entry.api_key, request_id)

    async def _request():
        async with httpx.AsyncClient(timeout=settings.global_timeout) as client:
            response = await client.post(url, json=request_body, headers=headers)
            response.raise_for_status()
            return response.json()

    return await _retry_with_backoff(_request)


def resolve_model(model_name: Optional[str], request_body: dict) -> tuple[Optional[ModelEntry], Optional[str]]:
    model_name = model_name or request_body.get("model")
    if not model_name:
        return None, "model parameter is required"

    entry = model_registry.get_best_model(model_name)
    if entry is None:
        return None, f"No healthy model found for: {model_name}"

    return entry, None
