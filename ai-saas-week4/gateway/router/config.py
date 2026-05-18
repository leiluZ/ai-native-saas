"""Router configuration"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RouterConfig:
    health_check_interval: float = 5.0
    health_check_timeout: float = 3.0

    degradation_p99_threshold_ms: float = 800.0
    degradation_consecutive_5xx: int = 3
    degradation_gpu_memory_pct: float = 95.0

    load_balance_cpu_threshold_pct: float = 80.0
    load_balance_gpu_threshold_pct: float = 80.0

    cost_monthly_cap_usd: float = 10.0
    cost_gpt4_per_1k_tokens: float = 0.03
    cost_gpt35_per_1k_tokens: float = 0.002

    vip_model: str = "gpt-4"
    default_local_model: str = "vllm-local"
    fallback_cloud_model: str = "gpt-3.5-turbo"

    switch_latency_budget_ms: float = 50.0

    metrics_port: int = 9090


router_config = RouterConfig()
