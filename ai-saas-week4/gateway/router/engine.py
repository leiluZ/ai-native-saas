"""Router decision engine - VIP/regular/cost/load balancing"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from gateway.router.config import router_config
from gateway.router.cost_tracker import get_cost_tracker
from gateway.router.degradation import get_degradation_trigger, DegradationReason
from gateway.router.health_checker import get_health_checker

logger = logging.getLogger(__name__)


class RouteTarget(str, Enum):
    LOCAL_VLLM = "vllm-local"
    LOCAL_OLLAMA = "ollama-local"
    CLOUD_GPT4 = "gpt-4"
    CLOUD_GPT35 = "gpt-3.5-turbo"


class RouteReason(str, Enum):
    VIP_USER = "vip_user"
    REGULAR_USER = "regular_user"
    DEGRADATION = "degradation"
    OVER_BUDGET = "over_budget"
    LOAD_BALANCE = "load_balance"
    DEFAULT = "default"
    FALLBACK = "fallback"


@dataclass
class RouteDecision:
    target: RouteTarget
    reason: RouteReason
    detail: str
    timestamp: float = field(default_factory=time.time)
    switch_latency_ms: float = 0.0
    user_id: str = ""
    model_requested: str = ""


class RouterEngine:
    def __init__(self):
        self._vip_users: set[str] = set()
        self._decision_history: list[RouteDecision] = []
        self._switch_count: int = 0
        self._switch_failure_count: int = 0

    def add_vip_user(self, user_id: str):
        self._vip_users.add(user_id)

    def remove_vip_user(self, user_id: str):
        self._vip_users.discard(user_id)

    def is_vip(self, user_id: str) -> bool:
        return user_id in self._vip_users

    @property
    def switch_failure_rate(self) -> float:
        if self._switch_count == 0:
            return 0.0
        return self._switch_failure_count / self._switch_count

    @property
    def decision_history(self) -> list[RouteDecision]:
        return list(self._decision_history)

    def decide(
        self,
        user_id: str = "",
        requested_model: str = "",
        is_stream: bool = False,
    ) -> RouteDecision:
        start = time.time()
        health_checker = get_health_checker()
        degradation = get_degradation_trigger()
        cost_tracker = get_cost_tracker()

        if degradation.last_decision.reason != DegradationReason.MANUAL:
            degradation.evaluate(health_checker.stats)

        if self.is_vip(user_id):
            decision = RouteDecision(
                target=RouteTarget.CLOUD_GPT4,
                reason=RouteReason.VIP_USER,
                detail=f"VIP user {user_id} routed to GPT-4",
                user_id=user_id,
                model_requested=requested_model,
            )
        elif degradation.is_degraded:
            decision = RouteDecision(
                target=RouteTarget.CLOUD_GPT35,
                reason=RouteReason.DEGRADATION,
                detail=f"Local degraded: {degradation.last_decision.detail}",
                user_id=user_id,
                model_requested=requested_model,
            )
        elif cost_tracker.is_over_budget(user_id):
            decision = RouteDecision(
                target=RouteTarget.LOCAL_VLLM,
                reason=RouteReason.OVER_BUDGET,
                detail=f"User {user_id} over monthly budget ${router_config.cost_monthly_cap_usd}",
                user_id=user_id,
                model_requested=requested_model,
            )
        elif (
            health_checker.stats.latest_cpu_pct > router_config.load_balance_cpu_threshold_pct
            or health_checker.stats.latest_gpu_pct > router_config.load_balance_gpu_threshold_pct
        ):
            decision = RouteDecision(
                target=RouteTarget.CLOUD_GPT35,
                reason=RouteReason.LOAD_BALANCE,
                detail=f"Local overloaded: CPU {health_checker.stats.latest_cpu_pct:.1f}%, GPU {health_checker.stats.latest_gpu_pct:.1f}%",
                user_id=user_id,
                model_requested=requested_model,
            )
        else:
            decision = RouteDecision(
                target=RouteTarget.LOCAL_VLLM,
                reason=RouteReason.DEFAULT,
                detail="Local vLLM healthy, routing locally",
                user_id=user_id,
                model_requested=requested_model,
            )

        decision.switch_latency_ms = (time.time() - start) * 1000
        self._record_decision(decision)
        return decision

    def _record_decision(self, decision: RouteDecision):
        self._decision_history.append(decision)
        if len(self._decision_history) > 10000:
            self._decision_history = self._decision_history[-10000:]

        logger.info(
            f"Route decision: {decision.target.value} | "
            f"reason={decision.reason.value} | "
            f"user={decision.user_id} | "
            f"latency={decision.switch_latency_ms:.2f}ms | "
            f"detail={decision.detail}"
        )

    def record_switch_failure(self):
        self._switch_count += 1
        self._switch_failure_count += 1

    def record_switch_success(self):
        self._switch_count += 1


_router_engine: Optional[RouterEngine] = None


def get_router_engine() -> RouterEngine:
    global _router_engine
    if _router_engine is None:
        _router_engine = RouterEngine()
    return _router_engine


def set_router_engine(engine: RouterEngine):
    global _router_engine
    _router_engine = engine
