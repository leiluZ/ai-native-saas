import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from typing import Optional

from .kv_cache_runner import TuningResult, ConfigBenchmarkResult


def plot_throughput_vs_config(
    tuning_result: TuningResult,
    output_dir: Path,
    show: bool = False,
):
    labels = []
    throughputs = []
    p99s = []
    gpu_mems = []

    config_aggregates: dict[str, list[ConfigBenchmarkResult]] = {}
    for r in tuning_result.config_results:
        if r.success and r.metrics is not None:
            config_aggregates.setdefault(r.config_label, []).append(r)

    for label, results in config_aggregates.items():
        if not results:
            continue
        labels.append(label)
        throughputs.append(sum(r.metrics.throughput_mean for r in results) / len(results))
        p99s.append(sum(r.metrics.e2e_latency_p99 for r in results) / len(results))
        gpu_mems.append(sum(r.gpu_memory_pct for r in results) / len(results))

    if not labels:
        return

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    x = np.arange(len(labels))
    width = 0.6

    colors = ["#2ecc71" if l == tuning_result.optimal_label else "#3498db" for l in labels]

    axes[0].bar(x, throughputs, width, color=colors)
    axes[0].set_xlabel("Config")
    axes[0].set_ylabel("Throughput (tokens/s)")
    axes[0].set_title("Average Throughput by Config")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
    axes[0].grid(axis="y", alpha=0.3)

    axes[1].bar(x, p99s, width, color=colors)
    axes[1].set_xlabel("Config")
    axes[1].set_ylabel("P99 Latency (s)")
    axes[1].set_title("P99 Latency by Config")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
    axes[1].grid(axis="y", alpha=0.3)

    axes[2].bar(x, gpu_mems, width, color=colors)
    axes[2].axhline(y=80, color="orange", linestyle="--", label="80% target")
    axes[2].axhline(y=92, color="red", linestyle="--", label="92% safety limit")
    axes[2].set_xlabel("Config")
    axes[2].set_ylabel("GPU Memory (%)")
    axes[2].set_title("GPU Memory Utilization by Config")
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
    axes[2].legend()
    axes[2].grid(axis="y", alpha=0.3)

    plt.tight_layout()
    output_path = output_dir / "kv_cache_throughput_vs_config.png"
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    if show:
        plt.show()
    plt.close()


def plot_heatmap(
    tuning_result: TuningResult,
    output_dir: Path,
    show: bool = False,
):
    gmu_values = sorted(set(r.config.gpu_memory_utilization for r in tuning_result.config_results))
    bs_values = sorted(set(r.config.block_size for r in tuning_result.config_results))
    mns_values = sorted(set(r.config.max_num_seqs for r in tuning_result.config_results))

    if not gmu_values or not bs_values or not mns_values:
        return

    fig, axes = plt.subplots(1, len(mns_values), figsize=(6 * len(mns_values), 5))
    if len(mns_values) == 1:
        axes = [axes]

    for ax_idx, mns in enumerate(mns_values):
        heatmap_data = np.zeros((len(bs_values), len(gmu_values)))
        annot_data = np.empty((len(bs_values), len(gmu_values)), dtype=object)

        for i, bs in enumerate(bs_values):
            for j, gmu in enumerate(gmu_values):
                matching = [
                    r for r in tuning_result.config_results
                    if r.success and r.metrics is not None
                    and abs(r.config.gpu_memory_utilization - gmu) < 0.001
                    and r.config.block_size == bs
                    and r.config.max_num_seqs == mns
                ]
                if matching:
                    avg_tput = sum(r.metrics.throughput_mean for r in matching) / len(matching)
                    heatmap_data[i, j] = avg_tput
                    annot_data[i, j] = f"{avg_tput:.1f}"
                else:
                    heatmap_data[i, j] = 0
                    annot_data[i, j] = "N/A"

        im = axes[ax_idx].imshow(heatmap_data, cmap="YlOrRd", aspect="auto")
        axes[ax_idx].set_xticks(range(len(gmu_values)))
        axes[ax_idx].set_xticklabels([f"{v:.2f}" for v in gmu_values])
        axes[ax_idx].set_yticks(range(len(bs_values)))
        axes[ax_idx].set_yticklabels(bs_values)
        axes[ax_idx].set_xlabel("GPU Memory Utilization")
        axes[ax_idx].set_ylabel("Block Size")
        axes[ax_idx].set_title(f"Throughput Heatmap (max_num_seqs={mns})")

        for i in range(len(bs_values)):
            for j in range(len(gmu_values)):
                text_color = "white" if heatmap_data[i, j] > heatmap_data.max() * 0.6 else "black"
                axes[ax_idx].text(j, i, annot_data[i, j], ha="center", va="center", color=text_color, fontsize=8)

        plt.colorbar(im, ax=axes[ax_idx], label="Throughput (tok/s)")

    plt.tight_layout()
    output_path = output_dir / "kv_cache_heatmap.png"
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    if show:
        plt.show()
    plt.close()


