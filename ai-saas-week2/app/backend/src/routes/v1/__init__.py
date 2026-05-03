"""API v1 路由模块"""

from fastapi import APIRouter
from .health import router as health_router
from .chat import router as chat_router
from .langgraph import router as langgraph_router

router = APIRouter()
router.include_router(health_router)
router.include_router(chat_router)
router.include_router(langgraph_router)
