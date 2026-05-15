import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from benchmark.kv_cache_runner import (
    KVCacheBenchmarkRunner,
    ConfigBenchmarkResult,
    TuningResult,
)
from benchmark.kv_cache_config import KVCacheConfig, SafetyThresholds
from benchmark.vllm_lifecycle import VLLMLifecycleManager, VLLMInstance
from benchmark.prefill_adjuster import PrefillAdjuster
from benchmark.adapters import InferenceResult
from benchmark.metrics import BenchmarkMetrics


class TestConfigBenchmarkResult:
    def test_default_values(self):
        config = KVCacheConfig()
        result = ConfigBenchmarkResult(config=config, config_label=config.label())
        assert result.config == config
        assert result.round_number == 0
        assert result.metrics is None
        assert result.oom_count == 0
        assert result.success is False

    def test_with_metrics(self):
        config = KVCacheConfig()
        metrics = BenchmarkMetrics(
            total_requests=10,
            successful_requests=10,
            throughput_mean=100.0,
            e2e_latency_p99=1.5,
        )
        result = ConfigBenchmarkResult(
            config=config,
            config_label=config.label(),
            metrics=metrics,
            success=True,
            gpu_memory_pct=85.0,
            p99_latency_s=1.5,
        )
        assert result.success is True
        assert result.metrics.throughput_mean == 100.0
        assert result.gpu_memory_pct == 85.0


class TestTuningResult:
    def test_default_values(self):
        result = TuningResult()
        assert result.config_results == []
        assert result.optimal_config is None
        assert result.total_configs_tested == 0


