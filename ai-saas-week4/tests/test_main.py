import pytest
import sys
import os
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from benchmark.adapters import InferenceResult, BaseAdapter
from benchmark.metrics import MetricsCalculator, BenchmarkMetrics
from benchmark.main import run_benchmark, print_metrics, run_single_benchmark


class MockAdapter(BaseAdapter):
    def __init__(self, base_url="http://localhost:8000", timeout=300, max_retries=3, retry_delay=1.0):
        super().__init__(base_url, timeout, max_retries, retry_delay)
        self.call_count = 0

    async def generate(self, prompt: str, request_id: str, max_tokens: int = 512) -> InferenceResult:
        self.call_count += 1
        return InferenceResult(
            request_id=request_id,
            prompt_tokens=len(prompt) // 4,
            completion_tokens=max_tokens,
            ttft=0.5,
            tpot=0.02,
            e2e_latency=0.5 + max_tokens * 0.02,
            total_tokens=len(prompt) // 4 + max_tokens,
            throughput=max_tokens / (0.5 + max_tokens * 0.02),
            success=True,
            prompt_length=len(prompt),
            completion_length=max_tokens,
            timestamp=1000.0 + self.call_count
        )

    async def get_gpu_memory(self):
        return 8192.0


class FailingMockAdapter(BaseAdapter):
    def __init__(self, base_url="http://localhost:8000", timeout=300, max_retries=3, retry_delay=1.0):
        super().__init__(base_url, timeout, max_retries, retry_delay)

    async def generate(self, prompt: str, request_id: str, max_tokens: int = 512) -> InferenceResult:
        return InferenceResult(
            request_id=request_id,
            prompt_tokens=0,
            completion_tokens=0,
            ttft=0,
            tpot=0,
            e2e_latency=0.1,
            total_tokens=0,
            throughput=0,
            success=False,
            error="Simulated failure"
        )

    async def get_gpu_memory(self):
        return None


class TestRunBenchmark:
    @pytest.mark.asyncio
    async def test_run_with_mock_adapter(self):
        adapter = MockAdapter()
        prompts = ["test prompt 1", "test prompt 2", "test prompt 3"]

        calculator = await run_benchmark(adapter, prompts, concurrency=2, max_tokens=100)

        assert len(calculator.results) == 3
        for result in calculator.results:
            assert result.success is True
            assert result.ttft == 0.5
            assert result.tpot == 0.02

    @pytest.mark.asyncio
    async def test_run_with_concurrency(self):
        adapter = MockAdapter()
        prompts = ["prompt"] * 20

        calculator = await run_benchmark(adapter, prompts, concurrency=5, max_tokens=50)

        assert len(calculator.results) == 20
        assert adapter.call_count == 20

    @pytest.mark.asyncio
    async def test_run_with_failing_adapter(self):
        adapter = FailingMockAdapter()
        prompts = ["prompt"] * 5

        calculator = await run_benchmark(adapter, prompts, concurrency=2, max_tokens=100)

        assert len(calculator.results) == 5
        for result in calculator.results:
            assert result.success is False
            assert result.error == "Simulated failure"

    @pytest.mark.asyncio
    async def test_run_with_empty_prompts(self):
        adapter = MockAdapter()
        calculator = await run_benchmark(adapter, [], concurrency=1, max_tokens=100)
        assert len(calculator.results) == 0

    @pytest.mark.asyncio
    async def test_run_with_single_prompt(self):
        adapter = MockAdapter()
        calculator = await run_benchmark(adapter, ["single prompt"], concurrency=1, max_tokens=100)
        assert len(calculator.results) == 1

    @pytest.mark.asyncio
    async def test_run_gpu_memory_tracking(self):
        adapter = MockAdapter()
        prompts = ["prompt"] * 3

        calculator = await run_benchmark(
            adapter, prompts, concurrency=1, max_tokens=100, gpu_memory_poll_interval=0.1
        )

        assert calculator.peak_gpu_vram == 8192.0

    @pytest.mark.asyncio
    async def test_run_metrics_calculation(self):
        adapter = MockAdapter()
        prompts = ["prompt"] * 10

        calculator = await run_benchmark(adapter, prompts, concurrency=3, max_tokens=100)
        metrics = calculator.calculate()

        assert metrics.total_requests == 10
        assert metrics.successful_requests == 10
        assert metrics.failed_requests == 0
        assert metrics.success_rate == 1.0
        assert metrics.ttft_mean == 0.5
        assert metrics.tpot_mean == pytest.approx(0.02, abs=0.001)

    @pytest.mark.asyncio
    async def test_run_mixed_success_failure(self):
        class MixedAdapter(BaseAdapter):
            def __init__(self):
                super().__init__("http://localhost:8000")
                self.count = 0

            async def generate(self, prompt, request_id, max_tokens=512):
                self.count += 1
                if self.count % 2 == 0:
                    return InferenceResult(
                        request_id=request_id, prompt_tokens=0, completion_tokens=0,
                        ttft=0, tpot=0, e2e_latency=0, total_tokens=0, throughput=0,
                        success=False, error="Fail"
                    )
                return InferenceResult(
                    request_id=request_id, prompt_tokens=10, completion_tokens=50,
                    ttft=0.3, tpot=0.01, e2e_latency=0.8, total_tokens=60,
                    throughput=75.0, success=True
                )

            async def get_gpu_memory(self):
                return None

        adapter = MixedAdapter()
        prompts = ["prompt"] * 10

        calculator = await run_benchmark(adapter, prompts, concurrency=2, max_tokens=50)
        metrics = calculator.calculate()

        assert metrics.total_requests == 10
        assert metrics.successful_requests == 5
        assert metrics.failed_requests == 5
        assert metrics.success_rate == 0.5


