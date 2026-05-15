import asyncio
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

from .gpu_scanner import scan_gpus, format_scan_report
from .kv_cache_config import (
    KVCacheConfig,
    GridSearchConfig,
    SafetyThresholds,
    DEFAULT_GRID_SEARCH,
    DEFAULT_SAFETY_THRESHOLDS,
)
from .vllm_lifecycle import VLLMLifecycleManager
from .prefill_adjuster import PrefillAdjuster
from .kv_cache_runner import KVCacheBenchmarkRunner, TuningResult
from .kv_cache_visualization import generate_all_plots, print_tuning_report, generate_vllm_startup_command


def parse_args():
    parser = argparse.ArgumentParser(
        description="vLLM KV Cache Parameter Auto-Tuning",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--model", type=str, required=True, help="Model name or path")
    parser.add_argument("--port", type=int, default=8000, help="vLLM server port (default: 8000)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="vLLM server host (default: 127.0.0.1)")

    grid_group = parser.add_argument_group("Grid Search")
    grid_group.add_argument("--gmu-values", type=float, nargs="+", default=[0.80, 0.85, 0.90],
                            help="GPU memory utilization values (default: 0.80 0.85 0.90)")
    grid_group.add_argument("--bs-values", type=int, nargs="+", default=[16, 32],
                            help="Block size values (default: 16 32)")
    grid_group.add_argument("--mns-values", type=int, nargs="+", default=[32, 64, 128],
                            help="Max num seqs values (default: 32 64 128)")
    grid_group.add_argument("--no-chunked-prefill", action="store_true",
                            help="Disable chunked prefill in grid search")
    grid_group.add_argument("--bt-values", type=int, nargs="+", default=[None, 2048, 4096, 8192],
                            help="Max num batched tokens values (default: None 2048 4096 8192)")

    bench_group = parser.add_argument_group("Benchmark")
    bench_group.add_argument("--rounds", type=int, default=3, help="Rounds per config (default: 3)")
    bench_group.add_argument("--prompts", type=int, default=50, help="Prompts per round (default: 50)")
    bench_group.add_argument("--concurrency", type=int, default=8, help="Concurrency (default: 8)")
    bench_group.add_argument("--max-tokens", type=int, default=512, help="Max tokens per request (default: 512)")
    bench_group.add_argument("--timeout", type=int, default=300, help="Request timeout in seconds (default: 300)")

    safety_group = parser.add_argument_group("Safety Thresholds")
    safety_group.add_argument("--gpu-mem-max", type=float, default=92.0,
                              help="Max GPU memory %% before abort (default: 92)")
    safety_group.add_argument("--p99-latency-max", type=float, default=2.0,
                              help="Max P99 latency in seconds before abort (default: 2.0)")
    safety_group.add_argument("--consecutive-oom-max", type=int, default=2,
                              help="Max consecutive OOM rounds before abort (default: 2)")

    output_group = parser.add_argument_group("Output")
    output_group.add_argument("--output-dir", type=str, default="./kv_cache_tuning_results",
                              help="Output directory (default: ./kv_cache_tuning_results)")
    output_group.add_argument("--no-plots", action="store_true", help="Skip generating plots")

    parser.add_argument("--extra-vllm-args", type=str, nargs="*", default=[],
                        help="Extra arguments to pass to vLLM")

    return parser.parse_args()


async def run_tuning(args: argparse.Namespace) -> TuningResult:
    print("=" * 70)
    print("vLLM KV CACHE PARAMETER AUTO-TUNING")
    print("=" * 70)

    print("\n[1/5] Scanning GPU...")
    gpu_result = scan_gpus()
    print(format_scan_report(gpu_result))

    grid_search = GridSearchConfig(
        gpu_memory_utilization_values=args.gmu_values,
        block_size_values=args.bs_values,
        max_num_seqs_values=args.mns_values,
        enable_chunked_prefill_values=[True, False] if not args.no_chunked_prefill else [False],
        max_num_batched_tokens_values=args.bt_values,
    )

    safety = SafetyThresholds(
        gpu_memory_pct_max=args.gpu_mem_max,
        p99_latency_max_s=args.p99_latency_max,
        consecutive_oom_max=args.consecutive_oom_max,
    )

    configs = grid_search.generate_combinations()
    print(f"\n[2/5] Generated {len(configs)} config combinations for grid search")
    print(f"  gpu_memory_utilization: {args.gmu_values}")
    print(f"  block_size: {args.bs_values}")
    print(f"  max_num_seqs: {args.mns_values}")
    print(f"  chunked_prefill: {not args.no_chunked_prefill}")
    print(f"  max_num_batched_tokens: {args.bt_values}")
    print(f"  Rounds per config: {args.rounds}")
    print(f"  Total benchmark runs: {len(configs) * args.rounds}")

    lifecycle = VLLMLifecycleManager(
        model=args.model,
        port=args.port,
        host=args.host,
    )

    prefill_adjuster = PrefillAdjuster()

    runner = KVCacheBenchmarkRunner(
        lifecycle=lifecycle,
        safety=safety,
        prefill_adjuster=prefill_adjuster,
        rounds_per_config=args.rounds,
        prompts_per_round=args.prompts,
        concurrency=args.concurrency,
        max_tokens=args.max_tokens,
        timeout=args.timeout,
    )

    print(f"\n[3/5] Starting grid search benchmark...")
    extra_args = args.extra_vllm_args if args.extra_vllm_args else None
    tuning_result = await runner.run_all_configs(configs, extra_args)

    print(f"\n[4/5] Finding optimal configuration...")
    tuning_result = runner.find_optimal_config(tuning_result)
    tuning_result.gpu_info = {
        "gpu_count": gpu_result.total_gpu_count,
        "total_memory_mb": gpu_result.total_memory_mb,
        "cuda_version": gpu_result.cuda_version,
        "driver_version": gpu_result.driver_version,
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print_tuning_report(tuning_result)

    if not args.no_plots:
        print(f"\n[5/5] Generating visualization plots...")
        generate_all_plots(tuning_result, output_dir)

    results_json = {
        "timestamp": datetime.now().isoformat(),
        "model": args.model,
        "gpu_info": tuning_result.gpu_info,
        "grid_search_params": {
            "gpu_memory_utilization": args.gmu_values,
            "block_size": args.bs_values,
            "max_num_seqs": args.mns_values,
            "chunked_prefill": not args.no_chunked_prefill,
            "max_num_batched_tokens": [str(v) for v in args.bt_values],
        },
        "benchmark_params": {
            "rounds_per_config": args.rounds,
            "prompts_per_round": args.prompts,
            "concurrency": args.concurrency,
            "max_tokens": args.max_tokens,
        },
        "safety_thresholds": {
            "gpu_memory_pct_max": args.gpu_mem_max,
            "p99_latency_max_s": args.p99_latency_max,
            "consecutive_oom_max": args.consecutive_oom_max,
        },
        "optimal_config": tuning_result.optimal_config.to_dict() if tuning_result.optimal_config else None,
        "optimal_label": tuning_result.optimal_label,
        "total_configs_tested": tuning_result.total_configs_tested,
        "total_rounds": tuning_result.total_rounds,
        "total_time_s": tuning_result.total_time_s,
        "config_results": [
            {
                "label": r.config_label,
                "round": r.round_number,
                "success": r.success,
                "oom_count": r.oom_count,
                "gpu_memory_pct": r.gpu_memory_pct,
                "p99_latency_s": r.p99_latency_s,
                "throughput_mean": r.metrics.throughput_mean if r.metrics else 0,
                "terminated_by_safety": r.terminated_by_safety,
                "termination_reason": r.termination_reason,
                "errors": r.errors,
            }
            for r in tuning_result.config_results
        ],
    }

    json_path = output_dir / "tuning_results.json"
    with open(json_path, "w") as f:
        json.dump(results_json, f, indent=2)
    print(f"\nResults saved to: {json_path}")

    if tuning_result.optimal_config:
        cmd_path = output_dir / "vllm_startup_command.sh"
        cmd = generate_vllm_startup_command(tuning_result.optimal_config, args.model, args.host, args.port)
        with open(cmd_path, "w") as f:
            f.write("#!/bin/bash\n")
            f.write(cmd + "\n")
        cmd_path.chmod(0o755)
        print(f"Startup command saved to: {cmd_path}")

    return tuning_result


def main():
    args = parse_args()
    asyncio.run(run_tuning(args))


if __name__ == "__main__":
    main()
