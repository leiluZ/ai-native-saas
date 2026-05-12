import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from collections import defaultdict

from .adapters import InferenceResult


@dataclass
class BenchmarkMetrics:
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    success_rate: float = 0.0

    ttft_mean: float = 0.0
    ttft_p50: float = 0.0
    ttft_p95: float = 0.0
    ttft_p99: float = 0.0
    ttft_min: float = 0.0
    ttft_max: float = 0.0

    tpot_mean: float = 0.0
    tpot_p50: float = 0.0
    tpot_p95: float = 0.0
    tpot_p99: float = 0.0

    e2e_latency_mean: float = 0.0
    e2e_latency_p50: float = 0.0
    e2e_latency_p95: float = 0.0
    e2e_latency_p99: float = 0.0

    throughput_mean: float = 0.0
    throughput_p50: float = 0.0
    throughput_p95: float = 0.0
    throughput_p99: float = 0.0

    peak_gpu_vram: Optional[float] = None
    avg_tokens_per_request: float = 0.0
    total_tokens: int = 0

    results: List[InferenceResult] = field(default_factory=list)


class MetricsCalculator:
    def __init__(self):
        self.results: List[InferenceResult] = []
        self.peak_gpu_vram: float = 0.0

    def add_result(self, result: InferenceResult):
        self.results.append(result)

    def add_gpu_memory(self, memory_mb: float):
        if memory_mb > self.peak_gpu_vram:
            self.peak_gpu_vram = memory_mb

    def calculate(self) -> BenchmarkMetrics:
        successful = [r for r in self.results if r.success]
        failed = [r for r in self.results if not r.success]

        metrics = BenchmarkMetrics(
            total_requests=len(self.results),
            successful_requests=len(successful),
            failed_requests=len(failed),
            success_rate=len(successful) / len(self.results) if self.results else 0.0,
            peak_gpu_vram=self.peak_gpu_vram if self.peak_gpu_vram > 0 else None
        )

        if successful:
            ttfts = [r.ttft for r in successful if r.ttft > 0]
            tpots = [r.tpot for r in successful if r.tpot > 0]
            e2es = [r.e2e_latency for r in successful]
            throughputs = [r.throughput for r in successful if r.throughput > 0]
            tokens = [r.completion_tokens for r in successful]

            if ttfts:
                metrics.ttft_mean = np.mean(ttfts)
                metrics.ttft_p50 = np.percentile(ttfts, 50)
                metrics.ttft_p95 = np.percentile(ttfts, 95)
                metrics.ttft_p99 = np.percentile(ttfts, 99)
                metrics.ttft_min = np.min(ttfts)
                metrics.ttft_max = np.max(ttfts)

            if tpots:
                metrics.tpot_mean = np.mean(tpots)
                metrics.tpot_p50 = np.percentile(tpots, 50)
                metrics.tpot_p95 = np.percentile(tpots, 95)
                metrics.tpot_p99 = np.percentile(tpots, 99)

            if e2es:
                metrics.e2e_latency_mean = np.mean(e2es)
                metrics.e2e_latency_p50 = np.percentile(e2es, 50)
                metrics.e2e_latency_p95 = np.percentile(e2es, 95)
                metrics.e2e_latency_p99 = np.percentile(e2es, 99)

            if throughputs:
                metrics.throughput_mean = np.mean(throughputs)
                metrics.throughput_p50 = np.percentile(throughputs, 50)
                metrics.throughput_p95 = np.percentile(throughputs, 95)
                metrics.throughput_p99 = np.percentile(throughputs, 99)

            if tokens:
                metrics.avg_tokens_per_request = np.mean(tokens)
                metrics.total_tokens = sum(tokens)

        metrics.results = self.results
        return metrics

    def to_dataframe(self) -> pd.DataFrame:
        rows = []
        for r in self.results:
            rows.append({
                "request_id": r.request_id,
                "prompt_length": r.prompt_length,
                "completion_tokens": r.completion_tokens,
                "ttft": r.ttft,
                "tpot": r.tpot,
                "e2e_latency": r.e2e_latency,
                "throughput": r.throughput,
                "success": r.success,
                "error": r.error or "",
                "timestamp": r.timestamp
            })
        return pd.DataFrame(rows)

    def to_csv(self, filepath: str):
        df = self.to_dataframe()
        df.to_csv(filepath, index=False)
        return filepath


def calculate_percentiles(values: List[float], percentiles: List[int] = [50, 95, 99]) -> Dict[int, float]:
    if not values:
        return {p: 0.0 for p in percentiles}
    return {p: np.percentile(values, p) for p in percentiles}


def aggregate_metrics_by_prompt_length(
    results: List[InferenceResult],
    buckets: List[int] = [128, 512, 2048]
) -> Dict[str, Dict]:
    bucket_results = defaultdict(list)

    for r in results:
        if not r.success:
            continue
        length = r.prompt_length
        bucket = "long"
        if length <= 128:
            bucket = "short"
        elif length <= 512:
            bucket = "medium"
        bucket_results[bucket].append(r)

    aggregated = {}
    for bucket_name, bucket_data in bucket_results.items():
        if not bucket_data:
            continue
        ttfts = [r.ttft for r in bucket_data if r.ttft > 0]
        tpots = [r.tpot for r in bucket_data if r.tpot > 0]
        e2es = [r.e2e_latency for r in bucket_data]

        aggregated[bucket_name] = {
            "count": len(bucket_data),
            "ttft_mean": np.mean(ttfts) if ttfts else 0,
            "ttft_p50": np.percentile(ttfts, 50) if ttfts else 0,
            "ttft_p95": np.percentile(ttfts, 95) if ttfts else 0,
            "tpot_mean": np.mean(tpots) if tpots else 0,
            "tpot_p50": np.percentile(tpots, 50) if tpots else 0,
            "e2e_mean": np.mean(e2es) if e2es else 0,
            "e2e_p50": np.percentile(e2es, 50) if e2es else 0,
            "e2e_p95": np.percentile(e2es, 95) if e2es else 0,
        }

    return aggregated
