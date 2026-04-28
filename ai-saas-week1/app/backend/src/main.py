"""FastAPI主应用入口"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from uuid import uuid4
import logging
from app.config import settings
from app.routes.v1 import router as v1_router
from app.exceptions.handlers import register_exception_handlers
from app.dependencies import engine, redis_client

# 设置日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(request_id)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger(__name__)

# 请求上下文，存储 request_id
class RequestContext:
    request_id: str = None

request_context = RequestContext()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"启动 {settings.app_name} v{settings.app_version}", extra={"request_id": "SYSTEM"})
    yield
    await engine.dispose()
    await redis_client.close()
    logger.info(f"关闭 {settings.app_name}", extra={"request_id": "SYSTEM"})


app = FastAPI(title=settings.app_name, version=settings.app_version, description="AI SaaS FastAPI 后端服务", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    # 生成或获取 request_id
    request_id = request.headers.get("X-Request-ID", str(uuid4()))

    # 将 request_id 存储到上下文
    request_context.request_id = request_id

    # 添加 request_id 到请求状态
    request.state.request_id = request_id

    # 记录请求日志
    logger.info(f"请求开始: {request.method} {request.url}", extra={"request_id": request_id})

    # 执行请求
    response: Response = await call_next(request)

    # 添加 request_id 到响应头
    response.headers["X-Request-ID"] = request_id

    # 记录响应日志
    logger.info(f"请求结束: {request.method} {request.url} - {response.status_code}", extra={"request_id": request_id})

    return response


app.include_router(v1_router, prefix="/api/v1")
register_exception_handlers(app)
