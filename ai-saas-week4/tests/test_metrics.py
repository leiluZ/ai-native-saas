import pytest
import sys
import os
import numpy as np
import pandas as pd
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from benchmark.adapters import InferenceResult
from benchmark.metrics import (
    BenchmarkMetrics,
    MetricsCalculator,
    calculate_percentiles,
    aggregate_metrics_by_prompt_length
)


class TestBenchmarkMetrics:
    def test_default_values(self):
        metrics = BenchmarkMetrics()
        assert metrics.total_requests == 0
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 0
        assert metrics.success_rate == 0.0
        assert metrics.ttft_mean == 0.0
        assert metrics.peak_gpu_vram is None

    def test_custom_values(self):
        metrics = BenchmarkMetrics(
            total_requests=100,
            successful_requests=95,
            failed_requests=5,
            success_rate=0.95,
            ttft_mean=0.5,
            ttft_p50=0.45,
            ttft_p95=0.8,
            ttft_p99=1.2,
            peak_gpu_vram=8192.0
        )
        assert metrics.total_requests == 100
        assert metrics.success_rate == 0.95
        assert metrics.peak_gpu_vram == 8192.0


class TestMetricsCalculator:
    def test_add_single_result(self, success_result):
        calc = MetricsCalculator()
        calc.add_result(success_result)
        assert len(calc.results) == 1

    def test_add_multiple_results(self, mixed_results):
        calc = MetricsCalculator()
        for r in mixed_results:
            calc.add_result(r)
        assert len(calc.results) == len(mixed_results)

    def test_add_gpu_memory(self):
        calc = MetricsCalculator()
        calc.add_gpu_memory(4096.0)
        calc.add_gpu_memory(8192.0)
        calc.add_gpu_memory(6144.0)
        assert calc.peak_gpu_vram == 8192.0

    def test_calculate_empty(self):
        calc = MetricsCalculator()
        metrics = calc.calculate()
        assert metrics.total_requests == 0
        assert metrics.successful_requests == 0
        assert metrics.success_rate == 0.0

    def test_calculate_single_success(self, success_result):
        calc = MetricsCalculator()
        calc.add_result(success_result)
        metrics = calc.calculate()

        assert metrics.total_requests == 1
        assert metrics.successful_requests == 1
        assert metrics.failed_requests == 0
        assert metrics.success_rate == 1.0
        assert metrics.ttft_mean == 0.5
        assert metrics.tpot_mean == 0.02
        assert metrics.e2e_latency_mean == 2.5
        assert metrics.throughput_mean == 60.0

    def test_calculate_single_failed(self, failed_result):
        calc = MetricsCalculator()
        calc.add_result(failed_result)
        metrics = calc.calculate()

        assert metrics.total_requests == 1
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 1
        assert metrics.success_rate == 0.0
        assert metrics.ttft_mean == 0.0

    def test_calculate_mixed_results(self, mixed_results):
        calc = MetricsCalculator()
        for r in mixed_results:
            calc.add_result(r)
        metrics = calc.calculate()

        assert metrics.total_requests == 12
        assert metrics.successful_requests == 10
        assert metrics.failed_requests == 2
        assert metrics.success_rate == pytest.approx(10/12)

    def test_calculate_percentiles_accuracy(self):
        calc = MetricsCalculator()
        for i in range(100):
            calc.add_result(InferenceResult(
                request_id=f"req_{i}",
                prompt_tokens=50,
                completion_tokens=100,
                ttft=0.1 + i * 0.01,
                tpot=0.01,
                e2e_latency=1.0 + i * 0.1,
                total_tokens=150,
                throughput=100.0 - i * 0.5,
                success=True,
                prompt_length=200,
                completion_length=100,
                timestamp=1000.0 + i
            ))

        metrics = calc.calculate()

        assert metrics.ttft_p50 == pytest.approx(0.595, abs=0.01)
        assert metrics.ttft_p95 == pytest.approx(1.045, abs=0.01)
        assert metrics.ttft_p99 == pytest.approx(1.085, abs=0.01)

        assert metrics.e2e_latency_p50 == pytest.approx(5.95, abs=0.1)
        assert metrics.e2e_latency_p95 == pytest.approx(10.45, abs=0.1)
        assert metrics.e2e_latency_p99 == pytest.approx(10.85, abs=0.1)

    def test_calculate_with_gpu_memory(self, success_result):
        calc = MetricsCalculator()
        calc.add_result(success_result)
        calc.add_gpu_memory(8192.0)
        metrics = calc.calculate()
        assert metrics.peak_gpu_vram == 8192.0

    def test_calculate_zero_gpu_memory(self, success_result):
        calc = MetricsCalculator()
        calc.add_result(success_result)
        metrics = calc.calculate()
        assert metrics.peak_gpu_vram is None

    def test_to_dataframe(self, mixed_results):
        calc = MetricsCalculator()
        for r in mixed_results:
            calc.add_result(r)
        df = calc.to_dataframe()

        assert isinstance(df, pd.DataFrame)
        assert len(df) == len(mixed_results)
        assert "request_id" in df.columns
        assert "ttft" in df.columns
        assert "tpot" in df.columns
        assert "e2e_latency" in df.columns
        assert "throughput" in df.columns
        assert "success" in df.columns
        assert "error" in df.columns

    def test_to_csv(self, mixed_results):
        calc = MetricsCalculator()
        for r in mixed_results:
            calc.add_result(r)

        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as f:
            temp_path = f.name

        try:
            result_path = calc.to_csv(temp_path)
            assert result_path == temp_path
            assert os.path.exists(temp_path)

            df = pd.read_csv(temp_path)
            assert len(df) == len(mixed_results)
        finally:
            os.unlink(temp_path)

    def test_to_csv_columns_match(self, mixed_results):
        calc = MetricsCalculator()
        for r in mixed_results:
            calc.add_result(r)

        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as f:
            temp_path = f.name

        try:
            calc.to_csv(temp_path)
            df = pd.read_csv(temp_path)
            expected_columns = [
                "request_id", "prompt_length", "completion_tokens",
                "ttft", "tpot", "e2e_latency", "throughput",
                "success", "error", "timestamp"
            ]
            for col in expected_columns:
                assert col in df.columns
        finally:
            os.unlink(temp_path)

    def test_failed_requests_not_affect_metrics(self):
        calc = MetricsCalculator()
        for i in range(10):
            calc.add_result(InferenceResult(
                request_id=f"req_{i}",
                prompt_tokens=50,
                completion_tokens=100,
                ttft=0.5,
                tpot=0.02,
                e2e_latency=2.5,
                total_tokens=150,
                throughput=60.0,
                success=True,
                prompt_length=200,
                completion_length=100,
                timestamp=1000.0 + i
            ))
        for i in range(5):
            calc.add_result(InferenceResult(
                request_id=f"fail_{i}",
                prompt_tokens=0,
                completion_tokens=0,
                ttft=0,
                tpot=0,
                e2e_latency=999.0,
                total_tokens=0,
                throughput=0,
                success=False,
                error="Error"
            ))

        metrics = calc.calculate()

        assert metrics.total_requests == 15
        assert metrics.successful_requests == 10
        assert metrics.failed_requests == 5
        assert metrics.ttft_mean == 0.5
        assert metrics.e2e_latency_mean == 2.5


