import json
import logging
import re
from typing import Optional

import httpx

from profiler.config import ProfilerConfig, default_config
from profiler.core import ProfilingTrace, ProfilingEvent
from profiler.bottleneck import Bottleneck, BottleneckDetector

logger = logging.getLogger(__name__)


class LLMAnalyzer:
    def __init__(self, config: Optional[ProfilerConfig] = None):
        self.config = config or default_config

    def is_available(self) -> bool:
        return self.config.llm_enabled

    def analyze_logs(
        self,
        trace: ProfilingTrace,
        bottlenecks: list[Bottleneck],
        log_file: Optional[str] = None,
    ) -> str:
        if not self.config.llm_enabled:
            return self._generate_local_analysis(trace, bottlenecks)

        context = self._build_analysis_context(trace, bottlenecks, log_file)

        try:
            response = self._call_llm(context)
            return response
        except Exception as e:
            logger.warning(f"LLM analysis failed: {e}. Falling back to local analysis.")
            return self._generate_local_analysis(trace, bottlenecks)

    def _build_analysis_context(
        self,
        trace: ProfilingTrace,
        bottlenecks: list[Bottleneck],
        log_file: Optional[str],
    ) -> str:
        parts = [
            "You are a performance engineering expert. Analyze the following profiling data and generate optimization suggestions.",
            "",
            "## Profiling Trace Summary",
            f"- Total Duration: {trace.total_duration_us:.1f} us",
            f"- Total Events: {len(trace.events)}",
            f"- Phase Breakdown:",
        ]

        if trace.phase_breakdown:
            for phase, data in trace.phase_breakdown.items():
                if data["time_us"] > 0:
                    parts.append(f"  - {phase}: {data['time_us']:.1f}us ({data['percentage']:.1f}%)")

        if bottlenecks:
            parts.append("")
            parts.append("## Detected Bottlenecks")
            for b in bottlenecks:
                parts.append(f"### Bottleneck #{b.rank}: {b.name}")
                parts.append(f"- Category: {b.category.value}")
                parts.append(f"- Phase: {b.phase}")
                parts.append(f"- Impact: {b.impact_us:.1f}us ({b.impact_pct:.1f}%)")
                parts.append(f"- Detail: {b.detail}")
                parts.append(f"- Affected Events: {', '.join(b.affected_events[:5])}")
                parts.append("")

        parts.append("")
        parts.append("## Top 15 Operations by CPU Time")
        for e in trace.events[:15]:
            parts.append(f"- {e.name}: cpu={e.cpu_time_us:.1f}us, cuda={e.cuda_time_us:.1f}us, calls={e.call_count}, phase={e.phase}")

        parts.append("")
        parts.append("Please provide:")
        parts.append("1. Natural language summary of the 3 most critical bottlenecks")
        parts.append("2. Specific code-level optimization suggestions with expected impact")
        parts.append("3. Priority-ordered action plan for the engineering team")

        return "\n".join(parts)

    async def _call_llm(self, context: str) -> str:
        messages = [
            {"role": "system", "content": "You are a performance engineering expert specializing in GPU inference optimization."},
            {"role": "user", "content": context},
        ]

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.config.llm_endpoint}/v1/chat/completions",
                headers={"Content-Type": "application/json"},
                json={
                    "model": self.config.llm_model,
                    "messages": messages,
                    "max_tokens": 2048,
                    "temperature": 0.3,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    def _call_llm_sync(self, context: str) -> str:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()
            return loop.run_until_complete(self._call_llm(context))
        except RuntimeError:
            return asyncio.run(self._call_llm(context))

    def _generate_local_analysis(self, trace: ProfilingTrace, bottlenecks: list[Bottleneck]) -> str:
        parts = [
            "# Performance Optimization Analysis",
            "",
            "## Executive Summary",
            "",
            f"The profiling session captured {len(trace.events)} unique operations over "
            f"{trace.total_duration_us / 1000:.2f}ms of execution time.",
            "",
        ]

        if not bottlenecks:
            parts.append("No significant bottlenecks were detected. The system is operating within expected parameters.")
            return "\n".join(parts)

        parts.append("## Bottleneck Analysis")
        parts.append("")

        for b in bottlenecks:
            severity_label = (
                "CRITICAL" if b.severity > 0.7 else
                "HIGH" if b.severity > 0.4 else
                "MEDIUM"
            )
            parts.append(f"### {b.rank}. [{severity_label}] {b.name}")
            parts.append("")
            parts.append(f"**Category**: {b.category.value}")
            parts.append(f"**Phase**: {b.phase}")
            parts.append(f"**Impact**: {b.impact_us:.1f}us ({b.impact_pct:.1f}% of total)")
            parts.append("")
            parts.append(f"**Detail**: {b.detail}")
            parts.append("")
            parts.append("**Optimization Strategy**:")
            parts.append(b.suggestion_text)
            parts.append("")
            parts.append(f"**Affected Code**: `{b.code_location}`")
            parts.append(f"**Expected Improvement**: {b.expected_improvement}")
            parts.append(f"**Verification**: `{b.verification_command}`")
            parts.append("")

        parts.append("---")
        parts.append("")
        parts.append("## Priority-Ordered Action Plan")
        parts.append("")

        for b in bottlenecks:
            parts.append(f"{b.rank}. **{b.name}** - {b.expected_improvement}")
            parts.append(f"   - Modify: `{b.code_location}`")
            parts.append(f"   - Action: {b.suggestion_text[:120]}...")
            parts.append("")

        parts.append("## Next Steps")
        parts.append("")
        parts.append("1. Profile after each optimization to measure actual improvement")
        parts.append("2. Use the `--compare` flag to generate before/after comparison reports")
        parts.append("3. Monitor Prometheus metrics for latency/throughput trends in production")
        parts.append("4. Re-run profiling weekly to catch regressions early")

        return "\n".join(parts)

    def generate_natural_language_report(
        self,
        trace: ProfilingTrace,
        bottlenecks: list[Bottleneck],
        output_path: Optional[str],
    ) -> str:
        report = self.analyze_logs(trace, bottlenecks)

        if output_path:
            with open(output_path, "w") as f:
                f.write(report)
            logger.info(f"Natural language report saved to {output_path}")

        return report


def analyze_with_llm(
    trace: ProfilingTrace,
    bottlenecks: list[Bottleneck],
    config: Optional[ProfilerConfig] = None,
    output_path: Optional[str] = None,
) -> str:
    analyzer = LLMAnalyzer(config)
    return analyzer.generate_natural_language_report(trace, bottlenecks, output_path)
