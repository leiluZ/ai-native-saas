import pytest
import sys
import os
import tempfile
import pandas as pd
import numpy as np
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from benchmark.visualization import (
    load_benchmark_results,
    plot_latency_percentiles,
    plot_latency_cdf,
    plot_throughput_curve,
    plot_comparison_bar,
    plot_prompt_length_impact,
    generate_report
)


@pytest.fixture
def sample_df():
    data = []
    for i in range(50):
        data.append({
            "request_id": f"req_{i}",
            "prompt_length": 100 + i * 20,
            "completion_tokens": 80 + i * 5,
            "ttft": 0.3 + i * 0.02,
            "tpot": 0.01 + i * 0.001,
            "e2e_latency": 1.0 + i * 0.1,
            "throughput": 50.0 + i * 0.5,
            "success": True,
            "error": "",
            "timestamp": 1000.0 + i * 10
        })
    for i in range(5):
        data.append({
            "request_id": f"fail_{i}",
            "prompt_length": 0,
            "completion_tokens": 0,
            "ttft": 0,
            "tpot": 0,
            "e2e_latency": 0.05,
            "throughput": 0,
            "success": False,
            "error": "Connection timeout",
            "timestamp": 2000.0 + i
        })
    return pd.DataFrame(data)


@pytest.fixture
def temp_output_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestLoadBenchmarkResults:
    def test_load_csv(self, sample_df, temp_output_dir):
        csv_path = temp_output_dir / "test_results.csv"
        sample_df.to_csv(csv_path, index=False)

        loaded = load_benchmark_results(str(csv_path))
        assert len(loaded) == len(sample_df)
        assert list(loaded.columns) == list(sample_df.columns)

    def test_load_nonexistent_file(self):
        with pytest.raises(FileNotFoundError):
            load_benchmark_results("/nonexistent/path.csv")


class TestPlotLatencyPercentiles:
    def test_plot_creates_file(self, sample_df, temp_output_dir):
        plot_latency_percentiles(sample_df, "test-engine", temp_output_dir, show=False)

        output_path = temp_output_dir / "test-engine_percentiles.png"
        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_plot_with_empty_data(self, temp_output_dir):
        empty_df = pd.DataFrame(columns=[
            "request_id", "prompt_length", "completion_tokens",
            "ttft", "tpot", "e2e_latency", "throughput",
            "success", "error", "timestamp"
        ])
        plot_latency_percentiles(empty_df, "empty", temp_output_dir, show=False)


class TestPlotLatencyCDF:
    def test_plot_creates_file(self, sample_df, temp_output_dir):
        plot_latency_cdf(sample_df, "test-engine", temp_output_dir, show=False)

        output_path = temp_output_dir / "test-engine_cdf.png"
        assert output_path.exists()
        assert output_path.stat().st_size > 0


class TestPlotThroughputCurve:
    def test_plot_creates_file(self, sample_df, temp_output_dir):
        plot_throughput_curve(sample_df, "test-engine", temp_output_dir, window_size=5, show=False)

        output_path = temp_output_dir / "test-engine_throughput.png"
        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_plot_insufficient_data(self, temp_output_dir):
        small_df = pd.DataFrame([{
            "request_id": "req_0",
            "prompt_length": 100,
            "completion_tokens": 50,
            "ttft": 0.5,
            "tpot": 0.02,
            "e2e_latency": 1.5,
            "throughput": 33.3,
            "success": True,
            "error": "",
            "timestamp": 1000.0
        }])
        plot_throughput_curve(small_df, "small", temp_output_dir, window_size=10, show=False)


class TestPlotComparisonBar:
    def test_plot_creates_file(self, sample_df, temp_output_dir):
        results = {"vllm": sample_df, "ollama": sample_df.copy()}
        plot_comparison_bar(results, temp_output_dir, show=False)

        output_path = temp_output_dir / "comparison_bar.png"
        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_plot_single_engine(self, sample_df, temp_output_dir):
        results = {"vllm": sample_df}
        plot_comparison_bar(results, temp_output_dir, show=False)

        output_path = temp_output_dir / "comparison_bar.png"
        assert output_path.exists()


class TestPlotPromptLengthImpact:
    def test_plot_creates_file(self, sample_df, temp_output_dir):
        plot_prompt_length_impact(sample_df, "test-engine", temp_output_dir, show=False)

        output_path = temp_output_dir / "test-engine_prompt_length_impact.png"
        assert output_path.exists()
        assert output_path.stat().st_size > 0


class TestGenerateReport:
    def test_generate_report_creates_file(self, sample_df, temp_output_dir):
        results = {"vllm": sample_df}
        generate_report(results, temp_output_dir)

        report_path = temp_output_dir / "benchmark_report.txt"
        assert report_path.exists()
        assert report_path.stat().st_size > 0

    def test_report_content(self, sample_df, temp_output_dir):
        results = {"vllm": sample_df}
        generate_report(results, temp_output_dir)

        report_path = temp_output_dir / "benchmark_report.txt"
        content = report_path.read_text()

        assert "BENCHMARK REPORT" in content
        assert "VLLM" in content
        assert "Summary Statistics" in content
        assert "Latency Metrics" in content
        assert "Throughput Metrics" in content
        assert "Token Statistics" in content

    def test_report_multi_engine(self, sample_df, temp_output_dir):
        results = {"vllm": sample_df, "ollama": sample_df.copy()}
        generate_report(results, temp_output_dir)

        report_path = temp_output_dir / "benchmark_report.txt"
        content = report_path.read_text()

        assert "COMPARISON SUMMARY" in content
        assert "VLLM" in content
        assert "OLLAMA" in content

    def test_report_with_failures(self, sample_df, temp_output_dir):
        results = {"vllm": sample_df}
        generate_report(results, temp_output_dir)

        report_path = temp_output_dir / "benchmark_report.txt"
        content = report_path.read_text()
        assert "Failed:" in content


class TestVisualizationModule:
    def test_module_imports(self):
        import benchmark.visualization
        assert hasattr(benchmark.visualization, 'load_benchmark_results')
        assert hasattr(benchmark.visualization, 'plot_latency_percentiles')
        assert hasattr(benchmark.visualization, 'plot_latency_cdf')
        assert hasattr(benchmark.visualization, 'plot_throughput_curve')
        assert hasattr(benchmark.visualization, 'plot_comparison_bar')
        assert hasattr(benchmark.visualization, 'plot_prompt_length_impact')
        assert hasattr(benchmark.visualization, 'generate_report')
        assert hasattr(benchmark.visualization, 'main')

    def test_cli_help(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, '-m', 'benchmark.visualization', '--help'],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), '..')
        )
        assert result.returncode == 0
        assert '--csv' in result.stdout
        assert '--names' in result.stdout
        assert '--output' in result.stdout
