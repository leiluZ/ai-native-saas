import time
from prometheus_client import Counter, Gauge, Histogram, generate_latest, REGISTRY

REQUESTS_TOTAL = Counter(
    "gateway_requests_total",
    "Total number of requests received",
    ["endpoint", "method", "status"],
)

ERRORS_TOTAL = Counter(
    "gateway_errors_total",
    "Total number of error responses",
    ["endpoint", "error_type"],
)

REQUEST_LATENCY = Histogram(
    "gateway_request_latency_seconds",
    "Request latency in seconds",
    ["endpoint", "method"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

QUEUE_DEPTH = Gauge(
    "gateway_queue_depth",
    "Current request queue depth",
)

ACTIVE_CONNECTIONS = Gauge(
    "gateway_active_connections",
    "Number of active connections",
)

VRAM_USAGE = Gauge(
    "gateway_vram_usage_mb",
    "Estimated GPU VRAM usage in MB",
)

CACHE_HIT_RATE = Gauge(
    "gateway_cache_hit_rate",
    "KV Cache hit rate (0.0 - 1.0)",
)

ROUTE_DECISIONS = Counter(
    "gateway_route_decisions_total",
    "Total number of routing decisions",
    ["target", "reason"],
)

ROUTE_LATENCY = Histogram(
    "gateway_route_decision_seconds",
    "Route decision latency in seconds",
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1],
)

COST_TOTAL = Counter(
    "gateway_cost_dollars_total",
    "Total API cost in USD",
    ["user_id", "provider"],
)

SWITCH_FAILURES = Counter(
    "gateway_switch_failures_total",
    "Total route switch failures",
    ["from_target", "to_target"],
)


class MetricsMiddleware:
    def __init__(self):
        self._request_timers: dict = {}

    def record_request_start(self, request_id: str, endpoint: str, method: str):
        self._request_timers[request_id] = {
            "start": time.time(),
            "endpoint": endpoint,
            "method": method,
        }

    def record_request_end(self, request_id: str, endpoint: str, method: str, status_code: int):
        timer = self._request_timers.pop(request_id, None)
        elapsed = (time.time() - timer["start"]) if timer else 0

        status_str = str(status_code)
        REQUESTS_TOTAL.labels(endpoint=endpoint, method=method, status=status_str).inc()
        REQUEST_LATENCY.labels(endpoint=endpoint, method=method).observe(elapsed)

        if status_code >= 400:
            error_type = "4xx" if status_code < 500 else "5xx"
            ERRORS_TOTAL.labels(endpoint=endpoint, error_type=error_type).inc()

    def set_queue_depth(self, depth: int):
        QUEUE_DEPTH.set(depth)

    def set_active_connections(self, count: int):
        ACTIVE_CONNECTIONS.set(count)

    def set_vram_usage(self, mb: float):
        VRAM_USAGE.set(mb)

    def set_cache_hit_rate(self, rate: float):
        if 0.0 <= rate <= 1.0:
            CACHE_HIT_RATE.set(rate)

    def record_route_decision(self, target: str, reason: str, latency_s: float):
        ROUTE_DECISIONS.labels(target=target, reason=reason).inc()
        ROUTE_LATENCY.observe(latency_s)

    def record_cost(self, user_id: str, provider: str, amount: float):
        COST_TOTAL.labels(user_id=user_id, provider=provider).inc(amount)

    def record_switch_failure(self, from_target: str, to_target: str):
        SWITCH_FAILURES.labels(from_target=from_target, to_target=to_target).inc()


_metrics_middleware: MetricsMiddleware | None = None


def get_metrics_middleware() -> MetricsMiddleware:
    global _metrics_middleware
    if _metrics_middleware is None:
        _metrics_middleware = MetricsMiddleware()
    return _metrics_middleware


def get_metrics_response() -> bytes:
    return generate_latest(REGISTRY)
