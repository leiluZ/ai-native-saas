from dataclasses import dataclass, field
from typing import Optional
from itertools import product


@dataclass
class KVCacheConfig:
    gpu_memory_utilization: float = 0.90
    block_size: int = 16
    max_num_seqs: int = 64
    enable_chunked_prefill: bool = True
    max_num_batched_tokens: Optional[int] = None
    enable_prefix_caching: bool = True
    swap_space: int = 4
    max_model_len: Optional[int] = None

    def to_cli_args(self) -> list[str]:
        args = [
            f"--gpu-memory-utilization={self.gpu_memory_utilization}",
            f"--block-size={self.block_size}",
            f"--max-num-seqs={self.max_num_seqs}",
            f"--swap-space={self.swap_space}",
        ]
        if self.enable_chunked_prefill:
            args.append("--enable-chunked-prefill")
        if self.max_num_batched_tokens is not None:
            args.append(f"--max-num-batched-tokens={self.max_num_batched_tokens}")
        if self.enable_prefix_caching:
            args.append("--enable-prefix-caching")
        if self.max_model_len is not None:
            args.append(f"--max-model-len={self.max_model_len}")
        return args

    def to_dict(self) -> dict:
        return {
            "gpu_memory_utilization": self.gpu_memory_utilization,
            "block_size": self.block_size,
            "max_num_seqs": self.max_num_seqs,
            "enable_chunked_prefill": self.enable_chunked_prefill,
            "max_num_batched_tokens": self.max_num_batched_tokens,
            "enable_prefix_caching": self.enable_prefix_caching,
            "swap_space": self.swap_space,
            "max_model_len": self.max_model_len,
        }

    def label(self) -> str:
        chunked = "CP" if self.enable_chunked_prefill else "noCP"
        batched = f"BT{self.max_num_batched_tokens}" if self.max_num_batched_tokens else "BTdef"
        return f"gmu{self.gpu_memory_utilization}_bs{self.block_size}_mns{self.max_num_seqs}_{chunked}_{batched}"


@dataclass
class GridSearchConfig:
    gpu_memory_utilization_values: list[float] = field(default_factory=lambda: [0.80, 0.85, 0.90])
    block_size_values: list[int] = field(default_factory=lambda: [16, 32])
    max_num_seqs_values: list[int] = field(default_factory=lambda: [32, 64, 128])
    enable_chunked_prefill_values: list[bool] = field(default_factory=lambda: [True, False])
    max_num_batched_tokens_values: list[Optional[int]] = field(default_factory=lambda: [None, 2048, 4096, 8192])
    enable_prefix_caching: bool = True
    swap_space: int = 4

    def generate_combinations(self) -> list[KVCacheConfig]:
        base_combos = list(product(
            self.gpu_memory_utilization_values,
            self.block_size_values,
            self.max_num_seqs_values,
        ))

        configs = []
        for gmu, bs, mns in base_combos:
            configs.append(KVCacheConfig(
                gpu_memory_utilization=gmu,
                block_size=bs,
                max_num_seqs=mns,
                enable_chunked_prefill=False,
                max_num_batched_tokens=None,
                enable_prefix_caching=self.enable_prefix_caching,
                swap_space=self.swap_space,
            ))

        for gmu, bs, mns in base_combos:
            for cp in self.enable_chunked_prefill_values:
                for bt in self.max_num_batched_tokens_values:
                    configs.append(KVCacheConfig(
                        gpu_memory_utilization=gmu,
                        block_size=bs,
                        max_num_seqs=mns,
                        enable_chunked_prefill=cp,
                        max_num_batched_tokens=bt,
                        enable_prefix_caching=self.enable_prefix_caching,
                        swap_space=self.swap_space,
                    ))

        return configs

    def total_combinations(self) -> int:
        return len(self.generate_combinations())


@dataclass
class SafetyThresholds:
    gpu_memory_pct_max: float = 92.0
    p99_latency_max_s: float = 2.0
    oom_max_per_round: int = 0
    consecutive_oom_max: int = 2

    def is_safe(self, gpu_memory_pct: float, p99_latency_s: float, oom_count: int) -> bool:
        if gpu_memory_pct > self.gpu_memory_pct_max:
            return False
        if p99_latency_s > self.p99_latency_max_s:
            return False
        if oom_count > self.oom_max_per_round:
            return False
        return True


DEFAULT_GRID_SEARCH = GridSearchConfig()
DEFAULT_SAFETY_THRESHOLDS = SafetyThresholds()