def plot_performance_gain(
    tuning_result: TuningResult,
    output_dir: Path,
    show: bool = False,
):
    if tuning_result.optimal_config is None:
        return

    optimal_results = [
        r for r in tuning_result.config_results
        if r.success and r.metrics is not None and r.config_label == tuning_result.optimal_label
    ]

    other_results = [
        r for r in tuning_result.config_results
        if r.success and r.metrics is not None and r.config_label != tuning_result.optimal_label
    ]

    if not optimal_results or not other_results:
        return

    opt_throughput = sum(r.metrics.throughput_mean for r in optimal_results) / len(optimal_results)
    opt_p99 = sum(r.metrics.e2e_latency_p99 for r in optimal_results) / len(optimal_results)
    opt_gpu = sum(r.gpu_memory_pct for r in optimal_results) / len(optimal_results)

    other_throughput = sum(r.metrics.throughput_mean for r in other_results) / len(other_results)
    other_p99 = sum(r.metrics.e2e_latency_p99 for r in other_results) / len(other_results)
    other_gpu = sum(r.gpu_memory_pct for r in other_results) / len(other_results)

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    metrics_names = ["Throughput (tok/s)", "P99 Latency (s)", "GPU Memory (%)"]
    opt_values = [opt_throughput, opt_p99, opt_gpu]
    other_values = [other_throughput, other_p99, other_gpu]
    improvements = [
        (opt_throughput - other_throughput) / max(other_throughput, 0.001) * 100,
        (other_p99 - opt_p99) / max(other_p99, 0.001) * 100,
        (opt_gpu - other_gpu) / max(other_gpu, 0.001) * 100,
    ]

    for i, (name, opt, other, imp) in enumerate(zip(metrics_names, opt_values, other_values, improvements)):
        axes[i].bar(["Other Avg", "Optimal"], [other, opt], color=["#3498db", "#2ecc71"])
        axes[i].set_title(f"{name}\nImprovement: {imp:+.1f}%")
        axes[i].grid(axis="y", alpha=0.3)

        for bar_idx, val in enumerate([other, opt]):
            axes[i].text(bar_idx, val + max(other, opt) * 0.02, f"{val:.2f}", ha="center", fontsize=10)

    plt.suptitle(f"Optimal Config: {tuning_result.optimal_label}", fontsize=12, fontweight="bold")
    plt.tight_layout()
    output_path = output_dir / "kv_cache_performance_gain.png"
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    if show:
        plt.show()
    plt.close()


def plot_oom_distribution(
    tuning_result: TuningResult,
    output_dir: Path,
    show: bool = False,
):
    config_oom: dict[str, int] = {}
    for r in tuning_result.config_results:
        label = r.config_label
        config_oom[label] = config_oom.get(label, 0) + r.oom_count

    if not config_oom:
        return

    labels = list(config_oom.keys())
    values = list(config_oom.values())

    fig, ax = plt.subplots(figsize=(12, 6))
    colors = ["#e74c3c" if v > 0 else "#2ecc71" for v in values]
    ax.bar(range(len(labels)), values, color=colors)
    ax.set_xlabel("Config")
    ax.set_ylabel("Total OOM Count")
    ax.set_title("OOM Distribution Across Configs")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    output_path = output_dir / "kv_cache_oom_distribution.png"
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    if show:
        plt.show()
    plt.close()


