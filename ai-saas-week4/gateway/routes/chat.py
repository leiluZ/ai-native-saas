"""OpenAI 兼容 /v1/chat/completions 路由"""

import json
import logging
import time

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse

from gateway.proxy import (
    ProxyError,
    proxy_chat_completions,
    proxy_chat_completions_stream,
    resolve_model,
)
from gateway.registry import model_registry

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    request_id = getattr(request.state, "request_id", None)

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

    is_stream = body.get("stream", False)

    if is_stream:
        return StreamingResponse(
            _stream_response(entry, body, request_id),
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
        logger.info(
            f"Chat completion proxy latency: {elapsed_ms:.2f}ms",
            extra={"request_id": request_id},
        )
        return result
    except ProxyError as e:
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


async def _stream_response(entry, body, request_id):
    start_time = time.time()
    first_chunk_sent = False

    try:
        async for line in proxy_chat_completions_stream(entry, body, request_id):
            if line.startswith("data: ") and not first_chunk_sent:
                first_chunk_sent = True
                ttft_ms = (time.time() - start_time) * 1000
                logger.info(
                    f"Stream TTFT: {ttft_ms:.2f}ms",
                    extra={"request_id": request_id},
                )

            if line:
                yield f"{line}\n"
            else:
                yield "\n"

        yield "data: [DONE]\n\n"

        total_ms = (time.time() - start_time) * 1000
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
