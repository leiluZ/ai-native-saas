from dataclasses import dataclass, field
from typing import Optional

from .kv_cache_config import KVCacheConfig


@dataclass
class PrefillMetrics:
    avg_prefill_time_ms: float = 0.0
    p99_prefill_time_ms: float = 0.0
    avg_queue_depth: float = 0.0
    max_queue_depth: int = 0
    avg_waiting_time_ms: float = 0.0
    p99_waiting_time_ms: float = 0.0
    long_prompt_ratio: float = 0.0


@dataclass
class PrefillAdjustment:
    enable_chunked_prefill: bool
    max_num_batched_tokens: Optional[int]
    reason: str = ""


class PrefillAdjuster:
    def __init__(
        self,
        long_prompt_threshold_tokens: int = 8192,
        prefill_time_threshold_ms: float = 500.0,
        queue_depth_threshold: int = 10,
        waiting_time_threshold_ms: float = 1000.0,
    ):
        self.long_prompt_threshold_tokens = long_prompt_threshold_tokens
        self.prefill_time_threshold_ms = prefill_time_threshold_ms
        self.queue_depth_threshold = queue_depth_threshold
        self.waiting_time_threshold_ms = waiting_time_threshold_ms

    def analyze(self, metrics: PrefillMetrics) -> PrefillAdjustment:
        needs_chunked = False
        reasons = []

        if metrics.avg_prefill_time_ms > self.prefill_time_threshold_ms:
            needs_chunked = True
            reasons.append(f"avg prefill time {metrics.avg_prefill_time_ms:.1f}ms > {self.prefill_time_threshold_ms}ms")

        if metrics.p99_prefill_time_ms > self.prefill_time_threshold_ms * 2:
            needs_chunked = True
            reasons.append(f"p99 prefill time {metrics.p99_prefill_time_ms:.1f}ms > {self.prefill_time_threshold_ms * 2}ms")

        if metrics.avg_queue_depth > self.queue_depth_threshold:
            needs_chunked = True
            reasons.append(f"avg queue depth {metrics.avg_queue_depth:.1f} > {self.queue_depth_threshold}")

        if metrics.avg_waiting_time_ms > self.waiting_time_threshold_ms:
            needs_chunked = True
            reasons.append(f"avg waiting time {metrics.avg_waiting_time_ms:.1f}ms > {self.waiting_time_threshold_ms}ms")

        if metrics.long_prompt_ratio > 0.3:
            needs_chunked = True
            reasons.append(f"long prompt ratio {metrics.long_prompt_ratio:.1%} > 30%")

        if not needs_chunked:
            return PrefillAdjustment(
                enable_chunked_prefill=False,
                max_num_batched_tokens=None,
                reason="prefill performance acceptable",
            )

        batched_tokens = self._calculate_batched_tokens(metrics)
        reason_str = "; ".join(reasons) if reasons else "default adjustment"

        return PrefillAdjustment(
            enable_chunked_prefill=True,
            max_num_batched_tokens=batched_tokens,
            reason=reason_str,
        )

    def _calculate_batched_tokens(self, metrics: PrefillMetrics) -> Optional[int]:
        if metrics.avg_prefill_time_ms > 1000:
            return 2048
        elif metrics.avg_prefill_time_ms > 500:
            return 4096
        elif metrics.avg_queue_depth > 20:
            return 4096
        elif metrics.avg_queue_depth > 10:
            return 8192
        return None

    def apply_to_config(self, config: KVCacheConfig, adjustment: PrefillAdjustment) -> KVCacheConfig:
        return KVCacheConfig(
            gpu_memory_utilization=config.gpu_memory_utilization,
            block_size=config.block_size,
            max_num_seqs=config.max_num_seqs,
            enable_chunked_prefill=adjustment.enable_chunked_prefill,
            max_num_batched_tokens=adjustment.max_num_batched_tokens,
            enable_prefix_caching=config.enable_prefix_caching,
            swap_space=config.swap_space,
            max_model_len=config.max_model_len,
        )
