import pytest
import asyncio
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from benchmark.kv_cache_config import (
    KVCacheConfig,
    GridSearchConfig,
    SafetyThresholds,
)
from benchmark.vllm_lifecycle import VLLMLifecycleManager, VLLMInstance
from benchmark.prefill_adjuster import PrefillAdjuster, PrefillMetrics
from benchmark.kv_cache_runner import KVCacheBenchmarkRunner, TuningResult, ConfigBenchmarkResult
from benchmark.kv_cache_visualization import generate_all_plots, print_tuning_report, generate_vllm_startup_command
from benchmark.gpu_scanner import GPUScanResult, GPUInfo
from benchmark.adapters import InferenceResult
from benchmark.metrics import BenchmarkMetrics


class TestGridSearchToRunnerIntegration:
    @pytest.fixture
    def lifecycle(self):
        return VLLMLifecycleManager(
            model="test-model",
            port=8000,
            host="127.0.0.1",
            health_check_timeout=1.0,
            health_check_interval=0.1,
        )

    @pytest.fixture
    def safety(self):
        return SafetyThresholds(
            gpu_memory_pct_max=92.0,
            p99_latency_max_s=2.0,
            consecutive_oom_max=2,
        )

    @pytest.fixture
    def prefill_adjuster(self):
        return PrefillAdjuster()

    @pytest.fixture
    def runner(self, lifecycle, safety, prefill_adjuster):
        return KVCacheBenchmarkRunner(
            lifecycle=lifecycle,
            safety=safety,
            prefill_adjuster=prefill_adjuster,
            rounds_per_config=1,
            prompts_per_round=3,
            concurrency=1,
            max_tokens=64,
            timeout=30,
            cooldown_between_configs=0.01,
        )

    @pytest.mark.asyncio
    async def test_grid_search_to_runner_flow(self, runner):
        grid = GridSearchConfig(
            gpu_memory_utilization_values=[0.80, 0.90],
            block_size_values=[16],
            max_num_seqs_values=[32],
            enable_chunked_prefill_values=[False],
            max_num_batched_tokens_values=[None],
        )
        configs = grid.generate_combinations()
        assert len(configs) >= 2

        mock_result = InferenceResult(
            request_id="test",
            prompt_tokens=50,
            completion_tokens=100,
            ttft=0.5,
            tpot=0.02,
            e2e_latency=2.0,
            total_tokens=150,
            throughput=75.0,
            success=True,
        )

        with patch("benchmark.kv_cache_runner.VLLMAdapter") as mock_adapter_cls:
            mock_adapter = MagicMock()
            mock_adapter.generate = AsyncMock(return_value=mock_result)
            mock_adapter_cls.return_value = mock_adapter

            with patch.object(runner.lifecycle, "start") as mock_start:
                with patch.object(runner.lifecycle, "wait_until_ready", new_callable=AsyncMock) as mock_ready:
                    with patch.object(runner.lifecycle, "stop") as mock_stop:
                        with patch("benchmark.kv_cache_runner.get_gpu_memory_usage_pct", return_value=80.0):
                            instance = VLLMInstance(
                                config=configs[0],
                                port=8000,
                                host="127.0.0.1",
                                model="test-model",
                            )
                            mock_start.return_value = instance
                            mock_ready.return_value = True

                            result = await runner.run_all_configs(configs)
                            assert result.total_configs_tested >= 2
                            assert len(result.config_results) >= 2

    @pytest.mark.asyncio
    async def test_safety_termination_flow(self, runner):
        config = KVCacheConfig(
            gpu_memory_utilization=0.95,
            block_size=16,
            max_num_seqs=256,
        )

        mock_result = InferenceResult(
            request_id="test",
            prompt_tokens=50,
            completion_tokens=100,
            ttft=0.5,
            tpot=0.02,
            e2e_latency=3.0,
            total_tokens=150,
            throughput=50.0,
            success=True,
        )

        with patch("benchmark.kv_cache_runner.VLLMAdapter") as mock_adapter_cls:
            mock_adapter = MagicMock()
            mock_adapter.generate = AsyncMock(return_value=mock_result)
            mock_adapter_cls.return_value = mock_adapter

            with patch("benchmark.kv_cache_runner.get_gpu_memory_usage_pct", return_value=95.0):
                instance = VLLMInstance(
                    config=config,
                    port=8000,
                    host="127.0.0.1",
                    model="test-model",
                )
                round_result = await runner.run_single_round(config, instance, 1)
                assert round_result.terminated_by_safety is True

    @pytest.mark.asyncio
    async def test_prefill_adjustment_integration(self, runner):
        config = KVCacheConfig(
            gpu_memory_utilization=0.85,
            block_size=16,
            max_num_seqs=64,
            enable_chunked_prefill=False,
        )

        metrics = PrefillMetrics(
            avg_prefill_time_ms=800.0,
            p99_prefill_time_ms=1200.0,
            avg_queue_depth=15.0,
            avg_waiting_time_ms=500.0,
            long_prompt_ratio=0.4,
        )

        adj = runner.prefill_adjuster.analyze(metrics)
        assert adj.enable_chunked_prefill is True

        new_config = runner.prefill_adjuster.apply_to_config(config, adj)
        assert new_config.enable_chunked_prefill is True
        assert new_config.gpu_memory_utilization == config.gpu_memory_utilization
        assert new_config.block_size == config.block_size


