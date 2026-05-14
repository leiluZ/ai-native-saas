"""OpenAI 兼容 /v1/models 路由"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from gateway.proxy import ProxyError, proxy_list_models, resolve_model
from gateway.registry import model_registry

router = APIRouter(tags=["models"])


@router.get("/v1/models")
async def list_models(request: Request):
    request_id = getattr(request.state, "request_id", None)

    models = []
    for entry in model_registry.list_healthy_models():
        models.append(entry.to_openai_model())

    if not models:
        all_entries = model_registry.list_models()
        for entry in all_entries:
            models.append(entry.to_openai_model())

    return {
        "object": "list",
        "data": models,
    }


@router.get("/v1/models/{model_name:path}")
async def retrieve_model(model_name: str, request: Request):
    request_id = getattr(request.state, "request_id", None)

    entry = model_registry.get(model_name)
    if entry is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "message": f"Model not found: {model_name}",
                    "type": "invalid_request_error",
                    "code": 404,
                }
            },
        )

    return entry.to_openai_model()
