import subprocess
import re
import json
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GPUInfo:
    index: int
    name: str
    memory_total_mb: float
    memory_free_mb: float = 0.0
    memory_used_mb: float = 0.0
    utilization_pct: float = 0.0
    temperature_c: float = 0.0
    cuda_version: str = ""
    driver_version: str = ""


@dataclass
class GPUScanResult:
    gpus: list[GPUInfo] = field(default_factory=list)
    total_gpu_count: int = 0
    total_memory_mb: float = 0.0
    cuda_available: bool = False
    cuda_version: str = ""
    driver_version: str = ""
    nvidia_smi_available: bool = False
    errors: list[str] = field(default_factory=list)


def _run_command(cmd: list[str], timeout: int = 10) -> tuple[str, str, int]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout, result.stderr, result.returncode
    except FileNotFoundError:
        return "", f"Command not found: {cmd[0]}", -1
    except subprocess.TimeoutExpired:
        return "", f"Command timed out: {' '.join(cmd)}", -1


def _parse_nvidia_smi_query() -> list[GPUInfo]:
    stdout, stderr, rc = _run_command([
        "nvidia-smi",
        "--query-gpu=index,name,memory.total,memory.free,memory.used,utilization.gpu,temperature.gpu",
        "--format=csv,noheader,nounits"
    ])
    if rc != 0:
        return []

    gpus = []
    for line in stdout.strip().split("\n"):
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 7:
            try:
                gpus.append(GPUInfo(
                    index=int(parts[0]),
                    name=parts[1],
                    memory_total_mb=float(parts[2]),
                    memory_free_mb=float(parts[3]),
                    memory_used_mb=float(parts[4]),
                    utilization_pct=float(parts[5]),
                    temperature_c=float(parts[6]),
                ))
            except (ValueError, IndexError):
                continue
    return gpus


def _parse_cuda_version() -> tuple[str, str]:
    cuda_version = ""
    driver_version = ""

    stdout, _, rc = _run_command(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"])
    if rc == 0 and stdout.strip():
        driver_version = stdout.strip().split("\n")[0].strip()

    nvcc_stdout, _, nvcc_rc = _run_command(["nvcc", "--version"])
    if nvcc_rc == 0:
        match = re.search(r"release\s+(\d+\.\d+)", nvcc_stdout)
        if match:
            cuda_version = match.group(1)

    if not cuda_version:
        cuda_home = os.environ.get("CUDA_HOME", os.environ.get("CUDA_PATH", ""))
        if cuda_home:
            version_file = os.path.join(cuda_home, "version.txt")
            if os.path.exists(version_file):
                with open(version_file) as f:
                    content = f.read()
                    match = re.search(r"CUDA Version\s+(\d+\.\d+)", content)
                    if match:
                        cuda_version = match.group(1)

    if not cuda_version:
        try:
            import torch
            if torch.cuda.is_available():
                cuda_version = torch.version.cuda or ""
        except ImportError:
            pass

    return cuda_version, driver_version


def scan_gpus() -> GPUScanResult:
    result = GPUScanResult()
    result.nvidia_smi_available = _run_command(["nvidia-smi", "-L"])[2] == 0

    if not result.nvidia_smi_available:
        result.errors.append("nvidia-smi not available - no NVIDIA GPU detected")
        return result

    result.gpus = _parse_nvidia_smi_query()
    result.total_gpu_count = len(result.gpus)
    result.total_memory_mb = sum(g.memory_total_mb for g in result.gpus)

    result.cuda_version, result.driver_version = _parse_cuda_version()
    result.cuda_available = bool(result.cuda_version)

    if not result.cuda_available:
        result.errors.append("CUDA not detected - install CUDA toolkit or set CUDA_HOME")

    return result


def get_gpu_memory_usage_pct() -> float:
    gpus = _parse_nvidia_smi_query()
    if not gpus:
        return 0.0
    total_used = sum(g.memory_used_mb for g in gpus)
    total_memory = sum(g.memory_total_mb for g in gpus)
    if total_memory == 0:
        return 0.0
    return (total_used / total_memory) * 100.0


def get_gpu_utilization_pct() -> float:
    gpus = _parse_nvidia_smi_query()
    if not gpus:
        return 0.0
    return sum(g.utilization_pct for g in gpus) / len(gpus)


def format_scan_report(result: GPUScanResult) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append("GPU SCAN REPORT")
    lines.append("=" * 60)

    if result.errors:
        for err in result.errors:
            lines.append(f"  ERROR: {err}")
        return "\n".join(lines)

    lines.append(f"  Total GPUs:       {result.total_gpu_count}")
    lines.append(f"  Total VRAM:       {result.total_memory_mb:.0f} MB ({result.total_memory_mb/1024:.1f} GB)")
    lines.append(f"  CUDA Available:   {result.cuda_available}")
    lines.append(f"  CUDA Version:     {result.cuda_version or 'N/A'}")
    lines.append(f"  Driver Version:   {result.driver_version or 'N/A'}")

    for gpu in result.gpus:
        lines.append(f"\n  GPU {gpu.index}: {gpu.name}")
        lines.append(f"    Memory: {gpu.memory_used_mb:.0f}/{gpu.memory_total_mb:.0f} MB ({gpu.memory_used_mb/gpu.memory_total_mb*100:.1f}% used)")
        lines.append(f"    Utilization: {gpu.utilization_pct:.1f}%")
        lines.append(f"    Temperature: {gpu.temperature_c:.0f}°C")

    return "\n".join(lines)
