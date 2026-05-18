"""Smart routing proxy layer"""

from gateway.router.config import RouterConfig, router_config
from gateway.router.health_checker import (
    HealthChecker,
    HealthSnapshot,
    HealthStats,
    get_health_checker,
    set_health_checker,
)
from gateway.router.degradation import (
    DegradationDecision,
    DegradationReason,
    DegradationTrigger,
    get_degradation_trigger,
    set_degradation_trigger,
)
from gateway.router.engine import (
    RouteDecision,
    RouteReason,
    RouteTarget,
    RouterEngine,
    get_router_engine,
    set_router_engine,
)
from gateway.router.cost_tracker import (
    CostRecord,
    CostTracker,
    UserCost,
    get_cost_tracker,
    set_cost_tracker,
)
from gateway.router.stream_aggregator import (
    StreamAggregator,
    get_stream_aggregator,
    set_stream_aggregator,
)
from gateway.router.metrics import (
    RouterMetrics,
    get_metrics,
    set_metrics,
)

__all__ = [
    "RouterConfig",
    "router_config",
    "HealthChecker",
    "HealthSnapshot",
    "HealthStats",
    "get_health_checker",
    "set_health_checker",
    "DegradationDecision",
    "DegradationReason",
    "DegradationTrigger",
    "get_degradation_trigger",
    "set_degradation_trigger",
    "RouteDecision",
    "RouteReason",
    "RouteTarget",
    "RouterEngine",
    "get_router_engine",
    "set_router_engine",
    "CostRecord",
    "CostTracker",
    "UserCost",
    "get_cost_tracker",
    "set_cost_tracker",
    "StreamAggregator",
    "get_stream_aggregator",
    "set_stream_aggregator",
    "RouterMetrics",
    "get_metrics",
    "set_metrics",
]