class TestPrintMetrics:
    def test_print_success_metrics(self, capsys):
        metrics = BenchmarkMetrics(
            total_requests=10,
            successful_requests=10,
            failed_requests=0,
            success_rate=1.0,
            ttft_mean=0.5,
            ttft_p50=0.45,
            ttft_p95=0.8,
            ttft_p99=1.2,
            ttft_min=0.1,
            ttft_max=2.0,
            tpot_mean=0.02,
            tpot_p50=0.018,
            tpot_p95=0.03,
            tpot_p99=0.04,
            e2e_latency_mean=2.5,
            e2e_latency_p50=2.3,
            e2e_latency_p95=4.0,
            e2e_latency_p99=5.0,
            throughput_mean=60.0,
            throughput_p50=58.0,
            throughput_p95=70.0,
            throughput_p99=75.0,
            total_tokens=1500,
            avg_tokens_per_request=150.0,
            peak_gpu_vram=8192.0
        )

        print_metrics(metrics, "test-engine")

        captured = capsys.readouterr()
        assert "BENCHMARK RESULTS - TEST-ENGINE" in captured.out
        assert "Total:" in captured.out
        assert "Success:" in captured.out
        assert "TTFT" in captured.out
        assert "TPOT" in captured.out
        assert "End-to-End Latency" in captured.out
        assert "Throughput" in captured.out
        assert "Peak GPU VRAM" in captured.out

    def test_print_no_gpu_memory(self, capsys):
        metrics = BenchmarkMetrics(
            total_requests=5,
            successful_requests=5,
            failed_requests=0,
            success_rate=1.0,
            ttft_mean=0.3,
            tpot_mean=0.01,
            e2e_latency_mean=1.0,
            throughput_mean=50.0,
            total_tokens=500,
            avg_tokens_per_request=100.0
        )

        print_metrics(metrics, "no-gpu")
        captured = capsys.readouterr()
        assert "Peak GPU VRAM" not in captured.out

    def test_print_failed_requests(self, capsys):
        metrics = BenchmarkMetrics(
            total_requests=10,
            successful_requests=7,
            failed_requests=3,
            success_rate=0.7,
            ttft_mean=0.5,
            tpot_mean=0.02,
            e2e_latency_mean=2.0,
            throughput_mean=50.0,
            total_tokens=700,
            avg_tokens_per_request=100.0
        )

        print_metrics(metrics, "partial-fail")
        captured = capsys.readouterr()
        assert "Failed:" in captured.out
        assert "70.0%" in captured.out


class TestRunSingleBenchmark:
    @pytest.mark.asyncio
    async def test_run_single_benchmark(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            with patch('benchmark.main.get_adapter') as mock_get_adapter:
                mock_get_adapter.return_value = MockAdapter()

                metrics = await run_single_benchmark(
                    engine="vllm",
                    base_url="http://localhost:8000",
                    prompt_length="short",
                    total_requests=5,
                    concurrency=2,
                    max_tokens=100,
                    timeout=300,
                    output_dir=output_dir
                )

                assert metrics.total_requests == 5
                assert metrics.successful_requests == 5
                assert metrics.success_rate == 1.0

                csv_path = output_dir / "vllm_results.csv"
                assert csv_path.exists()

    @pytest.mark.asyncio
    async def test_run_single_benchmark_creates_csv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            with patch('benchmark.main.get_adapter') as mock_get_adapter:
                mock_get_adapter.return_value = MockAdapter()

                await run_single_benchmark(
                    engine="ollama",
                    base_url="http://localhost:11434",
                    prompt_length="medium",
                    total_requests=3,
                    concurrency=1,
                    max_tokens=50,
                    timeout=300,
                    output_dir=output_dir
                )

                csv_path = output_dir / "ollama_results.csv"
                assert csv_path.exists()

                import pandas as pd
                df = pd.read_csv(csv_path)
                assert len(df) == 3
                assert all(df['success'] == True)


class TestMainModule:
    def test_main_module_imports(self):
        import benchmark.main
        assert hasattr(benchmark.main, 'run_benchmark')
        assert hasattr(benchmark.main, 'print_metrics')
        assert hasattr(benchmark.main, 'run_single_benchmark')
        assert hasattr(benchmark.main, 'run_comparison_benchmark')
        assert hasattr(benchmark.main, 'main')

    def test_main_module_cli_help(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, '-m', 'benchmark.main', '--help'],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), '..')
        )
        assert result.returncode == 0
        assert '--engine' in result.stdout
        assert '--compare' in result.stdout
        assert '--concurrency' in result.stdout
        assert '--total-requests' in result.stdout
