import pytest
from unittest.mock import patch, MagicMock
from benchmark.gpu_scanner import (
    GPUInfo,
    GPUScanResult,
    scan_gpus,
    get_gpu_memory_usage_pct,
    get_gpu_utilization_pct,
    format_scan_report,
    _parse_nvidia_smi_query,
    _parse_cuda_version,
    _run_command,
)


class TestRunCommand:
    def test_successful_command(self):
        stdout, stderr, rc = _run_command(["echo", "hello"])
        assert rc == 0
        assert "hello" in stdout

    def test_command_not_found(self):
        stdout, stderr, rc = _run_command(["nonexistent_command_xyz"])
        assert rc == -1
        assert "not found" in stderr.lower()

    def test_command_with_timeout(self):
        stdout, stderr, rc = _run_command(["sleep", "30"], timeout=1)
        assert rc == -1
        assert "timed out" in stderr.lower()


class TestParseNvidiaSmiQuery:
    def test_parse_valid_output(self):
        mock_stdout = (
            "0, NVIDIA GeForce RTX 4090, 24564, 22000, 2564, 45, 65\n"
            "1, NVIDIA GeForce RTX 4090, 24564, 23000, 1564, 30, 60\n"
        )
        with patch("benchmark.gpu_scanner._run_command", return_value=(mock_stdout, "", 0)):
            gpus = _parse_nvidia_smi_query()
            assert len(gpus) == 2
            assert gpus[0].index == 0
            assert gpus[0].name == "NVIDIA GeForce RTX 4090"
            assert gpus[0].memory_total_mb == 24564
            assert gpus[0].memory_free_mb == 22000
            assert gpus[0].memory_used_mb == 2564
            assert gpus[0].utilization_pct == 45
            assert gpus[0].temperature_c == 65

    def test_parse_empty_output(self):
        with patch("benchmark.gpu_scanner._run_command", return_value=("", "", 0)):
            gpus = _parse_nvidia_smi_query()
            assert gpus == []

    def test_parse_command_failure(self):
        with patch("benchmark.gpu_scanner._run_command", return_value=("", "error", 1)):
            gpus = _parse_nvidia_smi_query()
            assert gpus == []

    def test_parse_malformed_output(self):
        mock_stdout = "bad,data,only,three\n"
        with patch("benchmark.gpu_scanner._run_command", return_value=(mock_stdout, "", 0)):
            gpus = _parse_nvidia_smi_query()
            assert gpus == []


class TestParseCudaVersion:
    def test_from_nvcc(self):
        with patch("benchmark.gpu_scanner._run_command") as mock_run:
            mock_run.side_effect = [
                ("535.104.05\n", "", 0),
                ("Cuda compilation tools, release 12.1, V12.1.105\n", "", 0),
            ]
            cuda, driver = _parse_cuda_version()
            assert cuda == "12.1"
            assert driver == "535.104.05"

    def test_from_cuda_home(self):
        with patch("benchmark.gpu_scanner._run_command") as mock_run:
            mock_run.side_effect = [
                ("535.104.05\n", "", 0),
                ("", "", 1),
            ]
            with patch("os.environ.get", return_value="/usr/local/cuda"):
                with patch("os.path.exists", return_value=True):
                    with patch("builtins.open", new_callable=MagicMock) as mock_open:
                        mock_open.return_value.__enter__.return_value.read.return_value = "CUDA Version 12.2\n"
                        cuda, driver = _parse_cuda_version()
                        assert cuda == "12.2"

    def test_no_cuda(self):
        with patch("benchmark.gpu_scanner._run_command", return_value=("", "", 1)):
            with patch("os.environ.get", return_value=""):
                with patch("os.path.exists", return_value=False):
                    cuda, driver = _parse_cuda_version()
                    assert cuda == ""


class TestScanGPUs:
    def test_no_nvidia_smi(self):
        with patch("benchmark.gpu_scanner._run_command", return_value=("", "", 1)):
            result = scan_gpus()
            assert not result.nvidia_smi_available
            assert result.total_gpu_count == 0
            assert len(result.errors) > 0

    def test_with_gpus(self):
        mock_stdout = "0, NVIDIA A100, 81920, 70000, 11920, 80, 55\n"
        with patch("benchmark.gpu_scanner._run_command") as mock_run:
            mock_run.side_effect = [
                ("GPU 0: NVIDIA A100\n", "", 0),
                (mock_stdout, "", 0),
                ("550.54.15\n", "", 0),
                ("Cuda compilation tools, release 12.4\n", "", 0),
            ]
            result = scan_gpus()
            assert result.nvidia_smi_available
            assert result.total_gpu_count == 1
            assert result.total_memory_mb == 81920
            assert result.cuda_available
            assert result.cuda_version == "12.4"


class TestGetGPUMemoryUsagePct:
    def test_with_gpus(self):
        mock_stdout = "0, GPU1, 10000, 8000, 2000, 50, 60\n"
        with patch("benchmark.gpu_scanner._parse_nvidia_smi_query", return_value=[
            GPUInfo(index=0, name="GPU1", memory_total_mb=10000, memory_used_mb=2000)
        ]):
            pct = get_gpu_memory_usage_pct()
            assert pct == 20.0

    def test_no_gpus(self):
        with patch("benchmark.gpu_scanner._parse_nvidia_smi_query", return_value=[]):
            pct = get_gpu_memory_usage_pct()
            assert pct == 0.0


class TestGetGPUUtilizationPct:
    def test_with_gpus(self):
        with patch("benchmark.gpu_scanner._parse_nvidia_smi_query", return_value=[
            GPUInfo(index=0, name="GPU1", memory_total_mb=10000, utilization_pct=75),
            GPUInfo(index=1, name="GPU2", memory_total_mb=10000, utilization_pct=85),
        ]):
            pct = get_gpu_utilization_pct()
            assert pct == 80.0

    def test_no_gpus(self):
        with patch("benchmark.gpu_scanner._parse_nvidia_smi_query", return_value=[]):
            pct = get_gpu_utilization_pct()
            assert pct == 0.0


class TestFormatScanReport:
    def test_with_errors(self):
        result = GPUScanResult(errors=["No GPU found"])
        report = format_scan_report(result)
        assert "ERROR" in report
        assert "No GPU found" in report

    def test_with_gpus(self):
        result = GPUScanResult(
            gpus=[GPUInfo(index=0, name="NVIDIA A100", memory_total_mb=81920, memory_used_mb=10000, utilization_pct=80, temperature_c=55)],
            total_gpu_count=1,
            total_memory_mb=81920,
            cuda_available=True,
            cuda_version="12.4",
            driver_version="550.54",
            nvidia_smi_available=True,
        )
        report = format_scan_report(result)
        assert "NVIDIA A100" in report
        assert "81920" in report
        assert "12.4" in report
        assert "550.54" in report
