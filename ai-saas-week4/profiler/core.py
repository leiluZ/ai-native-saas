import json
import logging
import os
import subprocess
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Optional

from profiler.config import ProfilerConfig, default_config

logger = logging.getLogger(__name__)

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None


@dataclass
class ProfilingEvent:
    name: str
    category: str
    start_time_us: float
    end_time_us: float
    duration_us: float
    cpu_time_us: float = 0.0
    cuda_time_us: float = 0.0
    input_shapes: Optional[str] = None
    flops: Optional[float] = None
    stack: Optional[list[str]] = None
    device: str = "cpu"
    self_cpu_time_us: float = 0.0
    call_count: int = 1
    phase: Optional[str] = None


@dataclass
class ProfilingTrace:
    events: list[ProfilingEvent] = field(default_factory=list)
    gpu_utilization_pct: float = 0.0
    gpu_memory_mb: float = 0.0
    cpu_utilization_pct: float = 0.0
    total_duration_us: float = 0.0
    phase_breakdown: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def total_cpu_time_us(self) -> float:
        return sum(e.cpu_time_us for e in self.events)

    def total_cuda_time_us(self) -> float:
        return sum(e.cuda_time_us for e in self.events if e.cuda_time_us > 0)

    def event_count(self) -> int:
        return len(self.events)

    def unique_ops(self) -> int:
        return len({e.name for e in self.events})


class TorchProfilerRunner:
    def __init__(self, config: Optional[ProfilerConfig] = None):
        self.config = config or default_config

    def is_available(self) -> bool:
        return TORCH_AVAILABLE

    @contextmanager
    def profile(
        self,
        target_fn=None,
        num_steps: int = None,
        use_cuda: bool = False,
    ):
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch is not available for profiling")

        activities = [torch.profiler.ProfilerActivity.CPU]
        if use_cuda and torch.cuda.is_available():
            activities.append(torch.profiler.ProfilerActivity.CUDA)

        schedule = torch.profiler.schedule(
            wait=self.config.schedule_wait,
            warmup=self.config.schedule_warmup,
            active=self.config.schedule_active,
            repeat=self.config.schedule_repeat,
        )

        with torch.profiler.profile(
            activities=activities,
            schedule=schedule,
            on_trace_ready=torch.profiler.tensorboard_trace_handler(
                os.path.join(self.config.output_dir, "trace"),
                use_gzip=True,
            ),
            record_shapes=self.config.record_shapes,
            profile_memory=self.config.profile_memory,
            with_stack=self.config.with_stack,
            with_flops=self.config.with_flops,
        ) as prof:
            yield prof

    def extract_trace(self, prof) -> ProfilingTrace:
        trace = ProfilingTrace()
        events = []

        for event in prof.key_averages():
            evt = ProfilingEvent(
                name=event.key,
                category=getattr(event, "tag", "unknown"),
                start_time_us=0.0,
                end_time_us=event.cpu_time_total / 1000.0 if hasattr(event, "cpu_time_total") else 0.0,
                duration_us=event.cpu_time_total / 1000.0 if hasattr(event, "cpu_time_total") else 0.0,
                cpu_time_us=event.cpu_time_total / 1000.0 if hasattr(event, "cpu_time_total") else 0.0,
                cuda_time_us=event.cuda_time_total / 1000.0 if hasattr(event, "cuda_time_total") else 0.0,
                self_cpu_time_us=event.self_cpu_time_total / 1000.0 if hasattr(event, "self_cpu_time_total") else 0.0,
                call_count=getattr(event, "count", 1),
                input_shapes=str(getattr(event, "input_shapes", "")) if hasattr(event, "input_shapes") else None,
                flops=getattr(event, "flops", None),
            )
            events.append(evt)

        events.sort(key=lambda e: e.cpu_time_us, reverse=True)
        trace.events = events
        trace.total_duration_us = prof.profiler.total_average().cpu_time_total / 1000.0 if hasattr(prof, "profiler") else sum(e.cpu_time_us for e in events)

        if torch.cuda.is_available():
            trace.gpu_utilization_pct = 0.0
            trace.gpu_memory_mb = torch.cuda.max_memory_allocated() / (1024 * 1024)

        return trace

    def run_and_profile(self, fn, *args, num_steps: int = None, use_cuda: bool = False, **kwargs) -> ProfilingTrace:
        steps = num_steps or (self.config.warmup_steps + self.config.active_steps)

        with self.profile(num_steps=steps, use_cuda=use_cuda) as prof:
            for i in range(steps):
                fn(*args, **kwargs)
                prof.step()

        return self.extract_trace(prof)


