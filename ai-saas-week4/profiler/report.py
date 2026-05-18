import json
import logging
import os
import time
from datetime import datetime
from typing import Optional

from profiler.config import ProfilerConfig, default_config
from profiler.core import ProfilingTrace
from profiler.flame_graph import FlameGraphGenerator
from profiler.phase_analyzer import PhaseAnalyzer
from profiler.bottleneck import Bottleneck, BottleneckDetector
from profiler.llm_analyzer import LLMAnalyzer

logger = logging.getLogger(__name__)


class ProfilingReportGenerator:
    def __init__(self, config: Optional[ProfilerConfig] = None):
        self.config = config or default_config

    def generate_full_report(self, trace: ProfilingTrace) -> dict:
        phase_analyzer = PhaseAnalyzer(self.config)
        phase_analyzer.analyze_phases(trace)

        detector = BottleneckDetector(self.config)
        bottlenecks = detector.detect(trace)

        llm_analyzer = LLMAnalyzer(self.config)
        llm_report = llm_analyzer.generate_natural_language_report(trace, bottlenecks, output_path=None)

        flame_gen = FlameGraphGenerator(self.config)
        flame_data = flame_gen.generate_flame_graph_data(trace)

        report = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "profiler_version": "1.0.0",
                "config": {
                    "output_dir": self.config.output_dir,
                    "nsys_enabled": self.config.nsys_enabled,
                    "llm_enabled": self.config.llm_enabled,
                },
            },
            "summary": {
                "total_duration_us": trace.total_duration_us,
                "total_duration_ms": round(trace.total_duration_us / 1000, 2),
                "total_events": len(trace.events),
                "unique_ops": trace.unique_ops(),
                "total_cpu_time_us": trace.total_cpu_time_us(),
                "total_cuda_time_us": trace.total_cuda_time_us(),
                "gpu_memory_mb": trace.gpu_memory_mb,
                "gpu_utilization_pct": trace.gpu_utilization_pct,
            },
            "phase_distribution": trace.phase_breakdown,
            "bottlenecks": [
                {
                    "rank": b.rank,
                    "name": b.name,
                    "category": b.category.value,
                    "phase": b.phase,
                    "severity": round(b.severity, 4),
                    "impact_us": round(b.impact_us, 2),
                    "impact_pct": round(b.impact_pct, 2),
                    "detail": b.detail,
                    "suggestion": b.suggestion_text,
                    "code_location": b.code_location,
                    "expected_improvement": b.expected_improvement,
                    "verification_command": b.verification_command,
                    "affected_events": b.affected_events[:10],
                }
                for b in bottlenecks
            ],
            "natural_language_analysis": llm_report,
            "flame_graph_data": flame_data,
            "top_operations": [
                {
                    "rank": i + 1,
                    "name": e.name,
                    "category": e.category,
                    "phase": e.phase,
                    "cpu_time_us": e.cpu_time_us,
                    "cuda_time_us": e.cuda_time_us,
                    "self_cpu_time_us": e.self_cpu_time_us,
                    "call_count": e.call_count,
                    "device": e.device,
                }
                for i, e in enumerate(trace.events[:30])
            ],
        }

        return report

    def save_report(self, report: dict, output_path: Optional[str] = None) -> str:
        os.makedirs(self.config.output_dir, exist_ok=True)

        if output_path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(self.config.output_dir, f"profiling_report_{ts}.json")

        with open(output_path, "w") as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"Full profiling report saved to {output_path}")

        md_path = output_path.replace(".json", ".md")
        self.save_markdown_report(report, md_path)

        return output_path

    def save_markdown_report(self, report: dict, output_path: str) -> str:
        lines = [
            f"# Profiling Report",
            f"",
            f"Generated: {report['metadata']['generated_at']}",
            f"",
            f"## Summary",
            f"",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total Duration | {report['summary']['total_duration_ms']:.2f} ms |",
            f"| Total Events | {report['summary']['total_events']} |",
            f"| Unique Operations | {report['summary']['unique_ops']} |",
            f"| CPU Time | {report['summary']['total_cpu_time_us']:.1f} us |",
            f"| CUDA Time | {report['summary']['total_cuda_time_us']:.1f} us |",
            f"| GPU Memory | {report['summary']['gpu_memory_mb']:.0f} MB |",
            f"",
            f"## Phase Distribution",
            f"",
            f"| Phase | Time (us) | % | Calls |",
            f"|-------|-----------|------|-------|",
        ]

        for phase, data in report.get("phase_distribution", {}).items():
            if data["time_us"] > 0:
                lines.append(f"| {phase} | {data['time_us']:.1f} | {data['percentage']:.1f}% | {data['call_count']} |")

        if report.get("bottlenecks"):
            lines.append("")
            lines.append("## Detected Bottlenecks")
            lines.append("")
            for b in report["bottlenecks"]:
                lines.append(f"### #{b['rank']} {b['name']}")
                lines.append(f"- **Category**: {b['category']}")
                lines.append(f"- **Phase**: {b['phase']}")
                lines.append(f"- **Severity**: {b['severity']*100:.0f}%")
                lines.append(f"- **Impact**: {b['impact_us']:.1f}us ({b['impact_pct']:.1f}%)")
                lines.append(f"- **Detail**: {b['detail']}")
                lines.append(f"- **Code Location**: `{b['code_location']}`")
                lines.append(f"- **Suggestion**: {b['suggestion']}")
                lines.append(f"- **Expected Improvement**: {b['expected_improvement']}")
                lines.append("")

        lines.append("")
        lines.append("## Natural Language Analysis")
        lines.append("")
        lines.append(report.get("natural_language_analysis", ""))

        with open(output_path, "w") as f:
            f.write("\n".join(lines))

        logger.info(f"Markdown report saved to {output_path}")
        return output_path

    def generate_and_save_all(self, trace: ProfilingTrace) -> dict:
        report = self.generate_full_report(trace)

        os.makedirs(self.config.output_dir, exist_ok=True)

        flame_gen = FlameGraphGenerator(self.config)
        flame_gen.generate_flame_graph_html(trace)
        flame_gen.generate_flame_graph_svg(trace)

        self.save_report(report)

        phase_analyzer = PhaseAnalyzer(self.config)
        phase_report = phase_analyzer.generate_phase_report(trace)
        with open(os.path.join(self.config.output_dir, "phase_report.txt"), "w") as f:
            f.write(phase_report)

        detector = BottleneckDetector(self.config)
        bottlenecks = detector.detect(trace)
        bottleneck_report = detector.generate_bottleneck_report(trace, bottlenecks)
        with open(os.path.join(self.config.output_dir, "bottleneck_report.txt"), "w") as f:
            f.write(bottleneck_report)

        logger.info(f"All reports generated in {self.config.output_dir}")
        return report


def generate_report(trace: ProfilingTrace, config: Optional[ProfilerConfig] = None) -> dict:
    generator = ProfilingReportGenerator(config)
    return generator.generate_and_save_all(trace)
