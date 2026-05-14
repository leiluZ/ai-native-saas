"""OpenAI 兼容 /v1/embeddings 路由"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from gateway.proxy import ProxyError, proxy_embeddings, resolve_model

logger = logging.getLogger(__name__)

router = APIRouter(tags=["embeddings"])


@router.post("/v1/embeddings")
async def create_embeddings(request: Request):
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

    try:
        result = await proxy_embeddings(entry, body, request_id)
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
