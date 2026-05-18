"""Prometheus metrics exposure for router decisions, cost, latency"""

import logging
from typing import Optional

from gateway.router.config import router_config

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Gauge, Histogram, generate_latest, REGISTRY
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False
    logger.warning("prometheus_client not installed, metrics disabled")


class RouterMetrics:
    def __init__(self):
        self._enabled = HAS_PROMETHEUS
        if not self._enabled:
            return

        self.route_decisions_total = Counter(
            "gateway_route_decisions_total",
            "Total route decisions",
            ["target", "reason"],
        )

        self.route_switch_total = Counter(
            "gateway_route_switch_total",
            "Total route switches",
            ["status"],
        )

        self.route_switch_latency = Histogram(
            "gateway_route_switch_latency_ms",
            "Route switch decision latency in ms",
            buckets=[1, 5, 10, 25, 50, 100, 250, 500],
        )

        self.degradation_active = Gauge(
            "gateway_degradation_active",
            "Whether degradation is currently active (1=yes, 0=no)",
        )

        self.health_check_success = Counter(
            "gateway_health_check_total",
            "Health check results",
            ["status"],
        )

        self.health_latency_p99 = Gauge(
            "gateway_health_latency_p99_ms",
            "P99 health check latency in ms",
        )

        self.health_latency_p50 = Gauge(
            "gateway_health_latency_p50_ms",
            "P50 health check latency in ms",
        )

        self.gpu_memory_pct = Gauge(
            "gateway_gpu_memory_pct",
            "GPU memory utilization percentage",
        )

        self.cpu_utilization_pct = Gauge(
            "gateway_cpu_utilization_pct",
            "CPU utilization percentage",
        )

        self.gpu_utilization_pct = Gauge(
            "gateway_gpu_utilization_pct",
            "GPU utilization percentage",
        )

        self.user_cost_usd = Gauge(
            "gateway_user_cost_usd",
            "User monthly cost in USD",
            ["user_id"],
        )

        self.total_monthly_cost = Gauge(
            "gateway_total_monthly_cost_usd",
            "Total monthly cost across all users",
        )

        self.stream_fallback_total = Counter(
            "gateway_stream_fallback_total",
            "Stream fallback events",
            ["status"],
        )

    def record_route_decision(self, target: str, reason: str):
        if not self._enabled:
            return
        self.route_decisions_total.labels(target=target, reason=reason).inc()

    def record_route_switch(self, success: bool, latency_ms: float):
        if not self._enabled:
            return
        status = "success" if success else "failure"
        self.route_switch_total.labels(status=status).inc()
        self.route_switch_latency.observe(latency_ms)

    def set_degradation_status(self, active: bool):
        if not self._enabled:
            return
        self.degradation_active.set(1 if active else 0)

    def record_health_check(self, success: bool):
        if not self._enabled:
            return
        status = "success" if success else "failure"
        self.health_check_success.labels(status=status).inc()

    def update_health_metrics(self, p50_ms: float, p99_ms: float):
        if not self._enabled:
            return
        self.health_latency_p50.set(p50_ms)
        self.health_latency_p99.set(p99_ms)

    def update_resource_metrics(self, gpu_mem_pct: float, cpu_pct: float, gpu_pct: float):
        if not self._enabled:
            return
        self.gpu_memory_pct.set(gpu_mem_pct)
        self.cpu_utilization_pct.set(cpu_pct)
        self.gpu_utilization_pct.set(gpu_pct)

    def update_user_cost(self, user_id: str, cost_usd: float):
        if not self._enabled:
            return
        self.user_cost_usd.labels(user_id=user_id).set(cost_usd)

    def update_total_cost(self, cost_usd: float):
        if not self._enabled:
            return
        self.total_monthly_cost.set(cost_usd)

    def record_stream_fallback(self, success: bool):
        if not self._enabled:
            return
        status = "success" if success else "failure"
        self.stream_fallback_total.labels(status=status).inc()

    def get_metrics_text(self) -> str:
        if not self._enabled:
            return "# prometheus_client not installed\n"
        return generate_latest(REGISTRY).decode("utf-8")


_metrics: Optional[RouterMetrics] = None


def get_metrics() -> RouterMetrics:
    global _metrics
    if _metrics is None:
        _metrics = RouterMetrics()
    return _metrics


def set_metrics(metrics: RouterMetrics):
    global _metrics
    _metrics = metrics
