import asyncio
import time
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .kv_cache_config import KVCacheConfig, SafetyThresholds
from .vllm_lifecycle import VLLMLifecycleManager, VLLMInstance
from .prefill_adjuster import PrefillAdjuster, PrefillMetrics, PrefillAdjustment
from .gpu_scanner import get_gpu_memory_usage_pct
from .adapters import VLLMAdapter, InferenceResult
from .metrics import MetricsCalculator, BenchmarkMetrics
from .prompts import get_prompts_by_length


@dataclass
class ConfigBenchmarkResult:
    config: KVCacheConfig
    config_label: str
    round_number: int = 0
    metrics: Optional[BenchmarkMetrics] = None
    oom_count: int = 0
    gpu_memory_pct: float = 0.0
    p99_latency_s: float = 0.0
    avg_queue_depth: float = 0.0
    terminated_by_safety: bool = False
    termination_reason: str = ""
    prefill_metrics: Optional[PrefillMetrics] = None
    prefill_adjustment: Optional[PrefillAdjustment] = None
    elapsed_time_s: float = 0.0
    success: bool = False
    errors: list[str] = field(default_factory=list)


@dataclass
class TuningResult:
    config_results: list[ConfigBenchmarkResult] = field(default_factory=list)
    optimal_config: Optional[KVCacheConfig] = None
    optimal_label: str = ""
    baseline_config: Optional[KVCacheConfig] = None
    baseline_metrics: Optional[BenchmarkMetrics] = None
    total_configs_tested: int = 0
    total_rounds: int = 0
    total_time_s: float = 0.0
    gpu_info: dict = field(default_factory=dict)