class NsysProfiler:
    def __init__(self, config: Optional[ProfilerConfig] = None):
        self.config = config or default_config

    def is_available(self) -> bool:
        try:
            result = subprocess.run(
                ["nsys", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def profile_command(
        self,
        command: list[str],
        output_name: Optional[str] = None,
        delay: Optional[int] = None,
    ) -> str:
        name = output_name or self.config.nsys_output
        dl = delay or self.config.nsys_delay
        output_file = os.path.join(self.config.output_dir, f"{name}.nsys-rep")

        cmd = [
            "nsys", "profile",
            "--output", output_file,
            "--force-overwrite", "true",
            "--delay", str(dl),
            "--duration", "30",
        ] + command

        logger.info(f"Running nsys profile: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"nsys profiling failed: {result.stderr}")
            raise RuntimeError(f"nsys profiling failed: {result.stderr}")

        return output_file

    def parse_nsys_report(self, report_path: str) -> ProfilingTrace:
        trace = ProfilingTrace()

        try:
            result = subprocess.run(
                ["nsys", "stats", "--format", "json", report_path],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return self._process_nsys_json(data, trace)
        except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse nsys report: {e}")

        return self._fallback_parse(report_path, trace)

    def _process_nsys_json(self, data: dict, trace: ProfilingTrace) -> ProfilingTrace:
        for item in data.get("GPU", {}).get("items", []):
            evt = ProfilingEvent(
                name=item.get("Name", "unknown"),
                category="cuda",
                start_time_us=item.get("Start", 0) / 1000.0,
                end_time_us=item.get("End", 0) / 1000.0,
                duration_us=item.get("Duration", 0) / 1000.0,
                cuda_time_us=item.get("Duration", 0) / 1000.0,
                device="gpu",
            )
            trace.events.append(evt)
        return trace

    def _fallback_parse(self, report_path: str, trace: ProfilingTrace) -> ProfilingTrace:
        try:
            result = subprocess.run(
                ["nsys", "stats", report_path],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0 and result.stdout:
                return self._process_nsys_text(result.stdout, trace)
        except subprocess.TimeoutExpired:
            pass
        return trace

    def _process_nsys_text(self, output: str, trace: ProfilingTrace) -> ProfilingTrace:
        for line in output.splitlines():
            parts = line.split()
            if len(parts) >= 3:
                try:
                    duration = float(parts[-1])
                    name = parts[0].split("(")[0]
                    evt = ProfilingEvent(
                        name=name,
                        category="cuda",
                        start_time_us=0.0,
                        end_time_us=duration,
                        duration_us=duration,
                        cuda_time_us=duration,
                        device="gpu",
                    )
                    trace.events.append(evt)
                except (ValueError, IndexError):
                    continue
        return trace


class CpuProfiler:
    def __init__(self, config: Optional[ProfilerConfig] = None):
        self.config = config or default_config

    def profile_block(self, fn, *args, **kwargs) -> ProfilingTrace:
        result = None
        events = []

        try:
            import cProfile
            import pstats
            import io
        except ImportError:
            return self._time_based_profile(fn, *args, **kwargs)

        pr = cProfile.Profile()
        pr.enable()

        start = time.perf_counter()
        result = fn(*args, **kwargs)
        elapsed = (time.perf_counter() - start) * 1_000_000

        pr.disable()

        s = io.StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
        ps.print_stats(50)

        for line in s.getvalue().splitlines():
            parts = line.strip().split()
            if len(parts) >= 5 and parts[0].count(":") == 1:
                try:
                    ncalls = parts[0]
                    cumtime = float(parts[3]) * 1_000_000
                    file_func = parts[-1]
                    evt = ProfilingEvent(
                        name=file_func,
                        category="python",
                        start_time_us=0.0,
                        end_time_us=cumtime,
                        duration_us=cumtime,
                        cpu_time_us=cumtime,
                        call_count=int(ncalls.split("/")[0]) if "/" in ncalls else int(ncalls),
                    )
                    events.append(evt)
                except (ValueError, IndexError):
                    continue

        trace = ProfilingTrace(
            events=events,
            total_duration_us=elapsed,
        )
        return trace, result

    def _time_based_profile(self, fn, *args, **kwargs) -> tuple:
        start = time.perf_counter()
        result = fn(*args, **kwargs)
        elapsed = (time.perf_counter() - start) * 1_000_000

        trace = ProfilingTrace(
            events=[
                ProfilingEvent(
                    name="total_execution",
                    category="cpu",
                    start_time_us=0.0,
                    end_time_us=elapsed,
                    duration_us=elapsed,
                    cpu_time_us=elapsed,
                )
            ],
            total_duration_us=elapsed,
        )
        return trace, result


class ProfileManager:
    def __init__(self, config: Optional[ProfilerConfig] = None):
        self.config = config or default_config
        self.torch_profiler = TorchProfilerRunner(self.config)
        self.nsys_profiler = NsysProfiler(self.config)
        self.cpu_profiler = CpuProfiler(self.config)
        self._traces: list[ProfilingTrace] = []

    def run_torch_profile(
        self,
        fn,
        *args,
        num_steps: int = None,
        use_cuda: bool = False,
        **kwargs,
    ) -> ProfilingTrace:
        if not self.torch_profiler.is_available():
            logger.warning("PyTorch not available, falling back to CPU profiling")
            trace, _ = self.cpu_profiler.profile_block(fn, *args, **kwargs)
        else:
            trace = self.torch_profiler.run_and_profile(fn, *args, num_steps=num_steps, use_cuda=use_cuda, **kwargs)

        self._traces.append(trace)
        return trace

    def run_nsys_profile(self, command: list[str]) -> Optional[ProfilingTrace]:
        if not self.nsys_profiler.is_available():
            logger.warning("nsys not available on this system")
            return None

        report_path = self.nsys_profiler.profile_command(command)
        trace = self.nsys_profiler.parse_nsys_report(report_path)
        self._traces.append(trace)
        return trace

    def run_cpu_profile(self, fn, *args, **kwargs) -> tuple:
        trace, result = self.cpu_profiler.profile_block(fn, *args, **kwargs)
        self._traces.append(trace)
        return trace, result

    def get_all_traces(self) -> list[ProfilingTrace]:
        return self._traces

    def save_trace(self, trace: ProfilingTrace, filename: str):
        os.makedirs(self.config.output_dir, exist_ok=True)
        path = os.path.join(self.config.output_dir, filename)

        data = {
            "events": [
                {
                    "name": e.name,
                    "category": e.category,
                    "start_time_us": e.start_time_us,
                    "end_time_us": e.end_time_us,
                    "duration_us": e.duration_us,
                    "cpu_time_us": e.cpu_time_us,
                    "cuda_time_us": e.cuda_time_us,
                    "self_cpu_time_us": e.self_cpu_time_us,
                    "call_count": e.call_count,
                    "phase": e.phase,
                    "device": e.device,
                }
                for e in trace.events
            ],
            "gpu_utilization_pct": trace.gpu_utilization_pct,
            "gpu_memory_mb": trace.gpu_memory_mb,
            "total_duration_us": trace.total_duration_us,
            "phase_breakdown": trace.phase_breakdown,
            "metadata": trace.metadata,
        }

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Trace saved to {path}")
        return path

    def load_trace(self, filename: str) -> ProfilingTrace:
        path = os.path.join(self.config.output_dir, filename)

        with open(path) as f:
            data = json.load(f)

        trace = ProfilingTrace(
            events=[
                ProfilingEvent(
                    name=e["name"],
                    category=e.get("category", "unknown"),
                    start_time_us=e.get("start_time_us", 0.0),
                    end_time_us=e.get("end_time_us", 0.0),
                    duration_us=e.get("duration_us", 0),
                    cpu_time_us=e.get("cpu_time_us", 0),
                    cuda_time_us=e.get("cuda_time_us", 0),
                    self_cpu_time_us=e.get("self_cpu_time_us", 0),
                    call_count=e.get("call_count", 1),
                    phase=e.get("phase"),
                    device=e.get("device", "cpu"),
                )
                for e in data.get("events", [])
            ],
            gpu_utilization_pct=data.get("gpu_utilization_pct", 0),
            gpu_memory_mb=data.get("gpu_memory_mb", 0),
            total_duration_us=data.get("total_duration_us", 0),
            phase_breakdown=data.get("phase_breakdown", {}),
            metadata=data.get("metadata", {}),
        )
        return trace


def get_profile_manager(config: Optional[ProfilerConfig] = None) -> ProfileManager:
    return ProfileManager(config)
