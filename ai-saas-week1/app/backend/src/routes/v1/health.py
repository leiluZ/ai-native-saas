"""健康检查路由"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis
from app.schemas.common import ResponseBase
from app.dependencies import get_db, get_redis

router = APIRouter(prefix="/health", tags=["健康检查"])


@router.get("/", summary="健康检查")
async def health_check(request: Request, db: AsyncSession = Depends(get_db), redis_client: redis.Redis = Depends(get_redis)):
    request_id = request.state.request_id

    try:
        await db.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    try:
        await redis_client.ping()
        redis_status = "healthy"
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"

    return ResponseBase(code=200, message="success", data={"api": "healthy", "database": db_status, "redis": redis_status}, request_id=request_id)
