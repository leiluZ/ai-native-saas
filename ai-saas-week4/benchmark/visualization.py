import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, Dict, List
import argparse
import sys


def load_benchmark_results(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    return df


def plot_latency_percentiles(
    df: pd.DataFrame,
    engine_name: str,
    output_dir: Path,
    show: bool = False
):
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    successful = df[df['success'] == True]

    if len(successful) == 0:
        plt.close(fig)
        return

    ttft = successful['ttft'].dropna()
    tpot = successful['tpot'].dropna()
    e2e = successful['e2e_latency'].dropna()

    percentiles = [50, 75, 90, 95, 99]
    ttft_values = [np.percentile(ttft, p) for p in percentiles]
    tpot_values = [np.percentile(tpot, p) for p in percentiles]
    e2e_values = [np.percentile(e2e, p) for p in percentiles]

    x = np.arange(len(percentiles))
    width = 0.25

    axes[0].bar(x - width, ttft_values, width, label='TTFT')
    axes[0].set_xlabel('Percentile')
    axes[0].set_ylabel('Time (s)')
    axes[0].set_title(f'{engine_name} - TTFT Percentiles')
    axes[0].set_xticks(x)
    axes[0].set_xticklabels([f'P{p}' for p in percentiles])
    axes[0].grid(axis='y', alpha=0.3)

    axes[1].bar(x, tpot_values, width, label='TPOT', color='orange')
    axes[1].set_xlabel('Percentile')
    axes[1].set_ylabel('Time (s)')
    axes[1].set_title(f'{engine_name} - TPOT Percentiles')
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([f'P{p}' for p in percentiles])
    axes[1].grid(axis='y', alpha=0.3)

    axes[2].bar(x + width, e2e_values, width, label='E2E Latency', color='green')
    axes[2].set_xlabel('Percentile')
    axes[2].set_ylabel('Time (s)')
    axes[2].set_title(f'{engine_name} - E2E Latency Percentiles')
    axes[2].set_xticks(x)
    axes[2].set_xticklabels([f'P{p}' for p in percentiles])
    axes[2].grid(axis='y', alpha=0.3)

    plt.tight_layout()
    output_path = output_dir / f'{engine_name}_percentiles.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    if show:
        plt.show()
    plt.close()
    print(f"Saved: {output_path}")


def plot_latency_cdf(
    df: pd.DataFrame,
    engine_name: str,
    output_dir: Path,
    show: bool = False
):
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    successful = df[df['success'] == True]

    for idx, (col, title, color) in enumerate([
        ('ttft', 'TTFT', 'blue'),
        ('tpot', 'TPOT', 'orange'),
        ('e2e_latency', 'E2E Latency', 'green')
    ]):
        values = successful[col].dropna().sort_values()
        cdf = np.arange(1, len(values) + 1) / len(values)

        axes[idx].plot(values, cdf, color=color, linewidth=2)
        axes[idx].set_xlabel('Time (s)')
        axes[idx].set_ylabel('Cumulative Probability')
        axes[idx].set_title(f'{engine_name} - {title} CDF')
        axes[idx].grid(alpha=0.3)
        axes[idx].axhline(y=0.5, color='gray', linestyle='--', alpha=0.5, label='P50')
        axes[idx].axhline(y=0.95, color='gray', linestyle=':', alpha=0.5, label='P95')
        axes[idx].axhline(y=0.99, color='gray', linestyle='-.', alpha=0.5, label='P99')
        axes[idx].legend()

    plt.tight_layout()
    output_path = output_dir / f'{engine_name}_cdf.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    if show:
        plt.show()
    plt.close()
    print(f"Saved: {output_path}")


def plot_throughput_curve(
    df: pd.DataFrame,
    engine_name: str,
    output_dir: Path,
    window_size: int = 10,
    show: bool = False
):
    fig, ax = plt.subplots(figsize=(12, 6))

    successful = df[df['success'] == True].sort_values('timestamp')

    if len(successful) < window_size:
        print(f"Warning: Not enough data points for throughput curve (need {window_size}, got {len(successful)})")
        return

    timestamps = successful['timestamp'].values
    throughputs = successful['throughput'].values

    rolling_throughput = []
    for i in range(window_size - 1, len(throughputs)):
        window = throughputs[i - window_size + 1:i + 1]
        rolling_throughput.append(np.mean(window))

    rolling_time = timestamps[window_size - 1:]

    ax.plot(rolling_time, rolling_throughput, color='purple', linewidth=1.5, label='Rolling Throughput')
    ax.axhline(y=np.mean(rolling_throughput), color='red', linestyle='--', label=f'Mean: {np.mean(rolling_throughput):.2f} tok/s')
    ax.fill_between(rolling_time, rolling_throughput, alpha=0.3)

    ax.set_xlabel('Timestamp')
    ax.set_ylabel('Throughput (tokens/s)')
    ax.set_title(f'{engine_name} - Throughput Over Time (window={window_size})')
    ax.legend()
    ax.grid(alpha=0.3)

    plt.xticks(rotation=45)
    plt.tight_layout()
    output_path = output_dir / f'{engine_name}_throughput.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    if show:
        plt.show()
    plt.close()
    print(f"Saved: {output_path}")


def plot_comparison_bar(
    results: Dict[str, pd.DataFrame],
    output_dir: Path,
    show: bool = False
):
    engines = list(results.keys())
    metrics = ['ttft_mean', 'tpot_mean', 'e2e_latency_mean', 'throughput_mean']

    fig, axes = plt.subplots(2, 2, figsize=(12, 10))

    metric_info = {
        'ttft_mean': ('TTFT Mean (s)', 'TTFT'),
        'tpot_mean': ('TPOT Mean (s)', 'TPOT'),
        'e2e_latency_mean': ('E2E Latency Mean (s)', 'E2E'),
        'throughput_mean': ('Throughput Mean (tok/s)', 'Throughput')
    }

    for idx, (metric, (title, name)) in enumerate(metric_info.items()):
        ax = axes[idx // 2, idx % 2]
        values = []
        for engine in engines:
            df = results[engine]
            successful = df[df['success'] == True]
            if metric == 'throughput_mean':
                values.append(successful['throughput'].mean())
            else:
                values.append(successful[metric.replace('_mean', '')].mean())

        bars = ax.bar(engines, values, color=['skyblue', 'lightcoral'][:len(engines)])
        ax.set_title(title)
        ax.grid(axis='y', alpha=0.3)

        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                   f'{val:.4f}', ha='center', va='bottom', fontsize=9)

    plt.tight_layout()
    output_path = output_dir / 'comparison_bar.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    if show:
        plt.show()
    plt.close()
    print(f"Saved: {output_path}")


def plot_prompt_length_impact(
    df: pd.DataFrame,
    engine_name: str,
    output_dir: Path,
    show: bool = False
):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    successful = df[df['success'] == True].copy()

    successful['prompt_bucket'] = pd.cut(
        successful['prompt_length'],
        bins=[0, 128, 512, 2048, float('inf')],
        labels=['Short (<128)', 'Medium (128-512)', 'Long (512-2048)', 'Very Long (>2048)']
    )

    grouped = successful.groupby('prompt_bucket', observed=True).agg({
        'ttft': ['mean', 'std'],
        'e2e_latency': ['mean', 'std'],
        'throughput': 'mean'
    }).reset_index()

    grouped.columns = ['prompt_bucket', 'ttft_mean', 'ttft_std', 'e2e_mean', 'e2e_std', 'throughput_mean']

    buckets = grouped['prompt_bucket'].astype(str)
    x = np.arange(len(buckets))
    width = 0.35

    axes[0].bar(x - width/2, grouped['ttft_mean'], width, yerr=grouped['ttft_std'],
                label='TTFT', color='steelblue', capsize=3)
    axes[0].bar(x + width/2, grouped['e2e_mean'], width, yerr=grouped['e2e_std'],
                label='E2E Latency', color='coral', capsize=3)
    axes[0].set_xlabel('Prompt Length Bucket')
    axes[0].set_ylabel('Time (s)')
    axes[0].set_title(f'{engine_name} - Latency by Prompt Length')
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(buckets, rotation=15)
    axes[0].legend()
    axes[0].grid(axis='y', alpha=0.3)

    axes[1].bar(x, grouped['throughput_mean'], width, color='green', alpha=0.7)
    axes[1].set_xlabel('Prompt Length Bucket')
    axes[1].set_ylabel('Throughput (tokens/s)')
    axes[1].set_title(f'{engine_name} - Throughput by Prompt Length')
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(buckets, rotation=15)
    axes[1].grid(axis='y', alpha=0.3)

    plt.tight_layout()
    output_path = output_dir / f'{engine_name}_prompt_length_impact.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    if show:
        plt.show()
    plt.close()
    print(f"Saved: {output_path}")


def generate_report(results: Dict[str, pd.DataFrame], output_dir: Path):
    report_path = output_dir / 'benchmark_report.txt'

    with open(report_path, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("LLM INFERENCE BENCHMARK REPORT\n")
        f.write("=" * 80 + "\n\n")

        for engine_name, df in results.items():
            successful = df[df['success'] == True]

            f.write(f"\n{'=' * 40}\n")
            f.write(f"Engine: {engine_name.upper()}\n")
            f.write(f"{'=' * 40}\n\n")

            f.write("Summary Statistics:\n")
            f.write(f"  Total Requests: {len(df)}\n")
            f.write(f"  Successful: {len(successful)} ({len(successful)/len(df)*100:.1f}%)\n")
            f.write(f"  Failed: {len(df) - len(successful)}\n\n")

            if len(successful) > 0:
                f.write("Latency Metrics (seconds):\n")
                f.write(f"  TTFT  - Mean: {successful['ttft'].mean():.4f}, P50: {successful['ttft'].median():.4f}, P95: {np.percentile(successful['ttft'], 95):.4f}, P99: {np.percentile(successful['ttft'], 99):.4f}\n")
                f.write(f"  TPOT  - Mean: {successful['tpot'].mean():.4f}, P50: {successful['tpot'].median():.4f}, P95: {np.percentile(successful['tpot'], 95):.4f}, P99: {np.percentile(successful['tpot'], 99):.4f}\n")
                f.write(f"  E2E   - Mean: {successful['e2e_latency'].mean():.4f}, P50: {successful['e2e_latency'].median():.4f}, P95: {np.percentile(successful['e2e_latency'], 95):.4f}, P99: {np.percentile(successful['e2e_latency'], 99):.4f}\n\n")

                f.write("Throughput Metrics:\n")
                f.write(f"  Mean: {successful['throughput'].mean():.2f} tokens/s\n")
                f.write(f"  P50: {successful['throughput'].median():.2f} tokens/s\n")
                f.write(f"  P95: {np.percentile(successful['throughput'], 95):.2f} tokens/s\n")
                f.write(f"  P99: {np.percentile(successful['throughput'], 99):.2f} tokens/s\n\n")

                f.write("Token Statistics:\n")
                f.write(f"  Total Tokens Generated: {successful['completion_tokens'].sum()}\n")
                f.write(f"  Avg Tokens/Request: {successful['completion_tokens'].mean():.1f}\n")

        if len(results) > 1:
            f.write("\n" + "=" * 80 + "\n")
            f.write("COMPARISON SUMMARY\n")
            f.write("=" * 80 + "\n\n")

            engines = list(results.keys())
            for metric, label in [('ttft', 'TTFT'), ('tpot', 'TPOT'), ('e2e_latency', 'E2E Latency'), ('throughput', 'Throughput')]:
                f.write(f"{label}:\n")
                for engine in engines:
                    df = results[engine]
                    successful = df[df['success'] == True]
                    if len(successful) > 0:
                        f.write(f"  {engine}: {successful[metric].mean():.4f}\n")
                f.write("\n")

    print(f"Saved: {report_path}")


def main():
    parser = argparse.ArgumentParser(description='Visualize LLM benchmark results')
    parser.add_argument('--csv', type=str, nargs='+', required=True, help='Path(s) to CSV result files')
    parser.add_argument('--names', type=str, nargs='+', help='Engine names for each CSV')
    parser.add_argument('--output', type=str, default='./benchmark_results', help='Output directory')
    parser.add_argument('--show', action='store_true', help='Show plots interactively')

    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.names and len(args.names) != len(args.csv):
        print("Error: Number of names must match number of CSV files")
        sys.exit(1)

    results = {}
    for idx, csv_path in enumerate(args.csv):
        name = args.names[idx] if args.names else Path(csv_path).stem
        results[name] = load_benchmark_results(csv_path)

    for engine_name, df in results.items():
        print(f"\nGenerating plots for {engine_name}...")
        plot_latency_percentiles(df, engine_name, output_dir, args.show)
        plot_latency_cdf(df, engine_name, output_dir, args.show)
        plot_throughput_curve(df, engine_name, output_dir, show=args.show)
        plot_prompt_length_impact(df, engine_name, output_dir, args.show)

    if len(results) > 1:
        print("\nGenerating comparison plots...")
        plot_comparison_bar(results, output_dir, args.show)

    print("\nGenerating report...")
    generate_report(results, output_dir)

    print(f"\nAll outputs saved to: {output_dir}")


if __name__ == "__main__":
    main()
