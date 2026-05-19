import logging
from typing import Optional

from profiler.config import ProfilerConfig, default_config
from profiler.core import ProfilingTrace, ProfilingEvent

logger = logging.getLogger(__name__)


class PhaseAnalyzer:
    def __init__(self, config: Optional[ProfilerConfig] = None):
        self.config = config or default_config

    def classify_phase(self, event: ProfilingEvent) -> str:
        name_lower = event.name.lower()

        if any(kw in name_lower for kw in ["prefill", "prompt", "forward", "embed"]):
            return "prefill"
        if any(kw in name_lower for kw in ["decode", "generate", "sampling", "softmax", "lm_head"]):
            return "decode"
        if any(kw in name_lower for kw in ["kv_cache", "cache", "paged_attention", "block_table", "alloc", "free"]):
            return "kv_cache_alloc"
        if any(kw in name_lower for kw in ["network", "send", "recv", "http", "socket", "stream", "response", "request"]):
            return "network_io"
        if any(kw in name_lower for kw in ["serialize", "deserialize", "json", "pickle", "marshal"]):
            return "serialization"
        if any(kw in name_lower for kw in ["kernel", "cuda", "launch", "memcpy", "h2d", "d2h"]):
            return "kernel"
        if any(kw in name_lower for kw in ["lock", "mutex", "semaphore", "barrier", "sync"]):
            return "lock_contention"
        if any(kw in name_lower for kw in ["disk", "file", "read", "write", "io", "load"]):
            return "io_intensive"

        return "compute"

    def analyze_phases(self, trace: ProfilingTrace) -> ProfilingTrace:
        phase_times = {
            "prefill": 0.0,
            "decode": 0.0,
            "kv_cache_alloc": 0.0,
            "network_io": 0.0,
            "serialization": 0.0,
            "kernel": 0.0,
            "lock_contention": 0.0,
            "io_intensive": 0.0,
            "compute": 0.0,
        }
        phase_counts = {k: 0 for k in phase_times}

        for event in trace.events:
            phase = self.classify_phase(event)
            event.phase = phase
            phase_times[phase] += event.duration_us
            phase_counts[phase] += event.call_count

        total = sum(phase_times.values())
        breakdown = {}
        for phase, time_us in sorted(phase_times.items(), key=lambda x: x[1], reverse=True):
            if total > 0:
                breakdown[phase] = {
                    "time_us": round(time_us, 2),
                    "percentage": round(time_us / total * 100, 2),
                    "call_count": phase_counts[phase],
                }

        trace.phase_breakdown = breakdown
        trace.metadata["phase_analysis"] = {"total_us": round(total, 2), "phase_count": len([p for p in breakdown if breakdown[p]["time_us"] > 0])}
        return trace

    def get_phase_distribution(self, trace: ProfilingTrace) -> dict:
        if not trace.phase_breakdown:
            self.analyze_phases(trace)
        return trace.phase_breakdown

    def generate_phase_report(self, trace: ProfilingTrace) -> str:
        breakdown = self.get_phase_distribution(trace)
        total = trace.metadata.get("phase_analysis", {}).get("total_us", trace.total_duration_us)

        lines = [
            "=" * 60,
            "  Phase Distribution Report",
            "=" * 60,
            "",
            f"  Total Profile Duration: {total:.1f} us ({total / 1000:.2f} ms)",
            f"  Total Events: {len(trace.events)}",
            "",
            "  Phase Breakdown:",
            "  " + "-" * 56,
            f"  {'Phase':<20s} {'Time (us)':>12s} {'%':>8s} {'Calls':>8s}",
            "  " + "-" * 56,
        ]

        for phase, data in breakdown.items():
            if data["time_us"] > 0:
                bar_len = int(data["percentage"] / 2)
                bar = "█" * bar_len
                lines.append(
                    f"  {phase:<20s} {data['time_us']:>10.1f}  {data['percentage']:>5.1f}%  {data['call_count']:>6d}  {bar}"
                )

        lines.append("  " + "-" * 56)
        lines.append("")
        return "\n".join(lines)


def analyze_phases(trace: ProfilingTrace, config: Optional[ProfilerConfig] = None) -> ProfilingTrace:
    analyzer = PhaseAnalyzer(config)
    return analyzer.analyze_phases(trace)
