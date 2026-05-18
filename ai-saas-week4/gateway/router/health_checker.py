"""Health checker - probes local endpoint every 5s, records success rate/latency/queue depth"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

from gateway.router.config import router_config

logger = logging.getLogger(__name__)


@dataclass
class HealthSnapshot:
    timestamp: float = field(default_factory=time.time)
    is_healthy: bool = False
    latency_ms: float = 0.0
    queue_depth: int = 0
    gpu_memory_pct: float = 0.0
    cpu_utilization_pct: float = 0.0
    gpu_utilization_pct: float = 0.0
    error: Optional[str] = None


@dataclass
class HealthStats:
    endpoint: str
    snapshots: list[HealthSnapshot] = field(default_factory=list)
    max_snapshots: int = 120

    @property
    def success_rate(self) -> float:
        if not self.snapshots:
            return 0.0
        healthy = sum(1 for s in self.snapshots if s.is_healthy)
        return healthy / len(self.snapshots)

    @property
    def p50_latency_ms(self) -> float:
        return self._percentile(50)

    @property
    def p99_latency_ms(self) -> float:
        return self._percentile(99)

    @property
    def avg_queue_depth(self) -> float:
        if not self.snapshots:
            return 0.0
        return sum(s.queue_depth for s in self.snapshots) / len(self.snapshots)

    @property
    def latest_gpu_memory_pct(self) -> float:
        if not self.snapshots:
            return 0.0
        return self.snapshots[-1].gpu_memory_pct

    @property
    def latest_cpu_pct(self) -> float:
        if not self.snapshots:
            return 0.0
        return self.snapshots[-1].cpu_utilization_pct

    @property
    def latest_gpu_pct(self) -> float:
        if not self.snapshots:
            return 0.0
        return self.snapshots[-1].gpu_utilization_pct

    @property
    def consecutive_5xx(self) -> int:
        count = 0
        for s in reversed(self.snapshots):
            if not s.is_healthy and s.error and "5" in str(s.error):
                count += 1
            else:
                break
        return count

    def _percentile(self, p: int) -> float:
        if not self.snapshots:
            return 0.0
        latencies = sorted(s.latency_ms for s in self.snapshots if s.is_healthy)
        if not latencies:
            return 0.0
        import math
        idx = math.ceil(len(latencies) * p / 100.0) - 1
        idx = max(0, min(idx, len(latencies) - 1))
        return latencies[idx]

    def add_snapshot(self, snapshot: HealthSnapshot):
        self.snapshots.append(snapshot)
        if len(self.snapshots) > self.max_snapshots:
            self.snapshots = self.snapshots[-self.max_snapshots:]


class HealthChecker:
    def __init__(self, endpoint: str, api_key: Optional[str] = None):
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.stats = HealthStats(endpoint=endpoint)
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def probe(self) -> HealthSnapshot:
        snapshot = HealthSnapshot()
        try:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            async with httpx.AsyncClient(timeout=router_config.health_check_timeout) as client:
                start = time.time()
                resp = await client.get(
                    f"{self.endpoint}/health",
                    headers=headers,
                )
                snapshot.latency_ms = (time.time() - start) * 1000

                if resp.status_code == 200:
                    snapshot.is_healthy = True
                    data = resp.json() if resp.text else {}
                    snapshot.queue_depth = data.get("queue_depth", 0)
                    snapshot.gpu_memory_pct = data.get("gpu_memory_pct", 0.0)
                    snapshot.cpu_utilization_pct = data.get("cpu_utilization_pct", 0.0)
                    snapshot.gpu_utilization_pct = data.get("gpu_utilization_pct", 0.0)
                else:
                    snapshot.error = str(resp.status_code)
        except Exception as e:
            snapshot.error = str(e)

        self.stats.add_snapshot(snapshot)
        return snapshot

    async def _loop(self):
        while self._running:
            try:
                await self.probe()
            except Exception as e:
                logger.error(f"Health check loop error: {e}")
            await asyncio.sleep(router_config.health_check_interval)

    def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def is_healthy(self) -> bool:
        if not self.stats.snapshots:
            return True
        return self.stats.snapshots[-1].is_healthy


_health_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker(endpoint="http://localhost:8000")
    return _health_checker


def set_health_checker(checker: HealthChecker):
    global _health_checker
    _health_checker = checker