class TestCalculatePercentiles:
    def test_empty_list(self):
        result = calculate_percentiles([])
        assert result == {50: 0.0, 95: 0.0, 99: 0.0}

    def test_single_value(self):
        result = calculate_percentiles([1.0])
        assert result[50] == 1.0
        assert result[95] == 1.0
        assert result[99] == 1.0

    def test_multiple_values(self):
        values = list(range(1, 101))
        result = calculate_percentiles(values)
        assert result[50] == pytest.approx(50.5, abs=0.1)
        assert result[95] == pytest.approx(95.05, abs=0.1)
        assert result[99] == pytest.approx(99.01, abs=0.1)

    def test_custom_percentiles(self):
        values = list(range(1, 101))
        result = calculate_percentiles(values, percentiles=[25, 75])
        assert 25 in result
        assert 75 in result
        assert 50 not in result


class TestAggregateMetricsByPromptLength:
    def test_short_prompts(self, short_prompt_results):
        aggregated = aggregate_metrics_by_prompt_length(short_prompt_results)
        assert "short" in aggregated
        assert aggregated["short"]["count"] == 5

    def test_medium_prompts(self, medium_prompt_results):
        aggregated = aggregate_metrics_by_prompt_length(medium_prompt_results)
        assert "medium" in aggregated
        assert aggregated["medium"]["count"] == 5

    def test_long_prompts(self, long_prompt_results):
        aggregated = aggregate_metrics_by_prompt_length(long_prompt_results)
        assert "long" in aggregated
        assert aggregated["long"]["count"] == 5

    def test_mixed_lengths(self, short_prompt_results, medium_prompt_results, long_prompt_results):
        all_results = short_prompt_results + medium_prompt_results + long_prompt_results
        aggregated = aggregate_metrics_by_prompt_length(all_results)

        assert "short" in aggregated
        assert "medium" in aggregated
        assert "long" in aggregated
        assert aggregated["short"]["count"] == 5
        assert aggregated["medium"]["count"] == 5
        assert aggregated["long"]["count"] == 5

    def test_aggregated_metrics_structure(self, short_prompt_results):
        aggregated = aggregate_metrics_by_prompt_length(short_prompt_results)
        bucket = aggregated["short"]

        assert "count" in bucket
        assert "ttft_mean" in bucket
        assert "ttft_p50" in bucket
        assert "ttft_p95" in bucket
        assert "tpot_mean" in bucket
        assert "tpot_p50" in bucket
        assert "e2e_mean" in bucket
        assert "e2e_p50" in bucket
        assert "e2e_p95" in bucket

    def test_failed_results_excluded(self, short_prompt_results, failed_result):
        all_results = short_prompt_results + [failed_result]
        aggregated = aggregate_metrics_by_prompt_length(all_results)
        assert aggregated["short"]["count"] == 5

    def test_empty_results(self):
        aggregated = aggregate_metrics_by_prompt_length([])
        assert aggregated == {}