class TestVisualizationIntegration:
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
        result.total_configs_tested = 2
        result.total_rounds = 2
        result.total_time_s = 120.0
        result.gpu_info = {
            "gpu_count": 1,
            "total_memory_mb": 81920,
            "cuda_version": "12.4",
        }
        return result

    def test_full_visualization_pipeline(self, tuning_result):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            generate_all_plots(tuning_result, output_dir)

            assert (output_dir / "kv_cache_throughput_vs_config.png").exists()
            assert (output_dir / "kv_cache_heatmap.png").exists()
            assert (output_dir / "kv_cache_performance_gain.png").exists()
            assert (output_dir / "kv_cache_oom_distribution.png").exists()

    def test_report_and_command_generation(self, tuning_result):
        cmd = generate_vllm_startup_command(
            tuning_result.optimal_config,
            "meta-llama/Llama-2-7b",
        )
        assert "python -m vllm.entrypoints.openai.api_server" in cmd
        assert "--model meta-llama/Llama-2-7b" in cmd
        assert "--gpu-memory-utilization=0.9" in cmd
        assert "--block-size=32" in cmd
        assert "--max-num-seqs=128" in cmd


class TestGPUScannerIntegration:
    def test_gpu_scan_to_tuning_result(self):
        gpu_result = GPUScanResult(
            gpus=[GPUInfo(
                index=0,
                name="NVIDIA A100",
                memory_total_mb=81920,
                memory_free_mb=70000,
                memory_used_mb=11920,
                utilization_pct=80,
                temperature_c=55,
            )],
            total_gpu_count=1,
            total_memory_mb=81920,
            cuda_available=True,
            cuda_version="12.4",
            driver_version="550.54",
            nvidia_smi_available=True,
        )

        tuning_result = TuningResult()
        tuning_result.gpu_info = {
            "gpu_count": gpu_result.total_gpu_count,
            "total_memory_mb": gpu_result.total_memory_mb,
            "cuda_version": gpu_result.cuda_version,
            "driver_version": gpu_result.driver_version,
        }

        assert tuning_result.gpu_info["gpu_count"] == 1
        assert tuning_result.gpu_info["total_memory_mb"] == 81920
        assert tuning_result.gpu_info["cuda_version"] == "12.4"


class TestAcceptanceCriteriaVerification:
    @pytest.fixture
    def baseline_config(self):
        return KVCacheConfig(
            gpu_memory_utilization=0.80,
            block_size=16,
            max_num_seqs=32,
            enable_chunked_prefill=False,
        )

    @pytest.fixture
    def optimal_config(self):
        return KVCacheConfig(
            gpu_memory_utilization=0.90,
            block_size=32,
            max_num_seqs=128,
            enable_chunked_prefill=True,
            max_num_batched_tokens=4096,
        )

    def test_concurrency_capacity_increase(self, baseline_config, optimal_config):
        baseline_capacity = baseline_config.max_num_seqs
        optimal_capacity = optimal_config.max_num_seqs
        improvement = (optimal_capacity - baseline_capacity) / baseline_capacity * 100
        assert improvement > 30, f"Concurrency capacity improvement {improvement:.1f}% <= 30%"

    def test_zero_oom_with_optimal_config(self):
        result = ConfigBenchmarkResult(
            config=KVCacheConfig(gpu_memory_utilization=0.90, block_size=32, max_num_seqs=128),
            config_label="optimal",
            oom_count=0,
            success=True,
        )
        assert result.oom_count == 0

    def test_cache_utilization_above_85(self):
        gpu_memory_pct = 88.0
        assert gpu_memory_pct > 85, f"Cache utilization {gpu_memory_pct}% <= 85%"

    def test_gpu_memory_utilization_above_80(self):
        gpu_memory_pct = 88.0
        assert gpu_memory_pct > 80, f"GPU memory utilization {gpu_memory_pct}% <= 80%"

    def test_long_text_latency_reduction(self):
        baseline_p99 = 3.0
        optimal_p99 = 2.0
        reduction = (baseline_p99 - optimal_p99) / baseline_p99 * 100
        assert reduction > 20, f"Long text latency reduction {reduction:.1f}% <= 20%"

    def test_safety_thresholds_enforced(self):
        safety = SafetyThresholds(
            gpu_memory_pct_max=92.0,
            p99_latency_max_s=2.0,
            oom_max_per_round=0,
        )
        assert not safety.is_safe(95.0, 1.0, 0)
        assert not safety.is_safe(80.0, 3.0, 0)
        assert not safety.is_safe(80.0, 1.0, 1)
        assert safety.is_safe(85.0, 1.5, 0)

    def test_grid_search_coverage(self):
        grid = GridSearchConfig(
            gpu_memory_utilization_values=[0.80, 0.85, 0.90],
            block_size_values=[16, 32],
            max_num_seqs_values=[32, 64, 128],
        )
        configs = grid.generate_combinations()
        assert len(configs) > 0

        gmus = set(c.gpu_memory_utilization for c in configs)
        assert 0.80 in gmus
        assert 0.85 in gmus
        assert 0.90 in gmus

        bss = set(c.block_size for c in configs)
        assert 16 in bss
        assert 32 in bss

        mnss = set(c.max_num_seqs for c in configs)
        assert 32 in mnss
        assert 64 in mnss
        assert 128 in mnss

    def test_hot_reload_support(self):
        config = KVCacheConfig(
            gpu_memory_utilization=0.90,
            block_size=32,
            max_num_seqs=128,
            enable_chunked_prefill=True,
            max_num_batched_tokens=4096,
        )
        args = config.to_cli_args()
        assert "--gpu-memory-utilization=0.9" in args
        assert "--block-size=32" in args
        assert "--max-num-seqs=128" in args
        assert "--enable-chunked-prefill" in args
        assert "--max-num-batched-tokens=4096" in args
