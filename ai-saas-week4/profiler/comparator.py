import json
import logging
import os
from datetime import datetime
from typing import Optional

from profiler.config import ProfilerConfig, default_config
from profiler.core import ProfilingTrace, ProfileManager

logger = logging.getLogger(__name__)


class ProfileComparator:
    def __init__(self, config: Optional[ProfilerConfig] = None):
        self.config = config or default_config

    def compare(
        self,
        before_trace: ProfilingTrace,
        after_trace: ProfilingTrace,
    ) -> dict:
        metrics = {}
        for metric_name in self.config.comparison_metrics:
            before_val = self._extract_metric(before_trace, metric_name)
            after_val = self._extract_metric(after_trace, metric_name)

            if before_val > 0:
                improvement = round((after_val - before_val) / before_val * 100, 2)
                improvement_abs = after_val - before_val
                direction = "decreased" if improvement < 0 else "increased"
            else:
                improvement = 0.0
                improvement_abs = 0.0
                direction = "unchanged"

            metrics[metric_name] = {
                "before": round(before_val, 2),
                "after": round(after_val, 2),
                "change_pct": improvement,
                "change_abs": round(improvement_abs, 2),
                "direction": direction,
                "improved": (improvement < 0 and metric_name.endswith("_ms")) or
                           (improvement > 0 and metric_name.endswith("_per_sec")),
            }

        latency_improvement = self._calc_latency_improvement(before_trace, after_trace)
        throughput_improvement = self._calc_throughput_improvement(before_trace, after_trace)

        return {
            "metadata": {
                "compared_at": datetime.now().isoformat(),
                "before_events": len(before_trace.events),
                "after_events": len(after_trace.events),
            },
            "metrics": metrics,
            "summary": {
                "p99_latency_improvement_pct": latency_improvement,
                "throughput_improvement_pct": throughput_improvement,
                "overall_improvement_pct": round((latency_improvement + throughput_improvement) / 2, 2),
                "passed_latency_threshold": latency_improvement > 20.0,
                "passed_throughput_threshold": throughput_improvement > 30.0,
            },
        }

    def _extract_metric(self, trace: ProfilingTrace, metric_name: str) -> float:
        metric_map = {
            "p50_latency_ms": self._get_event_percentile(trace, 50),
            "p99_latency_ms": self._get_event_percentile(trace, 99),
            "throughput_tokens_per_sec": self._calc_throughput(trace),
            "gpu_memory_mb": trace.gpu_memory_mb,
            "cpu_time_ms": trace.total_cpu_time_us() / 1000.0,
            "cache_hit_rate": 0.0,
        }
        return metric_map.get(metric_name, 0.0)

    def _get_event_percentile(self, trace: ProfilingTrace, p: int) -> float:
        import math
        durations = sorted(e.duration_us for e in trace.events if e.duration_us > 0 and e.phase == "compute")
        if not durations:
            durations = sorted(e.duration_us for e in trace.events if e.duration_us > 0)
        if not durations:
            return 0.0

        idx = math.ceil(len(durations) * p / 100.0) - 1
        idx = max(0, min(idx, len(durations) - 1))
        return durations[idx] / 1000.0

    def _calc_throughput(self, trace: ProfilingTrace) -> float:
        total_time_s = trace.total_duration_us / 1_000_000.0
        total_tokens = len(trace.events)
        if total_time_s <= 0:
            return 0.0
        return total_tokens / total_time_s

    def _calc_latency_improvement(self, before: ProfilingTrace, after: ProfilingTrace) -> float:
        before_p99 = self._extract_metric(before, "p99_latency_ms")
        after_p99 = self._extract_metric(after, "p99_latency_ms")
        if before_p99 <= 0:
            return 0.0
        return round(abs((after_p99 - before_p99) / before_p99 * 100), 2)

    def _calc_throughput_improvement(self, before: ProfilingTrace, after: ProfilingTrace) -> float:
        before_tp = self._extract_metric(before, "throughput_tokens_per_sec")
        after_tp = self._extract_metric(after, "throughput_tokens_per_sec")
        if before_tp <= 0:
            return 0.0
        return round((after_tp - before_tp) / before_tp * 100, 2)

    def save_comparison_report(self, comparison: dict, output_path: Optional[str] = None) -> str:
        os.makedirs(self.config.output_dir, exist_ok=True)

        if output_path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(self.config.output_dir, f"comparison_report_{ts}.json")

        with open(output_path, "w") as f:
            json.dump(comparison, f, indent=2, default=str)

        logger.info(f"Comparison report saved to {output_path}")
        return output_path

    def save_markdown_comparison(self, comparison: dict, output_path: Optional[str] = None) -> str:
        os.makedirs(self.config.output_dir, exist_ok=True)

        if output_path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(self.config.output_dir, f"comparison_report_{ts}.md")

        lines = [
            "# Before/After Optimization Comparison",
            "",
            f"Compared: {comparison['metadata']['compared_at']}",
            "",
            "## Metrics Comparison",
            "",
            "| Metric | Before | After | Change | Improved? |",
            "|--------|--------|-------|--------|-----------|",
        ]

        for name, data in comparison["metrics"].items():
            icon = "✅" if data["improved"] else "❌"
            arrow = "↓" if data["change_pct"] < 0 else "↑"
            lines.append(
                f"| {name} | {data['before']:.2f} | {data['after']:.2f} | "
                f"{arrow} {abs(data['change_pct']):.2f}% | {icon} |"
            )

        s = comparison["summary"]
        lines.extend([
            "",
            "## Summary",
            "",
            f"| Indicator | Value | Passed? |",
            f"|-----------|-------|---------|",
            f"| P99 Latency Improvement | {s['p99_latency_improvement_pct']:.2f}% | {'✅' if s['passed_latency_threshold'] else '❌'} |",
            f"| Throughput Improvement | {s['throughput_improvement_pct']:.2f}% | {'✅' if s['passed_throughput_threshold'] else '❌'} |",
            f"| Overall Improvement | {s['overall_improvement_pct']:.2f}% | - |",
        ])

        if s["passed_latency_threshold"]:
            lines.extend(["", "✅ **P99 latency decreased by >20%** - Acceptance criteria met!"])
        else:
            lines.extend(["", "⚠️ P99 latency improvement below 20% threshold - further optimization needed."])

        if s["passed_throughput_threshold"]:
            lines.extend(["✅ **Throughput increased by >30%** - Acceptance criteria met!"])
        else:
            lines.extend(["⚠️ Throughput improvement below 30% threshold - further optimization needed."])

        with open(output_path, "w") as f:
            f.write("\n".join(lines))

        logger.info(f"Markdown comparison saved to {output_path}")
        return output_path

    def load_and_compare(self, before_path: str, after_path: str) -> dict:
        mgr = ProfileManager(self.config)
        before = mgr.load_trace(before_path)
        after = mgr.load_trace(after_path)
        return self.compare(before, after)


def compare_profiles(
    before_trace: ProfilingTrace,
    after_trace: ProfilingTrace,
    config: Optional[ProfilerConfig] = None,
) -> dict:
    comparator = ProfileComparator(config)
    return comparator.compare(before_trace, after_trace)