def generate_all_plots(
    tuning_result: TuningResult,
    output_dir: Path,
    show: bool = False,
):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    plot_throughput_vs_config(tuning_result, output_dir, show)
    plot_heatmap(tuning_result, output_dir, show)
    plot_performance_gain(tuning_result, output_dir, show)
    plot_oom_distribution(tuning_result, output_dir, show)


def generate_vllm_startup_command(config, model: str, host: str = "127.0.0.1", port: int = 8000) -> str:
    args = config.to_cli_args()
    cmd_parts = [
        "python -m vllm.entrypoints.openai.api_server",
        f"--model {model}",
        f"--host {host}",
        f"--port {port}",
    ] + args
    return " \\\n    ".join(cmd_parts)


def print_tuning_report(tuning_result: TuningResult):
    print("\n" + "=" * 70)
    print("KV CACHE PARAMETER TUNING REPORT")
    print("=" * 70)

    print(f"\n  Total configs tested:  {tuning_result.total_configs_tested}")
    print(f"  Total rounds run:      {tuning_result.total_rounds}")
    print(f"  Total time:            {tuning_result.total_time_s:.1f}s")

    if tuning_result.optimal_config:
        print(f"\n  OPTIMAL CONFIG: {tuning_result.optimal_label}")
        print(f"    gpu_memory_utilization:  {tuning_result.optimal_config.gpu_memory_utilization}")
        print(f"    block_size:              {tuning_result.optimal_config.block_size}")
        print(f"    max_num_seqs:            {tuning_result.optimal_config.max_num_seqs}")
        print(f"    enable_chunked_prefill:  {tuning_result.optimal_config.enable_chunked_prefill}")
        print(f"    max_num_batched_tokens:  {tuning_result.optimal_config.max_num_batched_tokens}")
        print(f"    enable_prefix_caching:   {tuning_result.optimal_config.enable_prefix_caching}")

        optimal_results = [
            r for r in tuning_result.config_results
            if r.success and r.metrics is not None and r.config_label == tuning_result.optimal_label
        ]
        if optimal_results:
            avg_tput = sum(r.metrics.throughput_mean for r in optimal_results) / len(optimal_results)
            avg_p99 = sum(r.metrics.e2e_latency_p99 for r in optimal_results) / len(optimal_results)
            avg_gpu = sum(r.gpu_memory_pct for r in optimal_results) / len(optimal_results)
            print(f"\n  Performance (optimal config):")
            print(f"    Avg Throughput:    {avg_tput:.2f} tok/s")
            print(f"    Avg P99 Latency:   {avg_p99:.4f}s")
            print(f"    Avg GPU Memory:    {avg_gpu:.1f}%")

    print("\n" + "-" * 70)
    print("  Config Performance Summary:")
    print(f"  {'Config':<40} {'Throughput':>12} {'P99(s)':>10} {'GPU%':>8} {'OOM':>6}")
    print("  " + "-" * 68)

    config_aggregates: dict[str, list[ConfigBenchmarkResult]] = {}
    for r in tuning_result.config_results:
        if r.success and r.metrics is not None:
            config_aggregates.setdefault(r.config_label, []).append(r)

    for label, results in sorted(config_aggregates.items()):
        avg_tput = sum(r.metrics.throughput_mean for r in results) / len(results)
        avg_p99 = sum(r.metrics.e2e_latency_p99 for r in results) / len(results)
        avg_gpu = sum(r.gpu_memory_pct for r in results) / len(results)
        total_oom = sum(r.oom_count for r in results)
        marker = " ★" if label == tuning_result.optimal_label else ""
        print(f"  {label+marker:<40} {avg_tput:>12.2f} {avg_p99:>10.4f} {avg_gpu:>7.1f}% {total_oom:>5}")

    print("\n" + "=" * 70)
    print("  vLLM STARTUP COMMAND (optimal config):")
    print("  " + "-" * 70)
    if tuning_result.optimal_config:
        cmd = generate_vllm_startup_command(tuning_result.optimal_config, "<MODEL_NAME>")
        print(f"  {cmd}")
    print("=" * 70)
