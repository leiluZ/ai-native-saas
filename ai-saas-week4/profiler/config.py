from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProfilerConfig:
    output_dir: str = "profiling_results"
    warmup_steps: int = 5
    active_steps: int = 10

    with_stack: bool = True
    record_shapes: bool = True
    profile_memory: bool = True
    with_flops: bool = False

    cpu_activities: tuple = ("cpu",)
    gpu_activities: tuple = ("cuda",)

    schedule_wait: int = 1
    schedule_warmup: int = 1
    schedule_active: int = 3
    schedule_repeat: int = 2

    nsys_enabled: bool = False
    nsys_output: str = "nsys_profile"
    nsys_delay: int = 30

    flame_graph_enabled: bool = True
    flame_graph_width: int = 1200
    flame_graph_height: int = 600

    bottleneck_top_n: int = 3
    bottleneck_min_time_us: float = 100.0

    phase_thresholds: dict = field(default_factory=lambda: {
        "prefill": {"min_tokens": 32, "label": "Prefill"},
        "decode": {"max_tokens_per_step": 4, "label": "Decode"},
        "kv_cache_alloc": {"label": "KV Cache Allocation"},
        "network_io": {"label": "Network I/O"},
    })

    llm_enabled: bool = False
    llm_endpoint: str = "http://localhost:8000"
    llm_model: str = "gpt-3.5-turbo"

    auto_archive: bool = True
    archive_format: str = "timestamp"

    comparison_metrics: list = field(default_factory=lambda: [
        "p50_latency_ms", "p99_latency_ms", "throughput_tokens_per_sec",
        "gpu_memory_mb", "cpu_time_ms", "cache_hit_rate",
    ])


default_config = ProfilerConfig()
