"""OpenAI 兼容 /v1/chat/completions 路由 - 智能路由代理"""

import json
import logging
import time

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse

from gateway.proxy import (
    ProxyError,
    proxy_chat_completions,
    resolve_model,
)
from gateway.registry import model_registry
from gateway.router.cost_tracker import get_cost_tracker
from gateway.router.engine import (
    RouteTarget,
    get_router_engine,
)
from gateway.router.metrics import get_metrics
from gateway.router.stream_aggregator import get_stream_aggregator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

ENDPOINT_MAP = {
    RouteTarget.LOCAL_VLLM: "http://localhost:8000",
    RouteTarget.LOCAL_OLLAMA: "http://localhost:11434",
    RouteTarget.CLOUD_GPT4: "https://api.openai.com",
    RouteTarget.CLOUD_GPT35: "https://api.openai.com",
}


def _get_user_id(request: Request) -> str:
    user_id = request.headers.get("X-User-ID", "")
    if user_id:
        return user_id
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:][:32]
    return "anonymous"


def _estimate_tokens(body: dict) -> tuple[int, int]:
    prompt_tokens = 0
    for msg in body.get("messages", []):
        content = msg.get("content", "")
        if isinstance(content, str):
            prompt_tokens += len(content) // 4
    max_tokens = body.get("max_tokens", 256)
    return prompt_tokens, max_tokens


@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    request_id = getattr(request.state, "request_id", None)
    user_id = _get_user_id(request)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "message": "Invalid JSON in request body",
                    "type": "invalid_request_error",
                    "code": 400,
                }
            },
        )

    model_name = body.get("model")
    entry, error = resolve_model(model_name, body)
    if error:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "message": error,
                    "type": "invalid_request_error",
                    "code": 400,
                }
            },
        )

    engine = get_router_engine()
    decision = engine.decide(
        user_id=user_id,
        requested_model=model_name,
        is_stream=body.get("stream", False),
    )

    metrics = get_metrics()
    metrics.record_route_decision(decision.target.value, decision.reason.value)
    metrics.record_route_switch(True, decision.switch_latency_ms)

    is_stream = body.get("stream", False)

    if is_stream:
        aggregator = get_stream_aggregator()
        primary_endpoint = ENDPOINT_MAP.get(decision.target, "http://localhost:8000")
        fallback_endpoint = ENDPOINT_MAP.get(RouteTarget.CLOUD_GPT35, "https://api.openai.com")

        return StreamingResponse(
            get_stream_aggregator(aggregator, primary_endpoint, fallback_endpoint, body, request_id, user_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    try:
        start_time = time.time()
        result = await proxy_chat_completions(entry, body, request_id)
        elapsed_ms = (time.time() - start_time) * 1000

        prompt_tokens, completion_tokens = _estimate_tokens(body)
        if "usage" in result:
            prompt_tokens = result["usage"].get("prompt_tokens", prompt_tokens)
            completion_tokens = result["usage"].get("completion_tokens", completion_tokens)

        cost_tracker = get_cost_tracker()
        cost_tracker.record_usage(user_id, decision.target.value, prompt_tokens, completion_tokens)
        metrics.update_user_cost(user_id, cost_tracker.get_user_cost(user_id).monthly_cost_usd)
        metrics.update_total_cost(cost_tracker.get_monthly_total())

        logger.info(
            f"Chat completion proxy latency: {elapsed_ms:.2f}ms | "
            f"target={decision.target.value} | reason={decision.reason.value}",
            extra={"request_id": request_id},
        )
        return result
    except ProxyError as e:
        engine.record_switch_failure()
        return JSONResponse(
            status_code=e.status_code,
            content={
                "error": {
                    "message": e.message,
                    "type": e.error_type,
                    "code": e.status_code,
                }
            },
        )


async def _stream_with_router(aggregator, primary_endpoint, fallback_endpoint, body, request_id, user_id):
    start_time = time.time()
    first_chunk_sent = False
    total_content = ""

    try:
        async for line in aggregator.stream_with_fallback(
            primary_endpoint=primary_endpoint,
            fallback_endpoint=fallback_endpoint,
            request_body=body,
            request_id=request_id,
        ):
            if line.startswith("data: ") and not first_chunk_sent:
                first_chunk_sent = True
                ttft_ms = (time.time() - start_time) * 1000
                logger.info(
                    f"Stream TTFT: {ttft_ms:.2f}ms",
                    extra={"request_id": request_id},
                )

            if line.startswith("data: ") and "[DONE]" not in line:
                try:
                    data = json.loads(line[6:])
                    choices = data.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        total_content += delta.get("content", "")
                except json.JSONDecodeError:
                    pass

            if line:
                yield f"{line}\n"
            else:
                yield "\n"

        total_ms = (time.time() - start_time) * 1000

        prompt_tokens, completion_tokens = _estimate_tokens(body)
        completion_tokens = max(completion_tokens, len(total_content) // 4)

        cost_tracker = get_cost_tracker()
        cost_tracker.record_usage(user_id, body.get("model", "unknown"), prompt_tokens, completion_tokens)

        metrics = get_metrics()
        metrics.update_user_cost(user_id, cost_tracker.get_user_cost(user_id).monthly_cost_usd)
        metrics.update_total_cost(cost_tracker.get_monthly_total())

        logger.info(
            f"Stream completed in {total_ms:.2f}ms",
            extra={"request_id": request_id},
        )
    except ProxyError as e:
        error_chunk = {
            "error": {
                "message": e.message,
                "type": e.error_type,
                "code": e.status_code,
            }
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        logger.error(f"Stream error: {e}", extra={"request_id": request_id})
        error_chunk = {
            "error": {
                "message": f"Internal stream error: {str(e)}",
                "type": "server_error",
                "code": 500,
            }
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"
        yield "data: [DONE]\n\n"
