import pytest
import asyncio
import tempfile
import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock, call

from benchmark.kv_cache_tuner import run_tuning, parse_args
from benchmark.kv_cache_config import (
    KVCacheConfig,
    GridSearchConfig,
    SafetyThresholds,
)
from benchmark.vllm_lifecycle import VLLMLifecycleManager, VLLMInstance
from benchmark.prefill_adjuster import PrefillAdjuster
from benchmark.kv_cache_runner import (
    KVCacheBenchmarkRunner,
    TuningResult,
    ConfigBenchmarkResult,
)
from benchmark.adapters import InferenceResult
from benchmark.metrics import BenchmarkMetrics
from benchmark.gpu_scanner import GPUScanResult, GPUInfo


class TestKVCacheTunerE2E:
    @pytest.fixture
    def mock_gpu_scan(self):
        return GPUScanResult(
            gpus=[GPUInfo(
                index=0,
                name="NVIDIA A100-SXM4-80GB",
                memory_total_mb=81920,
                memory_free_mb=70000,
                memory_used_mb=11920,
                utilization_pct=0,
                temperature_c=45,
            )],
            total_gpu_count=1,
            total_memory_mb=81920,
            cuda_available=True,
            cuda_version="12.4",
            driver_version="550.54.15",
            nvidia_smi_available=True,
        )

    @pytest.fixture
    def mock_inference_result(self):
        return InferenceResult(
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

    @pytest.mark.asyncio
    async def test_full_tuning_pipeline(self, mock_gpu_scan, mock_inference_result):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "results"

            with patch("benchmark.kv_cache_tuner.scan_gpus", return_value=mock_gpu_scan):
                with patch("benchmark.kv_cache_runner.VLLMAdapter") as mock_adapter_cls:
                    mock_adapter = MagicMock()
                    mock_adapter.generate = AsyncMock(return_value=mock_inference_result)
                    mock_adapter_cls.return_value = mock_adapter

                    with patch("benchmark.kv_cache_runner.get_gpu_memory_usage_pct", return_value=85.0):
                        lifecycle = VLLMLifecycleManager(
                            model="test-model",
                            port=8000,
                            host="127.0.0.1",
                            health_check_timeout=1.0,
                            health_check_interval=0.1,
                        )

                        safety = SafetyThresholds(
                            gpu_memory_pct_max=92.0,
                            p99_latency_max_s=2.0,
                            consecutive_oom_max=2,
                        )

                        prefill_adjuster = PrefillAdjuster()

                        runner = KVCacheBenchmarkRunner(
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

                        grid = GridSearchConfig(
                            gpu_memory_utilization_values=[0.80, 0.90],
                            block_size_values=[16],
                            max_num_seqs_values=[32],
                            enable_chunked_prefill_values=[False],
                            max_num_batched_tokens_values=[None],
                        )
                        configs = grid.generate_combinations()

                        with patch.object(runner.lifecycle, "start") as mock_start:
                            with patch.object(runner.lifecycle, "wait_until_ready", new_callable=AsyncMock) as mock_ready:
                                with patch.object(runner.lifecycle, "stop") as mock_stop:
                                    instance = VLLMInstance(
                                        config=configs[0],
                                        port=8000,
                                        host="127.0.0.1",
                                        model="test-model",
                                    )
                                    mock_start.return_value = instance
                                    mock_ready.return_value = True

                                    tuning_result = await runner.run_all_configs(configs)
                                    tuning_result = runner.find_optimal_config(tuning_result)
                                    tuning_result.gpu_info = {
                                        "gpu_count": mock_gpu_scan.total_gpu_count,
                                        "total_memory_mb": mock_gpu_scan.total_memory_mb,
                                        "cuda_version": mock_gpu_scan.cuda_version,
                                    }

                                    assert tuning_result.total_configs_tested >= 2
                                    assert tuning_result.optimal_config is not None
                                    assert tuning_result.gpu_info["gpu_count"] == 1

                                    from benchmark.kv_cache_visualization import (
                                        generate_all_plots,
                                        print_tuning_report,
                                        generate_vllm_startup_command,
                                    )

                                    generate_all_plots(tuning_result, output_dir)
                                    assert (output_dir / "kv_cache_throughput_vs_config.png").exists()

                                    cmd = generate_vllm_startup_command(
                                        tuning_result.optimal_config,
                                        "test-model",
                                    )
                                    assert "python -m vllm.entrypoints.openai.api_server" in cmd

                                    results_json = {
                                        "optimal_config": tuning_result.optimal_config.to_dict(),
                                        "optimal_label": tuning_result.optimal_label,
                                        "total_configs_tested": tuning_result.total_configs_tested,
                                        "total_rounds": tuning_result.total_rounds,
                                        "total_time_s": tuning_result.total_time_s,
                                    }
                                    json_path = output_dir / "tuning_results.json"
                                    with open(json_path, "w") as f:
                                        json.dump(results_json, f, indent=2)
                                    assert json_path.exists()

    @pytest.mark.asyncio
    async def test_tuning_with_safety_termination(self, mock_gpu_scan, mock_inference_result):
        lifecycle = VLLMLifecycleManager(
            model="test-model",
            port=8000,
            host="127.0.0.1",
            health_check_timeout=1.0,
            health_check_interval=0.1,
        )

        safety = SafetyThresholds(
            gpu_memory_pct_max=92.0,
            p99_latency_max_s=2.0,
            consecutive_oom_max=2,
        )

        prefill_adjuster = PrefillAdjuster()

        runner = KVCacheBenchmarkRunner(
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

        config = KVCacheConfig(
            gpu_memory_utilization=0.95,
            block_size=16,
            max_num_seqs=256,
        )

        with patch("benchmark.kv_cache_runner.VLLMAdapter") as mock_adapter_cls:
            mock_adapter = MagicMock()
            mock_adapter.generate = AsyncMock(return_value=mock_inference_result)
            mock_adapter_cls.return_value = mock_adapter

            with patch("benchmark.kv_cache_runner.get_gpu_memory_usage_pct", return_value=95.0):
                instance = VLLMInstance(
                    config=config,
                    port=8000,
                    host="127.0.0.1",
                    model="test-model",
                )
                result = await runner.run_single_round(config, instance, 1)
                assert result.terminated_by_safety is True
                assert "GPU memory" in result.termination_reason

    @pytest.mark.asyncio
    async def test_tuning_with_oom_handling(self, mock_gpu_scan):
        lifecycle = VLLMLifecycleManager(
            model="test-model",
            port=8000,
            host="127.0.0.1",
            health_check_timeout=1.0,
            health_check_interval=0.1,
        )

        safety = SafetyThresholds(
            gpu_memory_pct_max=92.0,
            p99_latency_max_s=2.0,
            consecutive_oom_max=2,
        )

        prefill_adjuster = PrefillAdjuster()

        runner = KVCacheBenchmarkRunner(
            lifecycle=lifecycle,
            safety=safety,
            prefill_adjuster=prefill_adjuster,
            rounds_per_config=3,
            prompts_per_round=3,
            concurrency=1,
            max_tokens=64,
            timeout=30,
            cooldown_between_configs=0.01,
        )

        config = KVCacheConfig(
            gpu_memory_utilization=0.90,
            block_size=16,
            max_num_seqs=128,
        )

        oom_result = InferenceResult(
            request_id="test",
            prompt_tokens=0,
            completion_tokens=0,
            ttft=0,
            tpot=0,
            e2e_latency=0.1,
            total_tokens=0,
            throughput=0,
            success=False,
            error="CUDA OUT OF MEMORY",
        )

        with patch("benchmark.kv_cache_runner.VLLMAdapter") as mock_adapter_cls:
            mock_adapter = MagicMock()
            mock_adapter.generate = AsyncMock(return_value=oom_result)
            mock_adapter_cls.return_value = mock_adapter

            with patch("benchmark.kv_cache_runner.get_gpu_memory_usage_pct", return_value=90.0):
                instance = VLLMInstance(
                    config=config,
                    port=8000,
                    host="127.0.0.1",
                    model="test-model",
                )
                results = await runner.run_config_rounds(config, instance)
                assert len(results) >= 1
                assert results[0].oom_count > 0

    @pytest.mark.asyncio
    async def test_tuning_with_startup_failure(self, mock_gpu_scan):
        lifecycle = VLLMLifecycleManager(
            model="test-model",
            port=8000,
            host="127.0.0.1",
            health_check_timeout=1.0,
            health_check_interval=0.1,
        )

        safety = SafetyThresholds()
        prefill_adjuster = PrefillAdjuster()

        runner = KVCacheBenchmarkRunner(
            lifecycle=lifecycle,
            safety=safety,
            prefill_adjuster=prefill_adjuster,
            rounds_per_config=1,
            prompts_per_round=3,
            concurrency=1,
            max_tokens=64,
            timeout=30,
        )

        config = KVCacheConfig(
            gpu_memory_utilization=0.99,
            block_size=16,
            max_num_seqs=512,
        )

        with patch.object(runner.lifecycle, "start") as mock_start:
            with patch.object(runner.lifecycle, "wait_until_ready", new_callable=AsyncMock) as mock_ready:
                with patch.object(runner.lifecycle, "stop") as mock_stop:
                    instance = VLLMInstance(
                        config=config,
                        port=8000,
                        host="127.0.0.1",
                        model="test-model",
                        errors=["CUDA out of memory during model loading"],
                    )
                    mock_start.return_value = instance
                    mock_ready.return_value = False

                    result = await runner.run_all_configs([config])
                    assert len(result.config_results) == 1
                    assert not result.config_results[0].success

    @pytest.mark.asyncio
    async def test_end_to_end_with_multiple_configs(self, mock_gpu_scan, mock_inference_result):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "results"

            lifecycle = VLLMLifecycleManager(
                model="test-model",
                port=8000,
                host="127.0.0.1",
                health_check_timeout=1.0,
                health_check_interval=0.1,
            )

            safety = SafetyThresholds(
                gpu_memory_pct_max=92.0,
                p99_latency_max_s=2.0,
                consecutive_oom_max=2,
            )

            prefill_adjuster = PrefillAdjuster()

            runner = KVCacheBenchmarkRunner(
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

            grid = GridSearchConfig(
                gpu_memory_utilization_values=[0.80, 0.85, 0.90],
                block_size_values=[16, 32],
                max_num_seqs_values=[32, 64, 128],
                enable_chunked_prefill_values=[False],
                max_num_batched_tokens_values=[None],
            )
            configs = grid.generate_combinations()

            with patch("benchmark.kv_cache_runner.VLLMAdapter") as mock_adapter_cls:
                mock_adapter = MagicMock()
                mock_adapter.generate = AsyncMock(return_value=mock_inference_result)
                mock_adapter_cls.return_value = mock_adapter

                with patch("benchmark.kv_cache_runner.get_gpu_memory_usage_pct", return_value=85.0):
                    with patch.object(runner.lifecycle, "start") as mock_start:
                        with patch.object(runner.lifecycle, "wait_until_ready", new_callable=AsyncMock) as mock_ready:
                            with patch.object(runner.lifecycle, "stop") as mock_stop:
                                instance = VLLMInstance(
                                    config=configs[0],
                                    port=8000,
                                    host="127.0.0.1",
                                    model="test-model",
                                )
                                mock_start.return_value = instance
                                mock_ready.return_value = True

                                tuning_result = await runner.run_all_configs(configs)
                                tuning_result = runner.find_optimal_config(tuning_result)

                                assert tuning_result.total_configs_tested == len(configs)
                                assert tuning_result.optimal_config is not None

                                from benchmark.kv_cache_visualization import generate_all_plots
                                generate_all_plots(tuning_result, output_dir)

                                assert (output_dir / "kv_cache_throughput_vs_config.png").exists()
                                assert (output_dir / "kv_cache_heatmap.png").exists()
                                assert (output_dir / "kv_cache_performance_gain.png").exists()
                                assert (output_dir / "kv_cache_oom_distribution.png").exists()

    def test_cli_argument_parsing(self):
        import sys
        test_args = [
            "kv_cache_tuner",
            "--model", "meta-llama/Llama-2-7b",
            "--port", "9000",
            "--rounds", "2",
            "--prompts", "20",
            "--concurrency", "4",
            "--output-dir", "/tmp/test_output",
            "--no-plots",
        ]

        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.model == "meta-llama/Llama-2-7b"
            assert args.port == 9000
            assert args.rounds == 2
            assert args.prompts == 20
            assert args.concurrency == 4
            assert args.output_dir == "/tmp/test_output"
            assert args.no_plots is True

    def test_cli_default_values(self):
        import sys
        test_args = [
            "kv_cache_tuner",
            "--model", "test-model",
        ]

        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.gmu_values == [0.80, 0.85, 0.90]
            assert args.bs_values == [16, 32]
            assert args.mns_values == [32, 64, 128]
            assert args.rounds == 3
            assert args.prompts == 50
            assert args.concurrency == 8
            assert args.gpu_mem_max == 92.0
            assert args.p99_latency_max == 2.0

    def test_vllm_startup_command_template(self):
        from benchmark.kv_cache_visualization import generate_vllm_startup_command

        config = KVCacheConfig(
            gpu_memory_utilization=0.90,
            block_size=32,
            max_num_seqs=128,
            enable_chunked_prefill=True,
            max_num_batched_tokens=4096,
            enable_prefix_caching=True,
        )

        cmd = generate_vllm_startup_command(config, "meta-llama/Llama-2-7b-hf")
        assert "python -m vllm.entrypoints.openai.api_server" in cmd
        assert "--model meta-llama/Llama-2-7b-hf" in cmd
        assert "--gpu-memory-utilization=0.9" in cmd
        assert "--block-size=32" in cmd
        assert "--max-num-seqs=128" in cmd
        assert "--enable-chunked-prefill" in cmd
        assert "--max-num-batched-tokens=4096" in cmd
        assert "--enable-prefix-caching" in cmd

    def test_acceptance_criteria_verification(self):
        baseline = KVCacheConfig(
            gpu_memory_utilization=0.80,
            block_size=16,
            max_num_seqs=32,
        )
        optimal = KVCacheConfig(
            gpu_memory_utilization=0.90,
            block_size=32,
            max_num_seqs=128,
            enable_chunked_prefill=True,
            max_num_batched_tokens=4096,
        )

        capacity_improvement = (optimal.max_num_seqs - baseline.max_num_seqs) / baseline.max_num_seqs * 100
        assert capacity_improvement > 30, f"Capacity improvement {capacity_improvement:.1f}% <= 30%"

        assert optimal.gpu_memory_utilization > 0.80, "GPU memory utilization <= 80%"

        safety = SafetyThresholds()
        assert safety.is_safe(88.0, 1.5, 0), "Safety check should pass for optimal config"

        assert optimal.enable_chunked_prefill, "Chunked prefill should be enabled for long text optimization"
