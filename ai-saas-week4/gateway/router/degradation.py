"""Degradation triggers - P99 > 800ms, 5xx >= 3 consecutive, GPU memory > 95%"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from gateway.router.config import router_config
from gateway.router.health_checker import HealthStats

logger = logging.getLogger(__name__)


class DegradationReason(str, Enum):
    NONE = "none"
    P99_LATENCY = "p99_latency"
    CONSECUTIVE_5XX = "consecutive_5xx"
    GPU_MEMORY = "gpu_memory"
    MANUAL = "manual"


@dataclass
class DegradationDecision:
    should_degrade: bool = False
    reason: DegradationReason = DegradationReason.NONE
    detail: str = ""
    timestamp: float = field(default_factory=__import__("time").time)


class DegradationTrigger:
    def __init__(self):
        self._degraded = False
        self._degraded_since: Optional[float] = None
        self._last_decision = DegradationDecision()
        self._decision_history: list[DegradationDecision] = []

    @property
    def is_degraded(self) -> bool:
        return self._degraded

    @property
    def last_decision(self) -> DegradationDecision:
        return self._last_decision

    @property
    def decision_history(self) -> list[DegradationDecision]:
        return list(self._decision_history)

    def evaluate(self, stats: HealthStats) -> DegradationDecision:
        reasons = []

        if stats.p99_latency_ms > router_config.degradation_p99_threshold_ms:
            reasons.append((
                DegradationReason.P99_LATENCY,
                f"P99 latency {stats.p99_latency_ms:.1f}ms > {router_config.degradation_p99_threshold_ms}ms",
            ))

        if stats.consecutive_5xx >= router_config.degradation_consecutive_5xx:
            reasons.append((
                DegradationReason.CONSECUTIVE_5XX,
                f"Consecutive 5xx errors {stats.consecutive_5xx} >= {router_config.degradation_consecutive_5xx}",
            ))

        if stats.latest_gpu_memory_pct > router_config.degradation_gpu_memory_pct:
            reasons.append((
                DegradationReason.GPU_MEMORY,
                f"GPU memory {stats.latest_gpu_memory_pct:.1f}% > {router_config.degradation_gpu_memory_pct}%",
            ))

        if reasons:
            decision = DegradationDecision(
                should_degrade=True,
                reason=reasons[0][0],
                detail="; ".join(r[1] for r in reasons),
            )
        else:
            decision = DegradationDecision(
                should_degrade=False,
                reason=DegradationReason.NONE,
                detail="All metrics within thresholds",
            )

        self._apply_decision(decision)
        return decision

    def _apply_decision(self, decision: DegradationDecision):
        import time
        self._last_decision = decision
        self._decision_history.append(decision)
        if len(self._decision_history) > 1000:
            self._decision_history = self._decision_history[-1000:]

        if decision.should_degrade and not self._degraded:
            self._degraded = True
            self._degraded_since = time.time()
            logger.warning(f"DEGRADATION TRIGGERED: {decision.detail}")
        elif not decision.should_degrade and self._degraded:
            self._degraded = False
            self._degraded_since = None
            logger.info("Degradation cleared - all metrics back to normal")

    def force_degrade(self, reason: str = "manual"):
        import time
        decision = DegradationDecision(
            should_degrade=True,
            reason=DegradationReason.MANUAL,
            detail=reason,
        )
        self._apply_decision(decision)

    def force_recover(self):
        import time
        decision = DegradationDecision(
            should_degrade=False,
            reason=DegradationReason.NONE,
            detail="Manual recovery",
        )
        self._apply_decision(decision)


_degradation_trigger: Optional[DegradationTrigger] = None


def get_degradation_trigger() -> DegradationTrigger:
    global _degradation_trigger
    if _degradation_trigger is None:
        _degradation_trigger = DegradationTrigger()
    return _degradation_trigger


def set_degradation_trigger(trigger: DegradationTrigger):
    global _degradation_trigger
    _degradation_trigger = trigger
