"""FastAPI主应用入口"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from routes.v1 import router as v1_router
from exceptions.handlers import register_exception_handlers
from dependencies import engine, redis_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"启动 {settings.app_name} v{settings.app_version}")
    yield
    await engine.dispose()
    await redis_client.close()


app = FastAPI(title=settings.app_name, version=settings.app_version, description="AI SaaS FastAPI 后端服务", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(v1_router, prefix="/api/v1")
register_exception_handlers(app)
