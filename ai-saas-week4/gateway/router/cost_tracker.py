"""Cost tracker - single user monthly cap $10, exceed -> degrade to local"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from gateway.router.config import router_config

logger = logging.getLogger(__name__)


@dataclass
class CostRecord:
    user_id: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class UserCost:
    user_id: str
    monthly_cost_usd: float = 0.0
    total_tokens: int = 0
    records: list[CostRecord] = field(default_factory=list)


class CostTracker:
    def __init__(self):
        self._users: dict[str, UserCost] = {}
        self._month_start = time.time()

    def _get_month_key(self) -> str:
        return time.strftime("%Y-%m", time.localtime())

    def _reset_if_new_month(self):
        current_month = self._get_month_key()
        month_start_key = time.strftime("%Y-%m", time.localtime(self._month_start))
        if current_month != month_start_key:
            self._users.clear()
            self._month_start = time.time()

    def _calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        if "gpt-4" in model.lower():
            cost_per_1k = router_config.cost_gpt4_per_1k_tokens
        elif "gpt-3.5" in model.lower():
            cost_per_1k = router_config.cost_gpt35_per_1k_tokens
        else:
            return 0.0
        return (prompt_tokens + completion_tokens) / 1000 * cost_per_1k

    def record_usage(self, user_id: str, model: str, prompt_tokens: int, completion_tokens: int):
        self._reset_if_new_month()
        cost = self._calculate_cost(model, prompt_tokens, completion_tokens)

        if user_id not in self._users:
            self._users[user_id] = UserCost(user_id=user_id)

        user = self._users[user_id]
        user.monthly_cost_usd += cost
        user.total_tokens += prompt_tokens + completion_tokens
        user.records.append(CostRecord(
            user_id=user_id,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost,
        ))

        if len(user.records) > 10000:
            user.records = user.records[-10000:]

    def is_over_budget(self, user_id: str) -> bool:
        self._reset_if_new_month()
        user = self._users.get(user_id)
        if user is None:
            return False
        return user.monthly_cost_usd >= router_config.cost_monthly_cap_usd

    def get_user_cost(self, user_id: str) -> Optional[UserCost]:
        self._reset_if_new_month()
        return self._users.get(user_id)

    def get_all_costs(self) -> dict[str, UserCost]:
        self._reset_if_new_month()
        return dict(self._users)

    def get_monthly_total(self) -> float:
        self._reset_if_new_month()
        return sum(u.monthly_cost_usd for u in self._users.values())


_cost_tracker: Optional[CostTracker] = None


def get_cost_tracker() -> CostTracker:
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = CostTracker()
    return _cost_tracker


def set_cost_tracker(tracker: CostTracker):
    global _cost_tracker
    _cost_tracker = tracker