class KVCacheBenchmarkRunner:
    def __init__(
        self,
        lifecycle: VLLMLifecycleManager,
        safety: SafetyThresholds,
        prefill_adjuster: PrefillAdjuster,
        rounds_per_config: int = 3,
        prompts_per_round: int = 50,
        concurrency: int = 8,
        max_tokens: int = 512,
        timeout: int = 300,
        cooldown_between_configs: float = 5.0,
    ):
        self.lifecycle = lifecycle
        self.safety = safety
        self.prefill_adjuster = prefill_adjuster
        self.rounds_per_config = rounds_per_config
        self.prompts_per_round = prompts_per_round
        self.concurrency = concurrency
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.cooldown_between_configs = cooldown_between_configs

    async def run_single_round(
        self,
        config: KVCacheConfig,
        instance: VLLMInstance,
        round_num: int,
    ) -> ConfigBenchmarkResult:
        result = ConfigBenchmarkResult(
            config=config,
            config_label=config.label(),
            round_number=round_num,
        )

        start = time.time()

        try:
            adapter = VLLMAdapter(
                base_url=instance.base_url,
                timeout=self.timeout,
                max_retries=1,
                model=instance.model,
            )

            prompts = get_prompts_by_length("all", self.prompts_per_round)
            semaphore = asyncio.Semaphore(self.concurrency)
            calculator = MetricsCalculator()

            async def worker(prompt: str, request_id: str):
                async with semaphore:
                    infer_result = await adapter.generate(prompt, request_id, self.max_tokens)
                    calculator.add_result(infer_result)
                    return infer_result

            tasks = [worker(p, f"tune_{round_num}_{i}") for i, p in enumerate(prompts)]
            await asyncio.gather(*tasks, return_exceptions=True)

            metrics = calculator.calculate()
            result.metrics = metrics

            oom_count = sum(1 for r in calculator.results if not r.success and r.error and ("OOM" in str(r.error).upper() or "OUT OF MEMORY" in str(r.error).upper()))
            result.oom_count = oom_count

            result.gpu_memory_pct = get_gpu_memory_usage_pct()
            result.p99_latency_s = metrics.e2e_latency_p99

            result.prefill_metrics = PrefillMetrics(
                avg_prefill_time_ms=metrics.ttft_mean * 1000,
                p99_prefill_time_ms=metrics.ttft_p99 * 1000,
                avg_queue_depth=0.0,
                max_queue_depth=0,
                avg_waiting_time_ms=metrics.ttft_mean * 1000,
                p99_waiting_time_ms=metrics.ttft_p99 * 1000,
                long_prompt_ratio=0.0,
            )

            if not self.safety.is_safe(result.gpu_memory_pct, result.p99_latency_s, result.oom_count):
                result.terminated_by_safety = True
                reasons = []
                if result.gpu_memory_pct > self.safety.gpu_memory_pct_max:
                    reasons.append(f"GPU memory {result.gpu_memory_pct:.1f}% > {self.safety.gpu_memory_pct_max}%")
                if result.p99_latency_s > self.safety.p99_latency_max_s:
                    reasons.append(f"P99 latency {result.p99_latency_s:.3f}s > {self.safety.p99_latency_max_s}s")
                if result.oom_count > self.safety.oom_max_per_round:
                    reasons.append(f"OOM count {result.oom_count} > {self.safety.oom_max_per_round}")
                result.termination_reason = "; ".join(reasons)
            else:
                result.success = True

        except Exception as e:
            result.errors.append(str(e))

        result.elapsed_time_s = time.time() - start
        return result

    async def run_config_rounds(
        self,
        config: KVCacheConfig,
        instance: VLLMInstance,
    ) -> list[ConfigBenchmarkResult]:
        results = []
        consecutive_ooms = 0

        for round_num in range(1, self.rounds_per_config + 1):
            round_result = await self.run_single_round(config, instance, round_num)
            results.append(round_result)

            if round_result.terminated_by_safety:
                break

            if round_result.oom_count > 0:
                consecutive_ooms += 1
                if consecutive_ooms >= self.safety.consecutive_oom_max:
                    break
            else:
                consecutive_ooms = 0

        return results

    async def run_all_configs(
        self,
        configs: list[KVCacheConfig],
        extra_vllm_args: Optional[list[str]] = None,
    ) -> TuningResult:
        tuning_result = TuningResult()
        tuning_result.total_configs_tested = len(configs)
        tuning_start = time.time()

        for i, config in enumerate(configs):
            instance = self.lifecycle.start(config, extra_vllm_args)
            ready = await self.lifecycle.wait_until_ready(instance)

            if not ready:
                failed_result = ConfigBenchmarkResult(
                    config=config,
                    config_label=config.label(),
                    errors=instance.errors or ["vLLM failed to start"],
                )
                tuning_result.config_results.append(failed_result)
                self.lifecycle.stop(instance)
                continue

            round_results = await self.run_config_rounds(config, instance)
            tuning_result.config_results.extend(round_results)
            tuning_result.total_rounds += len(round_results)

            self.lifecycle.stop(instance)

            if i < len(configs) - 1:
                await asyncio.sleep(self.cooldown_between_configs)

        tuning_result.total_time_s = time.time() - tuning_start
        return tuning_result

    def find_optimal_config(self, tuning_result: TuningResult) -> TuningResult:
        best_score = -1.0
        best_label = ""
        best_config = None

        config_aggregates: dict[str, list[ConfigBenchmarkResult]] = {}
        for r in tuning_result.config_results:
            if r.success and r.metrics is not None:
                config_aggregates.setdefault(r.config_label, []).append(r)

        for label, results in config_aggregates.items():
            if not results:
                continue

            avg_throughput = sum(r.metrics.throughput_mean for r in results) / len(results)
            avg_p99 = sum(r.metrics.e2e_latency_p99 for r in results) / len(results)
            avg_oom = sum(r.oom_count for r in results) / len(results)
            avg_gpu_mem = sum(r.gpu_memory_pct for r in results) / len(results)

            if avg_oom > 0:
                continue

            score = (
                avg_throughput * 0.4
                + (1.0 / max(avg_p99, 0.001)) * 0.3
                + (avg_gpu_mem / 100.0) * 0.2
                + (1.0 - avg_oom) * 0.1
            )

            if score > best_score:
                best_score = score
                best_label = label
                best_config = results[0].config

        tuning_result.optimal_config = best_config
        tuning_result.optimal_label = best_label
        return tuning_result
