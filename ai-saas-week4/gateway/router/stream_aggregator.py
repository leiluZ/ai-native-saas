"""Stream aggregator - continue outputting chunks after fallback, no frontend disruption"""

import asyncio
import json
import logging
import time
from typing import AsyncGenerator, Optional

import httpx

from gateway.config import settings
from gateway.router.config import router_config
from gateway.router.engine import RouteDecision, RouteTarget, get_router_engine

logger = logging.getLogger(__name__)


class StreamAggregator:
    def __init__(self):
        self._active_streams: dict[str, dict] = {}

    async def stream_with_fallback(
        self,
        primary_endpoint: str,
        fallback_endpoint: str,
        request_body: dict,
        api_key: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if request_id:
            headers["X-Request-ID"] = request_id

        stream_body = {**request_body, "stream": True}
        router = get_router_engine()

        primary_url = f"{primary_endpoint.rstrip('/')}/v1/chat/completions"
        fallback_url = f"{fallback_endpoint.rstrip('/')}/v1/chat/completions"

        accumulated_content = ""
        finish_reason = None
        usage = None
        model = request_body.get("model", "unknown")
        switch_occurred = False
        switch_start = 0.0

        try:
            async with httpx.AsyncClient(timeout=settings.global_timeout) as client:
                async with client.stream("POST", primary_url, json=stream_body, headers=headers) as response:
                    if response.status_code != 200:
                        error_body = ""
                        async for chunk in response.aiter_text():
                            error_body += chunk
                        raise PrimaryStreamError(
                            status_code=response.status_code,
                            message=f"Primary upstream error: {error_body[:500]}",
                        )

                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                continue
                            try:
                                data = json.loads(data_str)
                                choices = data.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    accumulated_content += delta.get("content", "")
                                    finish_reason = choices[0].get("finish_reason") or finish_reason
                                usage = data.get("usage") or usage
                                model = data.get("model", model)
                            except json.JSONDecodeError:
                                pass
                            yield line + "\n"
                        elif line.startswith(":"):
                            yield line + "\n"

        except (PrimaryStreamError, httpx.TimeoutException, httpx.ConnectError, Exception) as e:
            switch_occurred = True
            switch_start = time.time()
            router.record_switch_success()
            logger.warning(f"Stream fallback triggered: {e}")

            fallback_body = {**request_body, "stream": True}
            if accumulated_content:
                fallback_body["messages"] = list(request_body.get("messages", []))
                fallback_body["messages"].append({
                    "role": "assistant",
                    "content": accumulated_content,
                })

            try:
                async with httpx.AsyncClient(timeout=settings.global_timeout) as client:
                    async with client.stream("POST", fallback_url, json=fallback_body, headers=headers) as response:
                        if response.status_code != 200:
                            router.record_switch_failure()
                            yield f"data: {json.dumps({'error': 'Fallback stream failed'})}\n\n"
                            yield "data: [DONE]\n\n"
                            return

                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                data_str = line[6:]
                                if data_str == "[DONE]":
                                    continue
                                try:
                                    data = json.loads(data_str)
                                    choices = data.get("choices", [])
                                    if choices:
                                        delta = choices[0].get("delta", {})
                                        new_content = delta.get("content", "")
                                        if new_content:
                                            accumulated_content += new_content
                                        finish_reason = choices[0].get("finish_reason") or finish_reason
                                    usage = data.get("usage") or usage
                                    model = data.get("model", model)
                                except json.JSONDecodeError:
                                    pass
                                yield line + "\n"
                            elif line.startswith(":"):
                                yield line + "\n"

                switch_latency = (time.time() - switch_start) * 1000
                if switch_latency > router_config.switch_latency_budget_ms:
                    logger.warning(
                        f"Stream switch latency {switch_latency:.2f}ms exceeded budget "
                        f"{router_config.switch_latency_budget_ms}ms"
                    )

            except Exception as fallback_error:
                router.record_switch_failure()
                logger.error(f"Fallback stream also failed: {fallback_error}")
                yield f"data: {json.dumps({'error': 'Both primary and fallback streams failed'})}\n\n"
                yield "data: [DONE]\n\n"
                return

        yield "data: [DONE]\n\n"


class PrimaryStreamError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


_stream_aggregator: Optional[StreamAggregator] = None


def get_stream_aggregator() -> StreamAggregator:
    global _stream_aggregator
    if _stream_aggregator is None:
        _stream_aggregator = StreamAggregator()
    return _stream_aggregator


def set_stream_aggregator(aggregator: StreamAggregator):
    global _stream_aggregator
    _stream_aggregator = aggregator
