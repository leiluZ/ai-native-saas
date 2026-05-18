import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from profiler.config import ProfilerConfig, default_config
from profiler.core import ProfilingTrace, ProfilingEvent

logger = logging.getLogger(__name__)


class BottleneckCategory(str, Enum):
    IO_INTENSIVE = "io_intensive"
    COMPUTE_INTENSIVE = "compute_intensive"
    LOCK_CONTENTION = "lock_contention"
    MEMORY_BOUND = "memory_bound"
    SERIALIZATION = "serialization"
    KERNEL_LAUNCH = "kernel_launch"
    BATCH_IMBALANCE = "batch_imbalance"
    NETWORK_BOUND = "network_bound"


@dataclass
class Bottleneck:
    rank: int
    name: str
    category: BottleneckCategory
    phase: str
    severity: float
    impact_us: float
    impact_pct: float
    detail: str
    affected_events: list[str] = field(default_factory=list)
    suggestion_text: str = ""
    code_location: str = ""
    expected_improvement: str = ""
    verification_command: str = ""


class BottleneckDetector:
    def __init__(self, config: Optional[ProfilerConfig] = None):
        self.config = config or default_config

    def detect(self, trace: ProfilingTrace) -> list[Bottleneck]:
        bottlenecks = []

        bottlenecks.extend(self._detect_slow_ops(trace))
        bottlenecks.extend(self._detect_serialization_bottleneck(trace))
        bottlenecks.extend(self._detect_kernel_launch_bottleneck(trace))
        bottlenecks.extend(self._detect_batch_imbalance(trace))
        bottlenecks.extend(self._detect_network_io_bottleneck(trace))
        bottlenecks.extend(self._detect_lock_contention(trace))

        if not bottlenecks:
            bottlenecks = self._generate_fallback_bottleneck(trace)

        bottlenecks.sort(key=lambda b: b.impact_us, reverse=True)
        for i, b in enumerate(bottlenecks[:self.config.bottleneck_top_n]):
            b.rank = i + 1
            b.suggestion_text = self._generate_suggestion(b, trace)
            b.code_location = self._suggest_code_location(b)
            b.expected_improvement = self._estimate_improvement(b)
            b.verification_command = self._generate_verification_command(b)

        return bottlenecks[:self.config.bottleneck_top_n]

    def _detect_slow_ops(self, trace: ProfilingTrace) -> list[Bottleneck]:
        results = []
        for event in trace.events[:10]:
            if event.duration_us > self.config.bottleneck_min_time_us:
                category = self._classify_bottleneck(event)
                if event.phase:
                    phase = event.phase
                else:
                    from profiler.phase_analyzer import PhaseAnalyzer
                    phase = PhaseAnalyzer(self.config).classify_phase(event)

                total = trace.total_duration_us if trace.total_duration_us > 0 else 1
                impact = event.duration_us * event.call_count
                results.append(Bottleneck(
                    rank=0,
                    name=event.name,
                    category=category,
                    phase=phase,
                    severity=self._calculate_severity(impact, total),
                    impact_us=impact,
                    impact_pct=round(impact / total * 100, 2),
                    detail=f"Operation '{event.name}' consumes {impact:.1f}us ({impact/total*100:.1f}%) of total time with {event.call_count} calls. "
                           f"CPU time: {event.cpu_time_us:.1f}us, CUDA time: {event.cuda_time_us:.1f}us.",
                    affected_events=[event.name],
                ))
        return results

    def _detect_serialization_bottleneck(self, trace: ProfilingTrace) -> list[Bottleneck]:
        serial_events = [e for e in trace.events if e.phase == "serialization"]
        total_serial = sum(e.cpu_time_us for e in serial_events)

        if total_serial > self.config.bottleneck_min_time_us:
            total = trace.total_duration_us if trace.total_duration_us > 0 else 1
            return [Bottleneck(
                rank=0,
                name="CPU Serialization/Deserialization Blocking",
                category=BottleneckCategory.IO_INTENSIVE,
                phase="serialization",
                severity=self._calculate_severity(total_serial, total),
                impact_us=total_serial,
                impact_pct=round(total_serial / total * 100, 2),
                detail="JSON serialization/deserialization is blocking the request pipeline. Each request spends significant time in encode/decode operations before reaching the inference engine.",
                affected_events=[e.name for e in serial_events[:5]],
            )]
        return []

    def _detect_kernel_launch_bottleneck(self, trace: ProfilingTrace) -> list[Bottleneck]:
        kernel_events = [e for e in trace.events if e.phase in ("kernel",) and e.device == "gpu"]
        total_cuda = sum(e.cuda_time_us for e in kernel_events)

        if total_cuda > self.config.bottleneck_min_time_us:
            total = trace.total_duration_us if trace.total_duration_us > 0 else 1
            return [Bottleneck(
                rank=0,
                name="CUDA Kernel Launch Delay",
                category=BottleneckCategory.KERNEL_LAUNCH,
                phase="decode",
                severity=self._calculate_severity(total_cuda, total),
                impact_us=total_cuda,
                impact_pct=round(total_cuda / total * 100, 2),
                detail="GPU kernel launch overhead is significant. Multiple small kernel launches create cumulative scheduling delays on the CUDA stream.",
                affected_events=[e.name for e in kernel_events[:5]],
            )]
        return []

    def _detect_batch_imbalance(self, trace: ProfilingTrace) -> list[Bottleneck]:
        compute_events = [e for e in trace.events if e.phase == "compute"]
        if len(compute_events) < 2:
            return []

        times = [e.duration_us for e in compute_events]
        if not times:
            return []

        avg = sum(times) / len(times)
        max_time = max(times)
        cv = (sum((t - avg) ** 2 for t in times) / len(times)) ** 0.5 / avg if avg > 0 else 0

        if cv > 0.5:
            total = trace.total_duration_us if trace.total_duration_us > 0 else 1
            imbalance_us = max_time - avg
            return [Bottleneck(
                rank=0,
                name="Batch Size Imbalance",
                category=BottleneckCategory.BATCH_IMBALANCE,
                phase="compute",
                severity=min(cv / 2, 1.0),
                impact_us=imbalance_us,
                impact_pct=round(imbalance_us / total * 100, 2),
                detail=f"Compute operations show high variance (CV={cv:.2f}). Some batches are significantly larger than average, causing straggler delays. "
                       f"Max time: {max_time:.1f}us, Avg: {avg:.1f}us.",
                affected_events=[e.name for e in compute_events[:5]],
            )]
        return []

    def _detect_network_io_bottleneck(self, trace: ProfilingTrace) -> list[Bottleneck]:
        net_events = [e for e in trace.events if e.phase == "network_io"]
        total_net = sum(e.cpu_time_us for e in net_events)

        if total_net > self.config.bottleneck_min_time_us:
            total = trace.total_duration_us if trace.total_duration_us > 0 else 1
            return [Bottleneck(
                rank=0,
                name="Network I/O Contention",
                category=BottleneckCategory.NETWORK_BOUND,
                phase="network_io",
                severity=self._calculate_severity(total_net, total),
                impact_us=total_net,
                impact_pct=round(total_net / total * 100, 2),
                detail="Network I/O is a significant bottleneck, especially in streaming response paths. Multiple concurrent SSE connections create connection pool pressure.",
                affected_events=[e.name for e in net_events[:5]],
            )]
        return []

    def _detect_lock_contention(self, trace: ProfilingTrace) -> list[Bottleneck]:
        lock_events = [e for e in trace.events if e.phase == "lock_contention"]
        total_lock = sum(e.cpu_time_us for e in lock_events)

        if total_lock > self.config.bottleneck_min_time_us:
            total = trace.total_duration_us if trace.total_duration_us > 0 else 1
            return [Bottleneck(
                rank=0,
                name="Lock Contention in Concurrent Access",
                category=BottleneckCategory.LOCK_CONTENTION,
                phase="lock_contention",
                severity=self._calculate_severity(total_lock, total),
                impact_us=total_lock,
                impact_pct=round(total_lock / total * 100, 2),
                detail="Asyncio lock contention detected during concurrent request handling. Cost tracker and health checker share locks, creating serialization under high concurrency.",
                affected_events=[e.name for e in lock_events[:5]],
            )]
        return []

    def _classify_bottleneck(self, event: ProfilingEvent) -> BottleneckCategory:
        name_lower = event.name.lower()

        if any(kw in name_lower for kw in ["serial", "json", "encode", "decode", "marshal"]):
            return BottleneckCategory.SERIALIZATION
        if any(kw in name_lower for kw in ["kernel", "cuda", "launch"]):
            return BottleneckCategory.KERNEL_LAUNCH
        if any(kw in name_lower for kw in ["lock", "mutex", "semaphore"]):
            return BottleneckCategory.LOCK_CONTENTION
        if any(kw in name_lower for kw in ["io", "memcpy", "h2d", "d2h"]):
            return BottleneckCategory.IO_INTENSIVE
        if any(kw in name_lower for kw in ["network", "http", "socket", "send", "recv"]):
            return BottleneckCategory.NETWORK_BOUND
        if any(kw in name_lower for kw in ["memory", "alloc", "cache"]):
            return BottleneckCategory.MEMORY_BOUND

        return BottleneckCategory.COMPUTE_INTENSIVE

    def _calculate_severity(self, impact_us: float, total_us: float) -> float:
        if total_us <= 0:
            return 0.5
        pct = impact_us / total_us
        return min(pct * 10, 1.0)

    def _generate_fallback_bottleneck(self, trace: ProfilingTrace) -> list[Bottleneck]:
        return [
            Bottleneck(
                rank=1,
                name="Insufficient Profiling Data",
                category=BottleneckCategory.COMPUTE_INTENSIVE,
                phase="compute",
                severity=0.3,
                impact_us=0.0,
                impact_pct=0.0,
                detail="Not enough data collected for bottleneck analysis. Consider increasing profiling duration or enabling more detailed tracing.",
            )
        ]

    def _generate_suggestion(self, bottleneck: Bottleneck, trace: ProfilingTrace) -> str:
        suggestions = {
            BottleneckCategory.SERIALIZATION:
                "Replace json.dumps/json.loads with orjson for 3-5x faster serialization. "
                "Use streaming JSON parsing for large payloads. Consider moving serialization to a separate thread pool.",
            BottleneckCategory.KERNEL_LAUNCH:
                "Use CUDA Graph capture to eliminate repeated kernel launch overhead. "
                "Increase batch sizes to amortize launch costs. Enable CUDA_LAUNCH_BLOCKING=0 for async launches.",
            BottleneckCategory.BATCH_IMBALANCE:
                "Implement dynamic batching with max_batch_size constraint. "
                "Add batch padding to equalize sizes. Use continuous batching to smooth workload distribution.",
            BottleneckCategory.NETWORK_BOUND:
                "Increase HTTP connection pool limits (httpx.AsyncClient limits). "
                "Use connection keep-alive strategically. Consider gRPC for internal service communication.",
            BottleneckCategory.LOCK_CONTENTION:
                "Replace asyncio.Lock with asyncio.Semaphore for reader-writer patterns. "
                "Use lock-free data structures (uvloop-friendly). Shard cost tracker by user for reduced contention.",
            BottleneckCategory.MEMORY_BOUND:
                "Enable PagedAttention KV Cache with block_size=16. "
                "Pre-allocate memory pools instead of per-request allocations.",
            BottleneckCategory.IO_INTENSIVE:
                "Use memory-mapped I/O for large files. Implement async I/O with aiofiles. "
                "Add prefetching buffer for sequential access patterns.",
            BottleneckCategory.COMPUTE_INTENSIVE:
                "Profile specific compute kernels with Nsight Compute. "
                "Consider quantized inference (AWQ/INT8) to reduce compute requirements.",
        }
        return suggestions.get(bottleneck.category, "General optimization: profile the hot path and reduce unnecessary computation.")

    def _suggest_code_location(self, bottleneck: Bottleneck) -> str:
        locations = {
            BottleneckCategory.SERIALIZATION:
                "gateway/proxy.py:_build_headers() and gateway/routes/chat.py:body parsing",
            BottleneckCategory.KERNEL_LAUNCH:
                "benchmark/adapters.py:vLLMAdapter (decoder layer forward calls)",
            BottleneckCategory.BATCH_IMBALANCE:
                "benchmark/kv_cache_runner.py:run_benchmark_round() batch assembly",
            BottleneckCategory.NETWORK_BOUND:
                "gateway/proxy.py:_stream_request() and gateway/routes/chat.py:_stream_with_router()",
            BottleneckCategory.LOCK_CONTENTION:
                "gateway/router/cost_tracker.py:record_usage() and gateway/router/health_checker.py:probe()",
            BottleneckCategory.MEMORY_BOUND:
                "benchmark/kv_cache_config.py:block_size and gpu_memory_utilization params",
            BottleneckCategory.IO_INTENSIVE:
                "gateway/routes/chat.py:_estimate_tokens() and gateway/proxy.py:_retry_with_backoff()",
            BottleneckCategory.COMPUTE_INTENSIVE:
                "benchmark/metrics.py:compute_metrics() aggregation",
        }
        return locations.get(bottleneck.category, "unknown - run profiler with --with-stack for stack traces")

    def _estimate_improvement(self, bottleneck: Bottleneck) -> str:
        estimates = {
            BottleneckCategory.SERIALIZATION: "20-35% latency reduction in request parsing",
            BottleneckCategory.KERNEL_LAUNCH: "15-25% reduction in per-step GPU overhead",
            BottleneckCategory.BATCH_IMBALANCE: "10-20% improvement in batch throughput consistency",
            BottleneckCategory.NETWORK_BOUND: "25-40% reduction in streaming overhead",
            BottleneckCategory.LOCK_CONTENTION: "15-30% improvement under high concurrency (>50 req/s)",
            BottleneckCategory.MEMORY_BOUND: "30-50% more concurrent requests",
            BottleneckCategory.IO_INTENSIVE: "10-20% reduction in I/O wait time",
            BottleneckCategory.COMPUTE_INTENSIVE: "5-15% reduction through quantization",
        }
        return estimates.get(bottleneck.category, "Unknown improvement potential")

    def _generate_verification_command(self, bottleneck: Bottleneck) -> str:
        phase = bottleneck.phase
        return (
            f"python -m profiler.main --target {bottleneck.category.value} "
            f"--before-profile {bottleneck.name[:30]} "
            f"--verify-improvement --threshold {max(5.0, bottleneck.impact_pct)}"
        )

    def generate_bottleneck_report(self, trace: ProfilingTrace, bottlenecks: list[Bottleneck]) -> str:
        lines = [
            "=" * 70,
            "  Bottleneck Analysis Report",
            "=" * 70,
            "",
            f"  Profile Duration: {trace.total_duration_us:.1f} us ({trace.total_duration_us/1000:.2f} ms)",
            f"  Events Analyzed: {len(trace.events)}",
            f"  Bottlenecks Found: {len(bottlenecks)}",
            "",
        ]

        for b in bottlenecks:
            lines.extend([
                f"  --- Bottleneck #{b.rank} ---",
                f"  Name:        {b.name}",
                f"  Category:    {b.category.value}",
                f"  Phase:       {b.phase}",
                f"  Severity:    {b.severity * 100:.0f}%",
                f"  Impact:      {b.impact_us:.1f}us ({b.impact_pct:.1f}%)",
                f"  Detail:      {b.detail}",
                f"  Code:        {b.code_location}",
                f"  Suggestion:  {b.suggestion_text}",
                f"  Expected:    {b.expected_improvement}",
                f"  Verify:      {b.verification_command}",
                "",
            ])

        lines.append("=" * 70)
        return "\n".join(lines)


def detect_bottlenecks(
    trace: ProfilingTrace,
    top_n: Optional[int] = None,
    config: Optional[ProfilerConfig] = None,
) -> list[Bottleneck]:
    cfg = config or ProfilerConfig()
    if top_n:
        cfg.bottleneck_top_n = top_n

    detector = BottleneckDetector(cfg)
    return detector.detect(trace)
