"""健康检查路由"""

from fastapi import APIRouter, Request, Response

from gateway.registry import model_registry

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check(request: Request):
    models_status = {}
    for entry in model_registry.list_models():
        models_status[entry.name] = {
            "status": entry.status.value,
            "provider": entry.provider,
            "priority": entry.priority,
            "last_checked": entry.last_checked,
        }

    healthy_count = len(model_registry.list_healthy_models())
    total_count = len(model_registry.list_models())

    return {
        "status": "healthy" if healthy_count > 0 else "degraded",
        "gateway": "running",
        "models": models_status,
        "healthy_models": healthy_count,
        "total_models": total_count,
        "request_id": getattr(request.state, "request_id", None),
    }


@router.get("/healthz")
async def healthz():
    return Response(
        content="ok",
        media_type="text/plain",
        status_code=200,
    )
