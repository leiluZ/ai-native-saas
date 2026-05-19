"""Automated Profiling & Bottleneck Analysis Pipeline

Usage:
    python -m profiler.main --target gateway --duration 60
    python -m profiler.main --target benchmark --compare
    python -m profiler.main --one-click-start
    python -m profiler.main --one-click-stop
"""

import argparse
import logging
import sys

from profiler.config import ProfilerConfig, default_config
from profiler.core import ProfileManager, ProfilingTrace
from profiler.runner import ProfilingRunner, OneClickProfiler
from profiler.report import ProfilingReportGenerator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def _make_target_fn(target: str, config: ProfilerConfig):
    if target == "gateway":
        def gateway_workload():
            import json
            data = {
                "model": "vllm-local",
                "messages": [{"role": "user", "content": "Hello, how are you?"}],
                "temperature": 0.7,
                "max_tokens": 128,
                "stream": False,
            }
            for _ in range(10):
                json.dumps(data)
                json.loads(json.dumps(data))
        return gateway_workload

    elif target == "benchmark":
        def benchmark_workload():
            from benchmark.metrics import compute_metrics
            from benchmark.adapters import InferenceResult

            results = []
            for i in range(20):
                results.append(InferenceResult(
                    request_id=f"req_{i}",
                    prompt_tokens=50 + i * 5,
                    completion_tokens=100 + i * 10,
                    ttft=0.3 + i * 0.02,
                    tpot=0.01 + i * 0.001,
                    e2e_latency=1.0 + i * 0.2,
                    total_tokens=150 + i * 15,
                    throughput=50.0 + i * 3,
                    success=True,
                    prompt_length=200 + i * 30,
                    completion_length=100 + i * 10,
                    timestamp=1000.0 + i * 5,
                ))
            compute_metrics(results)
        return benchmark_workload

    elif target == "proxy":
        def proxy_workload():
            import asyncio
            import httpx

            async def _do():
                async with httpx.AsyncClient() as client:
                    for _ in range(5):
                        await client.get("http://localhost:8000/health")
            try:
                asyncio.run(_do())
            except Exception:
                pass
        return proxy_workload

    elif target == "memory":
        def memory_workload():
            data = bytearray(1024 * 1024 * 10)
            for i in range(0, len(data), 4096):
                data[i] = i % 256
            result = sum(data)
        return memory_workload

    else:
        def compute_workload():
            total = 0.0
            for i in range(100000):
                total += (i ** 0.5) * (i % 7)
        return compute_workload


def main():
    parser = argparse.ArgumentParser(
        description="Automated Profiling & Bottleneck Analysis Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--target", "-t",
        default="compute",
        choices=["gateway", "benchmark", "proxy", "memory", "compute"],
        help="Profiling target",
    )
    parser.add_argument(
        "--duration", "-d",
        type=int,
        default=10,
        help="Profile duration in seconds (default: 10)",
    )
    parser.add_argument(
        "--output-dir", "-o",
        default="profiling_results",
        help="Output directory for profiling results",
    )
    parser.add_argument(
        "--steps", "-s",
        type=int,
        default=10,
        help="Number of profiling steps",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Generate before/after comparison report",
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Use LLM for natural language analysis",
    )
    parser.add_argument(
        "--one-click-start",
        action="store_true",
        help="Start profiling as a background process",
    )
    parser.add_argument(
        "--one-click-stop",
        action="store_true",
        help="Stop profiling and archive results",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Check profiling status",
    )

    args = parser.parse_args()

    config = ProfilerConfig(
        output_dir=args.output_dir,
        active_steps=args.steps,
        llm_enabled=args.llm,
    )

    if args.one_click_start:
        ocp = OneClickProfiler(config)
        result = ocp.start_profile(args.target, args.duration)
        print(f"Profiling started. Status file: {result}")
        return

    if args.one_click_stop:
        ocp = OneClickProfiler(config)
        result = ocp.stop_profile()
        print(f"Profiling stopped. Results archived to: {result}")
        return

    if args.status:
        ocp = OneClickProfiler(config)
        status = ocp.status()
        print(f"Profiler status: {status}")
        return

    runner = ProfilingRunner(config)
    fn = _make_target_fn(args.target, config)

    if args.compare:
        print(f"\n{'='*60}")
        print(f"  Running full profiling pipeline for: {args.target}")
        print(f"{'='*60}\n")

        results = runner.run_full_pipeline(
            fn_before=fn,
            fn_after=fn,
            num_steps=args.steps,
        )

        comparison = results["comparison"]
        s = comparison["summary"]
        print(f"\n{'='*60}")
        print(f"  Comparison Results")
        print(f"{'='*60}")
        print(f"  P99 Latency Improvement:   {s['p99_latency_improvement_pct']:.2f}% {'✅' if s['passed_latency_threshold'] else '❌'}")
        print(f"  Throughput Improvement:    {s['throughput_improvement_pct']:.2f}% {'✅' if s['passed_throughput_threshold'] else '❌'}")
        print(f"  Overall Improvement:       {s['overall_improvement_pct']:.2f}%")
        print(f"{'='*60}\n")
        print(f"  Output files in: {config.output_dir}")
        for f in runner.get_output_files():
            print(f"    - {f}")
    else:
        print(f"\n{'='*60}")
        print(f"  Running profile for: {args.target}")
        print(f"{'='*60}\n")

        trace = runner.run_before_profile(fn, num_steps=args.steps)
        report = runner.generate_before_reports()

        print(f"\n{'='*60}")
        print(f"  Profile Summary")
        print(f"{'='*60}")
        print(f"  Duration: {trace.total_duration_us:.1f} us")
        print(f"  Events:   {len(trace.events)}")
        print(f"  Bottlenecks detected: {len(report.get('bottlenecks', []))}")

        for b in report.get("bottlenecks", []):
            print(f"    #{b['rank']} {b['name']} - {b['impact_pct']:.1f}% impact")

        print(f"{'='*60}\n")
        print(f"  Output files in: {config.output_dir}")
        for f in runner.get_output_files():
            print(f"    - {f}")


if __name__ == "__main__":
    main()
