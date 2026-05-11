"""健康检查路由"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis.asyncio as redis
from src.schemas.common import ResponseBase
from src.dependencies import get_db, get_redis

router = APIRouter(prefix="/health", tags=["健康检查"])


@router.get("/", summary="健康检查")
async def health_check(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
):
    request_id = request.state.request_id

    # 检查数据库
    try:
        await db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    # 检查 Redis
    try:
        await redis_client.ping()
        redis_status = "healthy"
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"

    # 验证 LangGraph 状态机（迁移要求）
    # comment out for now to stop LLM call
    state_machine_status = "healthy (skipped)"
    # try:
    #    result = await run_langgraph("health check", "health-check-thread")
    #    if "final_response" in result:
    #        state_machine_status = "healthy"
    #    else:
    #        state_machine_status = "unhealthy: no response"
    # except Exception as e:
    #    state_machine_status = f"unhealthy: {str(e)}"

    return ResponseBase(
        code=200,
        message="success",
        data={
            "api": "healthy",
            "database": db_status,
            "redis": redis_status,
            "state_machine": state_machine_status,
        },
        request_id=request_id,
    )
