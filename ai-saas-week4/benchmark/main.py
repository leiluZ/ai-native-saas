import asyncio
import argparse
import time
import uuid
import yaml
from pathlib import Path
from typing import List, Dict, Optional
import sys

from .adapters import BaseAdapter, get_adapter, InferenceResult
from .metrics import MetricsCalculator, BenchmarkMetrics
from .prompts import get_prompts_by_length


async def run_benchmark(
    adapter: BaseAdapter,
    prompts: List[str],
    concurrency: int,
    max_tokens: int,
    gpu_memory_poll_interval: float = 1.0
) -> MetricsCalculator:
    calculator = MetricsCalculator()
    semaphore = asyncio.Semaphore(concurrency)

    async def worker(prompt: str, request_id: str):
        async with semaphore:
            result = await adapter.generate(prompt, request_id, max_tokens)
            calculator.add_result(result)
            return result

    gpu_monitor_task = None
    if hasattr(adapter, 'get_gpu_memory'):
        async def monitor_gpu():
            while True:
                try:
                    memory = await adapter.get_gpu_memory()
                    if memory:
                        calculator.add_gpu_memory(memory)
                except:
                    pass
                await asyncio.sleep(gpu_memory_poll_interval)

        gpu_monitor_task = asyncio.create_task(monitor_gpu())

    tasks = [worker(prompt, f"req_{i}_{uuid.uuid4().hex[:8]}") for i, prompt in enumerate(prompts)]

    await asyncio.gather(*tasks, return_exceptions=True)

    if gpu_monitor_task:
        gpu_monitor_task.cancel()
        try:
            await gpu_monitor_task
        except asyncio.CancelledError:
            pass

    return calculator


def print_metrics(metrics: BenchmarkMetrics, engine_name: str):
    print("\n" + "=" * 60)
    print(f"BENCHMARK RESULTS - {engine_name.upper()}")
    print("=" * 60)

    print(f"\nRequest Statistics:")
    print(f"  Total:     {metrics.total_requests}")
    print(f"  Success:   {metrics.successful_requests} ({metrics.success_rate*100:.1f}%)")
    print(f"  Failed:    {metrics.failed_requests}")

    if metrics.successful_requests > 0:
        print(f"\nTTFT (Time To First Token) [seconds]:")
        print(f"  Mean:  {metrics.ttft_mean:.4f}")
        print(f"  P50:   {metrics.ttft_p50:.4f}")
        print(f"  P95:   {metrics.ttft_p95:.4f}")
        print(f"  P99:   {metrics.ttft_p99:.4f}")
        print(f"  Min:   {metrics.ttft_min:.4f}")
        print(f"  Max:   {metrics.ttft_max:.4f}")

        print(f"\nTPOT (Time Per Output Token) [seconds]:")
        print(f"  Mean:  {metrics.tpot_mean:.4f}")
        print(f"  P50:   {metrics.tpot_p50:.4f}")
        print(f"  P95:   {metrics.tpot_p95:.4f}")
        print(f"  P99:   {metrics.tpot_p99:.4f}")

        print(f"\nEnd-to-End Latency [seconds]:")
        print(f"  Mean:  {metrics.e2e_latency_mean:.4f}")
        print(f"  P50:   {metrics.e2e_latency_p50:.4f}")
        print(f"  P95:   {metrics.e2e_latency_p95:.4f}")
        print(f"  P99:   {metrics.e2e_latency_p99:.4f}")

        print(f"\nThroughput [tokens/second]:")
        print(f"  Mean:  {metrics.throughput_mean:.2f}")
        print(f"  P50:   {metrics.throughput_p50:.2f}")
        print(f"  P95:   {metrics.throughput_p95:.2f}")
        print(f"  P99:   {metrics.throughput_p99:.2f}")

        print(f"\nToken Statistics:")
        print(f"  Total Tokens:           {metrics.total_tokens}")
        print(f"  Avg Tokens/Request:     {metrics.avg_tokens_per_request:.1f}")

        if metrics.peak_gpu_vram:
            print(f"\nPeak GPU VRAM: {metrics.peak_gpu_vram:.2f} MB")


def get_model_for_engine(args: argparse.Namespace) -> Optional[str]:
    engine = args.engine.lower() if args.engine else "vllm"
    if engine == "ollama":
        return args.ollama_model or args.model
    else:
        return args.vllm_model or args.model


def get_url_for_engine(args: argparse.Namespace) -> str:
    engine = args.engine.lower() if args.engine else "vllm"
    if engine == "ollama":
        return args.ollama_url or args.url or "http://localhost:11434"
    else:
        return args.vllm_url or args.url or "http://localhost:8000"


