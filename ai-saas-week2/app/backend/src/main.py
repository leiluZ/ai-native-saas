"""FastAPI主应用入口"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from uuid import uuid4
import logging
import subprocess
import sys
import time
import os
from app.config import settings
from app.routes.v1 import router as v1_router
from app.exceptions.handlers import register_exception_handlers
from app.dependencies import engine, redis_client


# 设置日志配置
class RequestIdFormatter(logging.Formatter):
    def format(self, record):
        if not hasattr(record, "request_id") or record.request_id is None:
            record.request_id = "-"
        return super().format(record)


def setup_logging():
    formatter = RequestIdFormatter(
        fmt="%(asctime)s - %(levelname)s - %(request_id)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)


setup_logging()

logger = logging.getLogger(__name__)


# 请求上下文，存储 request_id
class RequestContext:
    request_id: str = None


request_context = RequestContext()


def wait_for_database(max_wait_seconds: int = 30):
    """等待数据库就绪"""
    import socket

    db_host = os.environ.get("DB_HOST", "db")
    db_port = int(os.environ.get("DB_PORT", "5432"))

    logger.info(f"等待数据库就绪: {db_host}:{db_port}", extra={"request_id": "SYSTEM"})

    start_time = time.time()
    while time.time() - start_time < max_wait_seconds:
        try:
            s = socket.socket()
            s.settimeout(1)
            if s.connect_ex((db_host, db_port)) == 0:
                s.close()
                logger.info("数据库连接就绪", extra={"request_id": "SYSTEM"})
                return True
            s.close()
        except Exception as e:
            logger.debug(f"等待数据库: {e}", extra={"request_id": "SYSTEM"})

        time.sleep(1)

    logger.error(
        f"数据库在 {max_wait_seconds} 秒内未就绪", extra={"request_id": "SYSTEM"}
    )
    return False


def run_alembic_migrations():
    """运行数据库迁移"""
    try:
        logger.info("正在检查并运行数据库迁移...", extra={"request_id": "SYSTEM"})
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            cwd="/app",
        )
        if result.returncode == 0:
            logger.info("数据库迁移完成", extra={"request_id": "SYSTEM"})
        else:
            logger.warning(
                f"数据库迁移返回非零状态: {result.returncode}",
                extra={"request_id": "SYSTEM"},
            )
            if result.stdout:
                logger.info(
                    f"迁移输出: {result.stdout}", extra={"request_id": "SYSTEM"}
                )
            if result.stderr:
                logger.warning(
                    f"迁移错误: {result.stderr}", extra={"request_id": "SYSTEM"}
                )
    except Exception as e:
        logger.error(f"运行数据库迁移时出错: {e}", extra={"request_id": "SYSTEM"})


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        f"启动 {settings.app_name} v{settings.app_version}",
        extra={"request_id": "SYSTEM"},
    )
    wait_for_database()
    run_alembic_migrations()
    yield
    await engine.dispose()
    await redis_client.close()
    logger.info(f"关闭 {settings.app_name}", extra={"request_id": "SYSTEM"})


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI SaaS FastAPI 后端服务",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    # 生成或获取 request_id
    request_id = request.headers.get("X-Request-ID", str(uuid4()))

    # 将 request_id 存储到上下文
    request_context.request_id = request_id

    # 添加 request_id 到请求状态
    request.state.request_id = request_id

    # 记录请求日志
    logger.info(
        f"请求开始: {request.method} {request.url}", extra={"request_id": request_id}
    )

    # 执行请求
    response: Response = await call_next(request)

    # 添加 request_id 到响应头
    response.headers["X-Request-ID"] = request_id

    # 记录响应日志
    logger.info(
        f"请求结束: {request.method} {request.url} - {response.status_code}",
        extra={"request_id": request_id},
    )

    return response


app.include_router(v1_router, prefix="/api/v1")
register_exception_handlers(app)
