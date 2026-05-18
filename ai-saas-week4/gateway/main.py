"""OpenAI 兼容 API 网关 - FastAPI 主入口"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gateway.config import settings
from gateway.middleware import setup_middleware
from gateway.registry import ModelEntry, model_registry
from gateway.router.health_checker import get_health_checker
from gateway.routes.admin import router as admin_router
from gateway.routes.chat import router as chat_router
from gateway.routes.embeddings import router as embeddings_router
from gateway.routes.health import router as health_router
from gateway.routes.models import router as models_router


def setup_logging():
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(request_id)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.INFO,
    )


setup_logging()
logger = logging.getLogger(__name__)


def register_default_models():
    model_registry.register(
        ModelEntry(
            name="gpt-3.5-turbo",
            provider="openai",
            endpoint="https://api.openai.com",
            api_key=None,
            priority=10,
        )
    )
    model_registry.register(
        ModelEntry(
            name="vllm-local",
            provider="vllm",
            endpoint="http://localhost:8000",
            api_key=None,
            priority=1,
        )
    )
    model_registry.register(
        ModelEntry(
            name="ollama-local",
            provider="ollama",
            endpoint="http://localhost:11434",
            api_key=None,
            priority=2,
        )
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")

    register_default_models()
    await model_registry.start_health_check_loop()

    health_checker = get_health_checker()
    health_checker.start()

    yield

    await health_checker.stop()
    await model_registry.stop_health_check_loop()
    logger.info(f"Shutting down {settings.app_name}")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="OpenAI-compatible API Gateway with multi-model routing, streaming, and Function Calling support",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

setup_middleware(app, exclude_paths=["/health", "/docs", "/openapi.json", "/redoc", "/", "/admin"])

app.include_router(health_router)
app.include_router(chat_router)
app.include_router(models_router)
app.include_router(embeddings_router)
app.include_router(admin_router)


@app.get("/")
async def root():
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
    }