class TestKVCacheBenchmarkRunner:
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
            oom_max_per_round=0,
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
            rounds_per_config=2,
            prompts_per_round=5,
            concurrency=2,
            max_tokens=128,
            timeout=60,
            cooldown_between_configs=0.1,
        )

    @pytest.fixture
    def config(self):
        return KVCacheConfig(
            gpu_memory_utilization=0.85,
            block_size=16,
            max_num_seqs=64,
        )

    @pytest.fixture
    def instance(self, config):
        return VLLMInstance(
            config=config,
            port=8000,
            host="127.0.0.1",
            model="test-model",
        )

    @pytest.mark.asyncio
    async def test_run_single_round_success(self, runner, config, instance):
        mock_result = InferenceResult(
            request_id="test_0",
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

            with patch("benchmark.kv_cache_runner.get_gpu_memory_usage_pct", return_value=80.0):
                result = await runner.run_single_round(config, instance, 1)

                assert result.config == config
                assert result.round_number == 1
                assert result.success is True
                assert result.metrics is not None
                assert result.gpu_memory_pct == 80.0
                assert result.terminated_by_safety is False

    @pytest.mark.asyncio
    async def test_run_single_round_safety_terminated_gpu(self, runner, config, instance):
        mock_result = InferenceResult(
            request_id="test_0",
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

            with patch("benchmark.kv_cache_runner.get_gpu_memory_usage_pct", return_value=95.0):
                result = await runner.run_single_round(config, instance, 1)

                assert result.terminated_by_safety is True
                assert "GPU memory" in result.termination_reason

    @pytest.mark.asyncio
    async def test_run_single_round_safety_terminated_p99(self, runner, config, instance):
        mock_result = InferenceResult(
            request_id="test_0",
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

            with patch("benchmark.kv_cache_runner.get_gpu_memory_usage_pct", return_value=80.0):
                result = await runner.run_single_round(config, instance, 1)

                assert result.terminated_by_safety is True
                assert "P99 latency" in result.termination_reason

    @pytest.mark.asyncio
    async def test_run_single_round_with_oom(self, runner, config, instance):
        mock_result = InferenceResult(
            request_id="test_0",
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
            mock_adapter.generate = AsyncMock(return_value=mock_result)
            mock_adapter_cls.return_value = mock_adapter

            with patch("benchmark.kv_cache_runner.get_gpu_memory_usage_pct", return_value=80.0):
                result = await runner.run_single_round(config, instance, 1)

                assert result.oom_count > 0

    @pytest.mark.asyncio
    async def test_run_config_rounds_breaks_on_safety(self, runner, config, instance):
        call_count = 0

        async def mock_run_single_round(config, instance, round_num):
            nonlocal call_count
            call_count += 1
            result = ConfigBenchmarkResult(
                config=config,
                config_label=config.label(),
                round_number=round_num,
                terminated_by_safety=(round_num == 1),
                termination_reason="GPU memory 95% > 92%" if round_num == 1 else "",
            )
            return result

        with patch.object(runner, "run_single_round", side_effect=mock_run_single_round):
            results = await runner.run_config_rounds(config, instance)
            assert len(results) == 1

    @pytest.mark.asyncio
    async def test_run_config_rounds_breaks_on_consecutive_oom(self, runner, config, instance):
        call_count = 0

        async def mock_run_single_round(config, instance, round_num):
            nonlocal call_count
            call_count += 1
            return ConfigBenchmarkResult(
                config=config,
                config_label=config.label(),
                round_number=round_num,
                oom_count=1,
            )

        with patch.object(runner, "run_single_round", side_effect=mock_run_single_round):
            results = await runner.run_config_rounds(config, instance)
            assert len(results) == 2

    @pytest.mark.asyncio
    async def test_run_all_configs(self, runner, config):
        with patch.object(runner.lifecycle, "start") as mock_start:
            with patch.object(runner.lifecycle, "wait_until_ready", new_callable=AsyncMock) as mock_ready:
                with patch.object(runner.lifecycle, "stop") as mock_stop:
                    with patch.object(runner, "run_config_rounds", new_callable=AsyncMock) as mock_rounds:
                        instance = VLLMInstance(
                            config=config,
                            port=8000,
                            host="127.0.0.1",
                            model="test-model",
                        )
                        mock_start.return_value = instance
                        mock_ready.return_value = True
                        mock_rounds.return_value = [
                            ConfigBenchmarkResult(
                                config=config,
                                config_label=config.label(),
                                round_number=1,
                                success=True,
                                metrics=BenchmarkMetrics(throughput_mean=100.0, e2e_latency_p99=1.0),
                                gpu_memory_pct=85.0,
                            )
                        ]

                        result = await runner.run_all_configs([config])
                        assert result.total_configs_tested == 1
                        assert len(result.config_results) == 1

    @pytest.mark.asyncio
    async def test_run_all_configs_startup_failure(self, runner, config):
        with patch.object(runner.lifecycle, "start") as mock_start:
            with patch.object(runner.lifecycle, "wait_until_ready", new_callable=AsyncMock) as mock_ready:
                with patch.object(runner.lifecycle, "stop") as mock_stop:
                    instance = VLLMInstance(
                        config=config,
                        port=8000,
                        host="127.0.0.1",
                        model="test-model",
                        errors=["Failed to start"],
                    )
                    mock_start.return_value = instance
                    mock_ready.return_value = False

                    result = await runner.run_all_configs([config])
                    assert len(result.config_results) == 1
                    assert not result.config_results[0].success

    def test_find_optimal_config(self, runner, config):
        config2 = KVCacheConfig(
            gpu_memory_utilization=0.90,
            block_size=32,
            max_num_seqs=128,
        )

        tuning_result = TuningResult()
        tuning_result.config_results = [
            ConfigBenchmarkResult(
                config=config,
                config_label=config.label(),
                round_number=1,
                success=True,
                metrics=BenchmarkMetrics(throughput_mean=80.0, e2e_latency_p99=1.5),
                gpu_memory_pct=80.0,
            ),
            ConfigBenchmarkResult(
                config=config2,
                config_label=config2.label(),
                round_number=1,
                success=True,
                metrics=BenchmarkMetrics(throughput_mean=120.0, e2e_latency_p99=1.0),
                gpu_memory_pct=88.0,
            ),
        ]

        result = runner.find_optimal_config(tuning_result)
        assert result.optimal_config is not None
        assert result.optimal_label == config2.label()

    def test_find_optimal_config_excludes_oom(self, runner, config):
        config2 = KVCacheConfig(
            gpu_memory_utilization=0.90,
            block_size=32,
            max_num_seqs=128,
        )

        tuning_result = TuningResult()
        tuning_result.config_results = [
            ConfigBenchmarkResult(
                config=config,
                config_label=config.label(),
                round_number=1,
                success=True,
                metrics=BenchmarkMetrics(throughput_mean=80.0, e2e_latency_p99=1.5),
                gpu_memory_pct=80.0,
                oom_count=0,
            ),
            ConfigBenchmarkResult(
                config=config2,
                config_label=config2.label(),
                round_number=1,
                success=True,
                metrics=BenchmarkMetrics(throughput_mean=200.0, e2e_latency_p99=0.5),
                gpu_memory_pct=95.0,
                oom_count=3,
            ),
        ]

        result = runner.find_optimal_config(tuning_result)
        assert result.optimal_label == config.label()