async def run_single_benchmark(
    engine: str,
    base_url: str,
    prompt_length: str,
    total_requests: int,
    concurrency: int,
    max_tokens: int,
    timeout: int,
    output_dir: Path,
    max_retries: int = 3,
    model: Optional[str] = None,
    api_key: Optional[str] = None
) -> BenchmarkMetrics:
    print(f"\n{'='*60}")
    print(f"Running benchmark for {engine} at {base_url}")
    if model:
        print(f"Model: {model}")
    print(f"Prompt length: {prompt_length}, Requests: {total_requests}, Concurrency: {concurrency}")
    print(f"{'='*60}")

    adapter_kwargs = {
        "base_url": base_url,
        "timeout": timeout,
        "max_retries": max_retries
    }
    if model:
        adapter_kwargs["model"] = model
    if api_key:
        adapter_kwargs["api_key"] = api_key

    adapter = get_adapter(engine, **adapter_kwargs)

    prompts = get_prompts_by_length(prompt_length, total_requests)

    start_time = time.time()
    calculator = await run_benchmark(adapter, prompts, concurrency, max_tokens)
    elapsed = time.time() - start_time

    metrics = calculator.calculate()
    metrics.elapsed_time = elapsed

    print_metrics(metrics, engine)

    csv_path = output_dir / f"{engine}_results.csv"
    calculator.to_csv(str(csv_path))
    print(f"\nResults saved to: {csv_path}")

    return metrics


async def run_comparison_benchmark(
    vllm_url: str,
    ollama_url: str,
    prompt_length: str,
    total_requests: int,
    concurrency: int,
    max_tokens: int,
    timeout: int,
    output_dir: Path,
    max_retries: int = 3,
    vllm_model: Optional[str] = None,
    ollama_model: Optional[str] = None,
    vllm_api_key: Optional[str] = None
):
    print(f"\n{'='*60}")
    print("RUNNING COMPARISON BENCHMARK")
    print(f"{'='*60}")

    prompts = get_prompts_by_length(prompt_length, total_requests)
    prompts_per_engine = len(prompts)

    vllm_kwargs = {"base_url": vllm_url, "timeout": timeout, "max_retries": max_retries}
    ollama_kwargs = {"base_url": ollama_url, "timeout": timeout, "max_retries": max_retries}
    if vllm_model:
        vllm_kwargs["model"] = vllm_model
    if ollama_model:
        ollama_kwargs["model"] = ollama_model
    if vllm_api_key:
        vllm_kwargs["api_key"] = vllm_api_key

    vllm_adapter = get_adapter("vllm", **vllm_kwargs)
    ollama_adapter = get_adapter("ollama", **ollama_kwargs)

    print(f"\n[1/2] Benchmarking vLLM...")
    vllm_start = time.time()
    vllm_calculator = await run_benchmark(vllm_adapter, prompts, concurrency, max_tokens)
    vllm_elapsed = time.time() - vllm_start
    vllm_metrics = vllm_calculator.calculate()
    vllm_metrics.elapsed_time = vllm_elapsed

    print_metrics(vllm_metrics, "vLLM")

    print(f"\n[2/2] Benchmarking Ollama...")
    ollama_start = time.time()
    ollama_calculator = await run_benchmark(ollama_adapter, prompts, concurrency, max_tokens)
    ollama_elapsed = time.time() - ollama_start
    ollama_metrics = ollama_calculator.calculate()
    ollama_metrics.elapsed_time = ollama_elapsed

    print_metrics(ollama_metrics, "Ollama")

    vllm_csv = output_dir / "vllm_results.csv"
    ollama_csv = output_dir / "ollama_results.csv"
    vllm_calculator.to_csv(str(vllm_csv))
    ollama_calculator.to_csv(str(ollama_csv))

    print(f"\nResults saved to:")
    print(f"  - {vllm_csv}")
    print(f"  - {ollama_csv}")

    print(f"\n{'='*60}")
    print("COMPARISON SUMMARY")
    print(f"{'='*60}")

    print(f"\n{'Metric':<25} {'vLLM':>15} {'Ollama':>15} {'Winner':>10}")
    print("-" * 70)

    comparisons = [
        {"name": "TTFT Mean (s)", "vllm": vllm_metrics.ttft_mean, "ollama": ollama_metrics.ttft_mean, "lower_is_better": True},
        {"name": "TPOT Mean (s)", "vllm": vllm_metrics.tpot_mean, "ollama": ollama_metrics.tpot_mean, "lower_is_better": True},
        {"name": "E2E Latency Mean (s)", "vllm": vllm_metrics.e2e_latency_mean, "ollama": ollama_metrics.e2e_latency_mean, "lower_is_better": True},
        {"name": "Throughput Mean (tok/s)", "vllm": vllm_metrics.throughput_mean, "ollama": ollama_metrics.throughput_mean, "lower_is_better": False},
    ]

    for c in comparisons:
        if c["lower_is_better"]:
            winner = "vLLM" if c["vllm"] < c["ollama"] else "Ollama"
        else:
            winner = "vLLM" if c["vllm"] > c["ollama"] else "Ollama"
        print(f"{c['name']:<25} {c['vllm']:>15.4f} {c['ollama']:>15.4f} {winner:>10}")

    print("\n" + "=" * 60)
    print("To generate visualization plots, run:")
    plots_dir = str(output_dir / 'plots')
    print(f"  python -m benchmark.visualization --csv {vllm_csv} {ollama_csv} --names vllm ollama --output {plots_dir}")
    print("=" * 60)


def load_config(config_path: str) -> dict:
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


