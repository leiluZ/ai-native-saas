"""模型注册表 - 管理模型条目、健康检查与自动降级"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import httpx

from gateway.config import settings

logger = logging.getLogger(__name__)


class ModelStatus(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    DEGRADED = "degraded"


@dataclass
class ModelEntry:
    name: str
    provider: str
    endpoint: str
    api_key: Optional[str] = None
    priority: int = 0
    status: ModelStatus = ModelStatus.UNKNOWN
    last_checked: float = 0.0
    consecutive_failures: int = 0
    max_consecutive_failures: int = 3

    def to_openai_model(self) -> dict:
        return {
            "id": self.name,
            "object": "model",
            "created": int(self.last_checked),
            "owned_by": self.provider,
        }


class ModelRegistry:
    def __init__(self):
        self._models: dict[str, ModelEntry] = {}
        self._lock = asyncio.Lock()
        self._health_check_task: Optional[asyncio.Task] = None

    def register(self, entry: ModelEntry):
        self._models[entry.name] = entry

    def unregister(self, name: str):
        self._models.pop(name, None)

    def get(self, name: str) -> Optional[ModelEntry]:
        return self._models.get(name)

    def list_models(self) -> list[ModelEntry]:
        return list(self._models.values())

    def list_healthy_models(self) -> list[ModelEntry]:
        return [
            m
            for m in self._models.values()
            if m.status in (ModelStatus.HEALTHY, ModelStatus.DEGRADED)
        ]

    def get_best_model(self, preferred_name: Optional[str] = None) -> Optional[ModelEntry]:
        if preferred_name:
            entry = self._models.get(preferred_name)
            if entry and entry.status in (ModelStatus.HEALTHY, ModelStatus.DEGRADED):
                return entry

        healthy = sorted(
            [m for m in self._models.values() if m.status == ModelStatus.HEALTHY],
            key=lambda m: m.priority,
        )
        if healthy:
            return healthy[0]

        degraded = sorted(
            [m for m in self._models.values() if m.status == ModelStatus.DEGRADED],
            key=lambda m: m.priority,
        )
        if degraded:
            return degraded[0]

        return None

    async def check_model_health(self, entry: ModelEntry) -> bool:
        try:
            async with httpx.AsyncClient(timeout=settings.health_check_timeout) as client:
                response = await client.get(
                    f"{entry.endpoint.rstrip('/')}/health",
                    headers={"Authorization": f"Bearer {entry.api_key}"} if entry.api_key else {},
                )
                if response.status_code == 200:
                    return True

                response = await client.get(
                    f"{entry.endpoint.rstrip('/')}/v1/models",
                    headers={"Authorization": f"Bearer {entry.api_key}"} if entry.api_key else {},
                )
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"Health check failed for model {entry.name}: {e}")
            return False

    async def _update_model_status(self, entry: ModelEntry, healthy: bool):
        entry.last_checked = time.time()
        if healthy:
            entry.consecutive_failures = 0
            if entry.status == ModelStatus.DEGRADED:
                entry.status = ModelStatus.HEALTHY
                logger.info(f"Model {entry.name} recovered from degraded to healthy")
            else:
                entry.status = ModelStatus.HEALTHY
        else:
            entry.consecutive_failures += 1
            if entry.consecutive_failures >= entry.max_consecutive_failures:
                if entry.status == ModelStatus.HEALTHY:
                    entry.status = ModelStatus.DEGRADED
                    logger.warning(f"Model {entry.name} degraded after {entry.consecutive_failures} consecutive failures")
                elif entry.status == ModelStatus.DEGRADED:
                    entry.status = ModelStatus.UNHEALTHY
                    logger.error(f"Model {entry.name} marked unhealthy after {entry.consecutive_failures} consecutive failures")
            else:
                entry.status = ModelStatus.DEGRADED

    async def run_health_checks(self):
        async with self._lock:
            entries = list(self._models.values())

        results = await asyncio.gather(
            *[self.check_model_health(entry) for entry in entries],
            return_exceptions=True,
        )

        for entry, result in zip(entries, results):
            healthy = result is True
            await self._update_model_status(entry, healthy)

    async def start_health_check_loop(self):
        if self._health_check_task is not None:
            return

        async def _loop():
            while True:
                try:
                    await self.run_health_checks()
                except Exception as e:
                    logger.error(f"Health check loop error: {e}")
                await asyncio.sleep(settings.health_check_interval)

        self._health_check_task = asyncio.create_task(_loop())
        logger.info("Health check loop started")

    async def stop_health_check_loop(self):
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
            logger.info("Health check loop stopped")


model_registry = ModelRegistry()
