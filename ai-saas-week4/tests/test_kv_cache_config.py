import pytest
from benchmark.kv_cache_config import (
    KVCacheConfig,
    GridSearchConfig,
    SafetyThresholds,
    DEFAULT_GRID_SEARCH,
    DEFAULT_SAFETY_THRESHOLDS,
)


class TestKVCacheConfig:
    def test_default_values(self):
        config = KVCacheConfig()
        assert config.gpu_memory_utilization == 0.90
        assert config.block_size == 16
        assert config.max_num_seqs == 64
        assert config.enable_chunked_prefill is True
        assert config.max_num_batched_tokens is None
        assert config.enable_prefix_caching is True
        assert config.swap_space == 4

    def test_to_cli_args_basic(self):
        config = KVCacheConfig(
            gpu_memory_utilization=0.85,
            block_size=32,
            max_num_seqs=128,
            enable_chunked_prefill=False,
        )
        args = config.to_cli_args()
        assert "--gpu-memory-utilization=0.85" in args
        assert "--block-size=32" in args
        assert "--max-num-seqs=128" in args
        assert "--swap-space=4" in args
        assert "--enable-chunked-prefill" not in args
        assert "--enable-prefix-caching" in args

    def test_to_cli_args_with_chunked_prefill(self):
        config = KVCacheConfig(
            enable_chunked_prefill=True,
            max_num_batched_tokens=4096,
        )
        args = config.to_cli_args()
        assert "--enable-chunked-prefill" in args
        assert "--max-num-batched-tokens=4096" in args

    def test_to_cli_args_with_max_model_len(self):
        config = KVCacheConfig(max_model_len=8192)
        args = config.to_cli_args()
        assert "--max-model-len=8192" in args

    def test_to_dict(self):
        config = KVCacheConfig(gpu_memory_utilization=0.85, block_size=32, max_num_seqs=64)
        d = config.to_dict()
        assert d["gpu_memory_utilization"] == 0.85
        assert d["block_size"] == 32
        assert d["max_num_seqs"] == 64

    def test_label(self):
        config = KVCacheConfig(
            gpu_memory_utilization=0.85,
            block_size=32,
            max_num_seqs=128,
            enable_chunked_prefill=True,
            max_num_batched_tokens=4096,
        )
        label = config.label()
        assert "gmu0.85" in label
        assert "bs32" in label
        assert "mns128" in label
        assert "CP" in label
        assert "BT4096" in label

    def test_label_no_chunked_prefill(self):
        config = KVCacheConfig(enable_chunked_prefill=False, max_num_batched_tokens=None)
        label = config.label()
        assert "noCP" in label
        assert "BTdef" in label


class TestGridSearchConfig:
    def test_default_values(self):
        gs = GridSearchConfig()
        assert gs.gpu_memory_utilization_values == [0.80, 0.85, 0.90]
        assert gs.block_size_values == [16, 32]
        assert gs.max_num_seqs_values == [32, 64, 128]

    def test_generate_combinations_count(self):
        gs = GridSearchConfig()
        configs = gs.generate_combinations()
        assert len(configs) > 0
        assert gs.total_combinations() == len(configs)

    def test_generate_combinations_has_basic(self):
        gs = GridSearchConfig(
            gpu_memory_utilization_values=[0.80],
            block_size_values=[16],
            max_num_seqs_values=[32],
            enable_chunked_prefill_values=[False],
            max_num_batched_tokens_values=[None],
        )
        configs = gs.generate_combinations()
        basic_configs = [c for c in configs if not c.enable_chunked_prefill and c.max_num_batched_tokens is None]
        assert len(basic_configs) >= 1
        assert basic_configs[0].gpu_memory_utilization == 0.80
        assert basic_configs[0].block_size == 16
        assert basic_configs[0].max_num_seqs == 32

    def test_generate_combinations_includes_chunked_prefill_variants(self):
        gs = GridSearchConfig(
            gpu_memory_utilization_values=[0.90],
            block_size_values=[16],
            max_num_seqs_values=[64],
            enable_chunked_prefill_values=[True, False],
            max_num_batched_tokens_values=[None, 2048],
        )
        configs = gs.generate_combinations()
        has_cp_true = any(c.enable_chunked_prefill for c in configs)
        has_cp_false = any(not c.enable_chunked_prefill for c in configs)
        assert has_cp_true
        assert has_cp_false

    def test_custom_grid(self):
        gs = GridSearchConfig(
            gpu_memory_utilization_values=[0.75, 0.95],
            block_size_values=[8, 16, 32],
            max_num_seqs_values=[16, 256],
        )
        configs = gs.generate_combinations()
        assert len(configs) > 0
        gmus = set(c.gpu_memory_utilization for c in configs)
        assert 0.75 in gmus
        assert 0.95 in gmus


class TestSafetyThresholds:
    def test_default_values(self):
        st = SafetyThresholds()
        assert st.gpu_memory_pct_max == 92.0
        assert st.p99_latency_max_s == 2.0
        assert st.oom_max_per_round == 0
        assert st.consecutive_oom_max == 2

    def test_is_safe_all_ok(self):
        st = SafetyThresholds()
        assert st.is_safe(80.0, 1.0, 0) is True

    def test_is_safe_gpu_memory_exceeded(self):
        st = SafetyThresholds()
        assert st.is_safe(95.0, 1.0, 0) is False

    def test_is_safe_p99_latency_exceeded(self):
        st = SafetyThresholds()
        assert st.is_safe(80.0, 3.0, 0) is False

    def test_is_safe_oom_exceeded(self):
        st = SafetyThresholds()
        assert st.is_safe(80.0, 1.0, 1) is False

    def test_is_safe_boundary(self):
        st = SafetyThresholds()
        assert st.is_safe(92.0, 2.0, 0) is True
        assert st.is_safe(92.1, 2.0, 0) is False


class TestDefaults:
    def test_default_grid_search(self):
        assert DEFAULT_GRID_SEARCH is not None
        assert isinstance(DEFAULT_GRID_SEARCH, GridSearchConfig)

    def test_default_safety_thresholds(self):
        assert DEFAULT_SAFETY_THRESHOLDS is not None
        assert isinstance(DEFAULT_SAFETY_THRESHOLDS, SafetyThresholds)
