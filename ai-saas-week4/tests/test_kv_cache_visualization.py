import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch
from benchmark.kv_cache_visualization import (
    plot_throughput_vs_config,
    plot_heatmap,
    plot_performance_gain,
    plot_oom_distribution,
    generate_all_plots,
    generate_vllm_startup_command,
    print_tuning_report,
)
from benchmark.kv_cache_runner import TuningResult, ConfigBenchmarkResult
from benchmark.kv_cache_config import KVCacheConfig
from benchmark.metrics import BenchmarkMetrics


class TestGenerateVLLMStartupCommand:
    def test_basic_command(self):
        config = KVCacheConfig(
            gpu_memory_utilization=0.85,
            block_size=32,
            max_num_seqs=128,
        )
        cmd = generate_vllm_startup_command(config, "meta-llama/Llama-2-7b")
        assert "python -m vllm.entrypoints.openai.api_server" in cmd
        assert "--model meta-llama/Llama-2-7b" in cmd
        assert "--gpu-memory-utilization=0.85" in cmd
        assert "--block-size=32" in cmd
        assert "--max-num-seqs=128" in cmd

    def test_command_with_custom_host_port(self):
        config = KVCacheConfig()
        cmd = generate_vllm_startup_command(config, "model", host="0.0.0.0", port=9000)
        assert "--host 0.0.0.0" in cmd
        assert "--port 9000" in cmd


class TestPlots:
    @pytest.fixture
    def tuning_result(self):
        config1 = KVCacheConfig(
            gpu_memory_utilization=0.80,
            block_size=16,
            max_num_seqs=32,
        )
        config2 = KVCacheConfig(
            gpu_memory_utilization=0.90,
            block_size=32,
            max_num_seqs=128,
        )

        result = TuningResult()
        result.config_results = [
            ConfigBenchmarkResult(
                config=config1,
                config_label=config1.label(),
                round_number=1,
                success=True,
                metrics=BenchmarkMetrics(
                    total_requests=10,
                    successful_requests=10,
                    throughput_mean=80.0,
                    e2e_latency_p99=1.5,
                ),
                gpu_memory_pct=75.0,
            ),
            ConfigBenchmarkResult(
                config=config2,
                config_label=config2.label(),
                round_number=1,
                success=True,
                metrics=BenchmarkMetrics(
                    total_requests=10,
                    successful_requests=10,
                    throughput_mean=120.0,
                    e2e_latency_p99=1.0,
                ),
                gpu_memory_pct=88.0,
            ),
        ]
        result.optimal_config = config2
        result.optimal_label = config2.label()
        return result

    @pytest.fixture
    def temp_output_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_plot_throughput_vs_config(self, tuning_result, temp_output_dir):
        plot_throughput_vs_config(tuning_result, temp_output_dir)
        assert (temp_output_dir / "kv_cache_throughput_vs_config.png").exists()

    def test_plot_heatmap(self, tuning_result, temp_output_dir):
        plot_heatmap(tuning_result, temp_output_dir)
        assert (temp_output_dir / "kv_cache_heatmap.png").exists()

    def test_plot_performance_gain(self, tuning_result, temp_output_dir):
        plot_performance_gain(tuning_result, temp_output_dir)
        assert (temp_output_dir / "kv_cache_performance_gain.png").exists()

    def test_plot_oom_distribution(self, tuning_result, temp_output_dir):
        plot_oom_distribution(tuning_result, temp_output_dir)
        assert (temp_output_dir / "kv_cache_oom_distribution.png").exists()

    def test_generate_all_plots(self, tuning_result, temp_output_dir):
        generate_all_plots(tuning_result, temp_output_dir)
        assert (temp_output_dir / "kv_cache_throughput_vs_config.png").exists()
        assert (temp_output_dir / "kv_cache_heatmap.png").exists()
        assert (temp_output_dir / "kv_cache_performance_gain.png").exists()
        assert (temp_output_dir / "kv_cache_oom_distribution.png").exists()

    def test_plot_throughput_vs_config_empty(self, temp_output_dir):
        result = TuningResult()
        plot_throughput_vs_config(result, temp_output_dir)

    def test_plot_heatmap_empty(self, temp_output_dir):
        result = TuningResult()
        plot_heatmap(result, temp_output_dir)

    def test_plot_performance_gain_no_optimal(self, temp_output_dir):
        result = TuningResult()
        plot_performance_gain(result, temp_output_dir)

    def test_plot_oom_distribution_empty(self, temp_output_dir):
        result = TuningResult()
        plot_oom_distribution(result, temp_output_dir)


class TestPrintTuningReport:
    @pytest.fixture
    def tuning_result(self):
        config = KVCacheConfig(
            gpu_memory_utilization=0.90,
            block_size=32,
            max_num_seqs=128,
            enable_chunked_prefill=True,
            max_num_batched_tokens=4096,
        )

        result = TuningResult()
        result.config_results = [
            ConfigBenchmarkResult(
                config=config,
                config_label=config.label(),
                round_number=1,
                success=True,
                metrics=BenchmarkMetrics(
                    total_requests=10,
                    successful_requests=10,
                    throughput_mean=120.0,
                    e2e_latency_p99=1.0,
                ),
                gpu_memory_pct=88.0,
            ),
        ]
        result.optimal_config = config
        result.optimal_label = config.label()
        result.total_configs_tested = 18
        result.total_rounds = 54
        result.total_time_s = 3600.0
        return result

    def test_print_tuning_report(self, tuning_result, capsys):
        print_tuning_report(tuning_result)
        captured = capsys.readouterr()
        assert "KV CACHE PARAMETER TUNING REPORT" in captured.out
        assert "OPTIMAL CONFIG" in captured.out
        assert "gpu_memory_utilization" in captured.out
        assert "block_size" in captured.out
        assert "STARTUP COMMAND" in captured.out