async def main_async(args):
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.config:
        config = load_config(args.config)
        if args.engine:
            config['engine'] = args.engine
        if args.url:
            config['base_url'] = args.url
        args = argparse.Namespace(
            engine=config.get('engine', 'vllm'),
            url=config.get('base_url', 'http://localhost:8000'),
            prompt_length=config.get('prompt_length', 'all'),
            total_requests=config.get('total_requests', 100),
            concurrency=config.get('concurrency', 10),
            max_tokens=config.get('max_tokens', 512),
            timeout=config.get('timeout', 300),
            max_retries=config.get('max_retries', 3),
            output=str(output_dir),
            compare=False,
            vllm_url=config.get('vllm_url', 'http://localhost:8000'),
            ollama_url=config.get('ollama_url', 'http://localhost:11434'),
            model=config.get('model'),
            vllm_model=config.get('vllm_model'),
            ollama_model=config.get('ollama_model'),
            api_key=config.get('api_key'),
            vllm_api_key=config.get('vllm_api_key')
        )

    if args.compare:
        await run_comparison_benchmark(
            vllm_url=args.vllm_url,
            ollama_url=args.ollama_url,
            prompt_length=args.prompt_length,
            total_requests=args.total_requests,
            concurrency=args.concurrency,
            max_tokens=args.max_tokens,
            timeout=args.timeout,
            output_dir=output_dir,
            max_retries=args.max_retries,
            vllm_model=args.vllm_model,
            ollama_model=args.ollama_model,
            vllm_api_key=args.vllm_api_key
        )
    else:
        model = get_model_for_engine(args)
        url = get_url_for_engine(args)
        api_key = args.vllm_api_key if args.engine == "vllm" else None
        metrics = await run_single_benchmark(
            engine=args.engine,
            base_url=url,
            prompt_length=args.prompt_length,
            total_requests=args.total_requests,
            concurrency=args.concurrency,
            max_tokens=args.max_tokens,
            timeout=args.timeout,
            output_dir=output_dir,
            max_retries=args.max_retries,
            model=model,
            api_key=api_key
        )

        print("\n" + "=" * 60)
        print("To generate visualization plots, run:")
        print(f"  python -m benchmark.visualization --csv {output_dir / f'{args.engine}_results.csv'} --names {args.engine} --output {output_dir / 'plots'}")
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="LLM Inference Engine Benchmark Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run single engine benchmark
  python -m benchmark.main --engine vllm --url http://localhost:8000 --total-requests 100 --concurrency 10

  # Compare vLLM vs Ollama
  python -m benchmark.main --compare --vllm-url http://localhost:8000 --ollama-url http://localhost:11434

  # Use config file
  python -m benchmark.main --config config.yaml

  # Generate visualizations
  python -m benchmark.visualization --csv results/vllm_results.csv results/ollama_results.csv --names vllm ollama
        """
    )

    parser.add_argument("--config", type=str, help="Path to YAML configuration file")

    parser.add_argument("--engine", type=str, choices=["vllm", "ollama"], help="Inference engine to benchmark")
    parser.add_argument("--url", type=str, help="Base URL of the inference engine")

    parser.add_argument("--prompt-length", type=str, default="all",
                       choices=["short", "medium", "long", "all"],
                       help="Prompt length category (default: all)")
    parser.add_argument("--total-requests", type=int, default=100,
                       help="Total number of requests to send (default: 100)")
    parser.add_argument("--concurrency", type=int, default=10,
                       help="Number of concurrent requests (default: 10)")
    parser.add_argument("--max-tokens", type=int, default=512,
                       help="Maximum tokens to generate (default: 512)")
    parser.add_argument("--timeout", type=int, default=300,
                       help="Request timeout in seconds (default: 300)")
    parser.add_argument("--max-retries", type=int, default=3,
                       help="Maximum number of retries for failed requests (default: 3)")

    parser.add_argument("--output", type=str, default="./benchmark_results",
                       help="Output directory for results (default: ./benchmark_results)")

    parser.add_argument("--model", type=str,
                       help="Model name to use (applies to both engines, or the single engine being tested)")
    parser.add_argument("--vllm-model", type=str,
                       help="Model name for vLLM")
    parser.add_argument("--ollama-model", type=str,
                       help="Model name for Ollama")

    parser.add_argument("--api-key", type=str,
                       help="API key for authenticated API access (applies to vLLM)")
    parser.add_argument("--vllm-api-key", type=str,
                       help="API key for vLLM")

    parser.add_argument("--compare", action="store_true",
                       help="Run comparison benchmark between vLLM and Ollama")
    parser.add_argument("--vllm-url", type=str, default="http://localhost:8000",
                       help="vLLM base URL (default: http://localhost:8000)")
    parser.add_argument("--ollama-url", type=str, default="http://localhost:11434",
                       help="Ollama base URL (default: http://localhost:11434)")

    args = parser.parse_args()

    if args.compare and args.model:
        if not args.vllm_model:
            args.vllm_model = args.model
        if not args.ollama_model:
            args.ollama_model = args.model

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("\n\nBenchmark interrupted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\n\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
