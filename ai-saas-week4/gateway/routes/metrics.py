"""Prometheus 指标端点"""

from fastapi import APIRouter, Response

from gateway.metrics import get_metrics_response

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def metrics():
    return Response(
        content=get_metrics_response(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
