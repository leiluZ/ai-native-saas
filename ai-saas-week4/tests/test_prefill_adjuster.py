import pytest
from benchmark.prefill_adjuster import (
    PrefillAdjuster,
    PrefillMetrics,
    PrefillAdjustment,
)
from benchmark.kv_cache_config import KVCacheConfig


class TestPrefillMetrics:
    def test_default_values(self):
        m = PrefillMetrics()
        assert m.avg_prefill_time_ms == 0.0
        assert m.p99_prefill_time_ms == 0.0
        assert m.avg_queue_depth == 0.0
        assert m.max_queue_depth == 0
        assert m.avg_waiting_time_ms == 0.0
        assert m.p99_waiting_time_ms == 0.0
        assert m.long_prompt_ratio == 0.0


class TestPrefillAdjustment:
    def test_default_values(self):
        adj = PrefillAdjustment(enable_chunked_prefill=True, max_num_batched_tokens=2048)
        assert adj.enable_chunked_prefill is True
        assert adj.max_num_batched_tokens == 2048
        assert adj.reason == ""


class TestPrefillAdjuster:
    @pytest.fixture
    def adjuster(self):
        return PrefillAdjuster()

    def test_default_thresholds(self, adjuster):
        assert adjuster.long_prompt_threshold_tokens == 8192
        assert adjuster.prefill_time_threshold_ms == 500.0
        assert adjuster.queue_depth_threshold == 10
        assert adjuster.waiting_time_threshold_ms == 1000.0

    def test_no_adjustment_needed(self, adjuster):
        metrics = PrefillMetrics(
            avg_prefill_time_ms=200.0,
            p99_prefill_time_ms=400.0,
            avg_queue_depth=3.0,
            avg_waiting_time_ms=300.0,
            long_prompt_ratio=0.1,
        )
        adj = adjuster.analyze(metrics)
        assert adj.enable_chunked_prefill is False
        assert adj.max_num_batched_tokens is None

    def test_high_prefill_time_triggers_adjustment(self, adjuster):
        metrics = PrefillMetrics(
            avg_prefill_time_ms=600.0,
            p99_prefill_time_ms=800.0,
            avg_queue_depth=3.0,
            avg_waiting_time_ms=300.0,
            long_prompt_ratio=0.1,
        )
        adj = adjuster.analyze(metrics)
        assert adj.enable_chunked_prefill is True

    def test_high_p99_prefill_time_triggers_adjustment(self, adjuster):
        metrics = PrefillMetrics(
            avg_prefill_time_ms=200.0,
            p99_prefill_time_ms=1200.0,
            avg_queue_depth=3.0,
            avg_waiting_time_ms=300.0,
            long_prompt_ratio=0.1,
        )
        adj = adjuster.analyze(metrics)
        assert adj.enable_chunked_prefill is True

    def test_high_queue_depth_triggers_adjustment(self, adjuster):
        metrics = PrefillMetrics(
            avg_prefill_time_ms=200.0,
            p99_prefill_time_ms=400.0,
            avg_queue_depth=15.0,
            avg_waiting_time_ms=300.0,
            long_prompt_ratio=0.1,
        )
        adj = adjuster.analyze(metrics)
        assert adj.enable_chunked_prefill is True

    def test_high_waiting_time_triggers_adjustment(self, adjuster):
        metrics = PrefillMetrics(
            avg_prefill_time_ms=200.0,
            p99_prefill_time_ms=400.0,
            avg_queue_depth=3.0,
            avg_waiting_time_ms=1500.0,
            long_prompt_ratio=0.1,
        )
        adj = adjuster.analyze(metrics)
        assert adj.enable_chunked_prefill is True

    def test_high_long_prompt_ratio_triggers_adjustment(self, adjuster):
        metrics = PrefillMetrics(
            avg_prefill_time_ms=200.0,
            p99_prefill_time_ms=400.0,
            avg_queue_depth=3.0,
            avg_waiting_time_ms=300.0,
            long_prompt_ratio=0.5,
        )
        adj = adjuster.analyze(metrics)
        assert adj.enable_chunked_prefill is True

    def test_batched_tokens_2048_for_very_slow_prefill(self, adjuster):
        metrics = PrefillMetrics(
            avg_prefill_time_ms=1200.0,
            p99_prefill_time_ms=1500.0,
            avg_queue_depth=3.0,
            avg_waiting_time_ms=300.0,
            long_prompt_ratio=0.1,
        )
        adj = adjuster.analyze(metrics)
        assert adj.max_num_batched_tokens == 2048

    def test_batched_tokens_4096_for_moderate_prefill(self, adjuster):
        metrics = PrefillMetrics(
            avg_prefill_time_ms=600.0,
            p99_prefill_time_ms=800.0,
            avg_queue_depth=3.0,
            avg_waiting_time_ms=300.0,
            long_prompt_ratio=0.1,
        )
        adj = adjuster.analyze(metrics)
        assert adj.max_num_batched_tokens == 4096

    def test_batched_tokens_4096_for_high_queue_depth(self, adjuster):
        metrics = PrefillMetrics(
            avg_prefill_time_ms=200.0,
            p99_prefill_time_ms=400.0,
            avg_queue_depth=25.0,
            avg_waiting_time_ms=300.0,
            long_prompt_ratio=0.1,
        )
        adj = adjuster.analyze(metrics)
        assert adj.max_num_batched_tokens == 4096

    def test_batched_tokens_8192_for_moderate_queue_depth(self, adjuster):
        metrics = PrefillMetrics(
            avg_prefill_time_ms=200.0,
            p99_prefill_time_ms=400.0,
            avg_queue_depth=15.0,
            avg_waiting_time_ms=300.0,
            long_prompt_ratio=0.1,
        )
        adj = adjuster.analyze(metrics)
        assert adj.max_num_batched_tokens == 8192

    def test_apply_to_config(self, adjuster):
        config = KVCacheConfig(
            gpu_memory_utilization=0.85,
            block_size=32,
            max_num_seqs=128,
            enable_chunked_prefill=False,
            max_num_batched_tokens=None,
        )
        adj = PrefillAdjustment(enable_chunked_prefill=True, max_num_batched_tokens=4096)
        new_config = adjuster.apply_to_config(config, adj)
        assert new_config.gpu_memory_utilization == 0.85
        assert new_config.block_size == 32
        assert new_config.max_num_seqs == 128
        assert new_config.enable_chunked_prefill is True
        assert new_config.max_num_batched_tokens == 4096

    def test_custom_thresholds(self):
        adjuster = PrefillAdjuster(
            prefill_time_threshold_ms=100.0,
            queue_depth_threshold=5,
        )
        metrics = PrefillMetrics(
            avg_prefill_time_ms=150.0,
            p99_prefill_time_ms=200.0,
            avg_queue_depth=3.0,
            avg_waiting_time_ms=50.0,
            long_prompt_ratio=0.0,
        )
        adj = adjuster.analyze(metrics)
        assert adj.enable_chunked_prefill is True
