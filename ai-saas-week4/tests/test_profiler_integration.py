import json
import os
import pytest

from profiler.config import ProfilerConfig, default_config
from profiler.core import (
    ProfilingTrace,
    ProfilingEvent,
    CpuProfiler,
    ProfileManager,
    TorchProfilerRunner,
)
from profiler.phase_analyzer import PhaseAnalyzer
from profiler.bottleneck import BottleneckDetector, Bottleneck
from profiler.flame_graph import FlameGraphGenerator
from profiler.report import ProfilingReportGenerator
from profiler.comparator import ProfileComparator
from profiler.runner import ProfilingRunner
from profiler.llm_analyzer import LLMAnalyzer


class TestPhaseAnalysisIntegration:
    """Integration test: PhaseAnalyzer --> BottleneckDetector"""

    def test_phase_analysis_feeds_bottleneck_detection(self, temp_dir):
        config = ProfilerConfig(
            output_dir=temp_dir,
            bottleneck_min_time_us=10.0,
        )

        events = [
            ProfilingEvent("prefill_forward", "compute", 0, 500, 500, cpu_time_us=500),
            ProfilingEvent("decode_sampling", "compute", 0, 300, 300, cpu_time_us=300),
            ProfilingEvent("json_dumps_encode", "cpu", 0, 400, 400, cpu_time_us=400),
            ProfilingEvent("http_send_response", "network", 0, 600, 600, cpu_time_us=600),
            ProfilingEvent("cuda_launch_kernel", "gpu", 0, 150, 150, cpu_time_us=150),
        ]
        trace = ProfilingTrace(events=events, total_duration_us=1950)

        analyzer = PhaseAnalyzer(config)
        trace = analyzer.analyze_phases(trace)

        detected_phases = set(e.phase for e in trace.events if e.phase)
        assert "serialization" in detected_phases
        assert "network_io" in detected_phases
        assert "kernel" in detected_phases
        assert "prefill" in detected_phases
        assert "decode" in detected_phases

        detector = BottleneckDetector(config)
        bottlenecks = detector.detect(trace)
        assert len(bottlenecks) > 0

    def test_phase_distribution_in_report(self, temp_dir):
        config = ProfilerConfig(output_dir=temp_dir)
        generator = ProfilingReportGenerator(config)

        events = [
            ProfilingEvent("prefill_op", "compute", 0, 400, 400, cpu_time_us=400),
            ProfilingEvent("decode_op", "compute", 0, 300, 300, cpu_time_us=300),
            ProfilingEvent("network_op", "network", 0, 300, 300, cpu_time_us=300),
        ]
        trace = ProfilingTrace(events=events, total_duration_us=1000)

        report = generator.generate_full_report(trace)

        assert "prefill" in report["phase_distribution"]
        assert report["phase_distribution"]["prefill"]["percentage"] == 40.0
        assert "decode" in report["phase_distribution"]
        assert report["phase_distribution"]["decode"]["percentage"] == 30.0


class TestProfilingPipelineIntegration:
    """Integration test: CPU Profiler --> ProfileManager --> Report Generator"""

    def test_profiler_to_report_pipeline(self, temp_dir):
        config = ProfilerConfig(output_dir=temp_dir)
        manager = ProfileManager(config)

        def workload():
            data = {}
            for i in range(1000):
                data[f"key_{i}"] = json.dumps({"value": i, "data": [j for j in range(100)]})
            for i in range(1000):
                _ = json.loads(data.get(f"key_{i}", "{}"))
            return len(data)

        trace, result = manager.run_cpu_profile(workload)
        assert result == 1000

        path = manager.save_trace(trace, "pipeline_test.json")
        loaded = manager.load_trace("pipeline_test.json")
        assert loaded.total_duration_us == trace.total_duration_us

        generator = ProfilingReportGenerator(config)
        report = generator.generate_and_save_all(loaded)
        assert "summary" in report
        assert report["summary"]["total_events"] >= 0

        files = os.listdir(temp_dir)
        assert any("profiling_report" in f for f in files)
        assert any("flame_graph" in f for f in files)
        assert any("phase_report" in f for f in files)


class TestBottleneckToReportIntegration:
    """Integration test: BottleneckDetector --> ProfilingReportGenerator"""

    def test_bottlenecks_integrated_in_report(self, temp_dir):
        config = ProfilerConfig(output_dir=temp_dir, bottleneck_top_n=3)
        generator = ProfilingReportGenerator(config)

        events = [
            ProfilingEvent("json_loads_encode", "cpu", 0, 2000, 2000, cpu_time_us=2000),
            ProfilingEvent("json_dumps_decode", "cpu", 0, 1500, 1500, cpu_time_us=1500),
            ProfilingEvent("http_send", "network", 0, 3000, 3000, cpu_time_us=3000),
            ProfilingEvent("cuda_launch_kernel", "gpu", 0, 800, 800, cpu_time_us=800),
            ProfilingEvent("lock_acquire", "sync", 0, 500, 500, cpu_time_us=500),
        ]
        trace = ProfilingTrace(events=events, total_duration_us=7800)

        report = generator.generate_and_save_all(trace)
        bottlenecks = report.get("bottlenecks", [])

        assert len(bottlenecks) > 0
        assert len(bottlenecks) <= 3

        for b in bottlenecks:
            assert "rank" in b
            assert "name" in b
            assert "category" in b
            assert "suggestion" in b
            assert "code_location" in b
            assert "expected_improvement" in b
            assert "verification_command" in b
            assert b["impact_pct"] > 0

        md_report_path = None
        for f in os.listdir(temp_dir):
            if "profiling_report" in f and f.endswith(".md"):
                md_report_path = os.path.join(temp_dir, f)
                break

        assert md_report_path is not None
        with open(md_report_path) as f:
            md_content = f.read()

        assert "Bottleneck" in md_content
        for b in bottlenecks:
            assert b["name"] in md_content


class TestComparisonIntegration:
    """Integration test: ProfilingRunner --> ProfileComparator"""

    def test_full_compare_workflow(self, temp_dir):
        config = ProfilerConfig(output_dir=temp_dir)
        runner = ProfilingRunner(config)

        def slow_workload():
            data = {}
            for i in range(50):
                data[f"k_{i}"] = json.dumps({"v": i})
            for i in range(50):
                _ = json.loads(data.get(f"k_{i}", "{}"))
            return len(data)

        results = runner.run_full_pipeline(slow_workload, num_steps=3)

        assert "comparison" in results
        comparison = results["comparison"]
        assert "summary" in comparison
        assert "metrics" in comparison
        assert comparison["summary"]["p99_latency_improvement_pct"] is not None
        assert comparison["summary"]["throughput_improvement_pct"] is not None

        files = runner.get_output_files()
        assert any("comparison" in f.lower() for f in files)


class TestFlameGraphToReportIntegration:
    """Integration test: FlameGraph --> Report Generator"""

    def test_flame_graph_data_in_report(self, temp_dir):
        config = ProfilerConfig(output_dir=temp_dir)
        generator = ProfilingReportGenerator(config)

        events = [
            ProfilingEvent("func_a", "compute", 0, 300, 300, cpu_time_us=300, stack=["main", "a"]),
            ProfilingEvent("func_b", "compute", 0, 200, 200, cpu_time_us=200, stack=["main", "b"]),
        ]
        trace = ProfilingTrace(events=events, total_duration_us=500)

        report = generator.generate_full_report(trace)
        flame_data = report.get("flame_graph_data", {})

        assert flame_data["name"] == "root"
        assert flame_data["value"] > 0

        flame_gen = FlameGraphGenerator(config)
        html_path = flame_gen.generate_flame_graph_html(trace)
        svg_path = flame_gen.generate_flame_graph_svg(trace)

        assert os.path.exists(html_path)
        assert os.path.exists(svg_path)

        with open(html_path) as f:
            html = f.read()
        assert "Flame Graph" in html


class TestLLMAnalyzerIntegration:
    """Integration test: LLMAnalyzer + Report Generator"""

    def test_llm_analysis_in_report(self, temp_dir):
        config = ProfilerConfig(output_dir=temp_dir, llm_enabled=False)
        generator = ProfilingReportGenerator(config)

        events = [
            ProfilingEvent("prefill_forward", "compute", 0, 400, 400, cpu_time_us=400),
            ProfilingEvent("decode_sampling", "compute", 0, 300, 300, cpu_time_us=300),
            ProfilingEvent("http_send", "network", 0, 300, 300, cpu_time_us=300),
        ]
        trace = ProfilingTrace(events=events, total_duration_us=1000)

        report = generator.generate_and_save_all(trace)
        analysis = report.get("natural_language_analysis", "")
        assert len(analysis) > 0
        assert "Executive Summary" in analysis
        assert "Bottleneck Analysis" in analysis


class TestRunnerIntegration:
    """Integration test: complete runner workflow"""

    def test_runner_full_workflow(self, temp_dir):
        config = ProfilerConfig(output_dir=temp_dir)
        runner = ProfilingRunner(config)

        def workload():
            total = 0
            for i in range(1000):
                total += i * 0.5
            return total

        results = runner.run_full_pipeline(workload, num_steps=5)

        assert results["before_report"]["summary"]["total_events"] >= 0
        assert results["after_report"]["summary"]["total_events"] >= 0

        files = os.listdir(temp_dir)
        assert any(f.endswith(".json") for f in files)
        assert any(f.endswith(".md") for f in files)
        assert any(f.endswith(".svg") for f in files)

    def test_runner_archive(self, temp_dir):
        config = ProfilerConfig(output_dir=temp_dir, auto_archive=True)
        runner = ProfilingRunner(config)

        os.makedirs(temp_dir, exist_ok=True)
        with open(os.path.join(temp_dir, "existing.txt"), "w") as f:
            f.write("data")

        runner.archive_existing_results()

        archives = [d for d in os.listdir(temp_dir) if d.startswith("archive_")]
        assert len(archives) >= 1


class TestEndToEndProfiling:
    """End-to-end tests for complete profiling pipeline"""

    def test_e2e_profiling_complete_pipeline(self, temp_dir):
        config = ProfilerConfig(
            output_dir=temp_dir,
            active_steps=3,
            bottleneck_top_n=3,
            auto_archive=True,
        )

        def realistic_workload():
            import json as _json
            import time as _time

            total_data = {}
            for i in range(3):
                key = f"request_{i}"
                data = {"id": i, "messages": [{"role": "user", "content": "Hello" * 10}]}
                total_data[key] = _json.dumps(data)

            for key, value in total_data.items():
                parsed = _json.loads(value)
                _ = parsed["messages"][0]["content"][:20]

            _time.sleep(0.01)

            for _ in range(2):
                _ = sum(i * 0.01 for i in range(100))

            return len(total_data)

        runner = ProfilingRunner(config)
        results = runner.run_full_pipeline(realistic_workload, num_steps=3)

        before = results["before_report"]
        assert before["summary"]["total_duration_ms"] > 0

        bottlenecks = before.get("bottlenecks", [])
        assert len(bottlenecks) <= 3

        comparison = results["comparison"]
        summary = comparison["summary"]
        assert "p99_latency_improvement_pct" in summary
        assert "throughput_improvement_pct" in summary
        assert "overall_improvement_pct" in summary

        output_files = os.listdir(temp_dir)
        required_types = {".json": False, ".md": False, ".svg": False}
        for f in output_files:
            for ext in required_types:
                if f.endswith(ext):
                    required_types[ext] = True

        assert required_types[".json"], "Missing JSON report"
        assert required_types[".md"], "Missing Markdown report"

    def test_e2e_bottleneck_verification_command(self, temp_dir):
        config = ProfilerConfig(output_dir=temp_dir, bottleneck_top_n=3)

        events = [
            ProfilingEvent("json_dumps_encode_request", "cpu", 0, 5000, 5000, cpu_time_us=5000),
            ProfilingEvent("json_loads_decode_response", "cpu", 0, 4000, 4000, cpu_time_us=4000),
            ProfilingEvent("http_send_response", "network", 0, 8000, 8000, cpu_time_us=8000),
        ]
        trace = ProfilingTrace(events=events, total_duration_us=17000)

        detector = BottleneckDetector(config)
        phase_analyzer = PhaseAnalyzer(config)
        phase_analyzer.analyze_phases(trace)

        bottlenecks = detector.detect(trace)

        for b in bottlenecks:
            assert b.verification_command, f"Bottleneck {b.name} has no verification command"
            assert "profiler" in b.verification_command.lower() or "python" in b.verification_command.lower()
            assert b.code_location, f"Bottleneck {b.name} has no code location"
            assert b.expected_improvement, f"Bottleneck {b.name} has no expected improvement"

    def test_e2e_optimization_suggestions_are_actionable(self, temp_dir):
        config = ProfilerConfig(output_dir=temp_dir)
        generator = ProfilingReportGenerator(config)

        events = [
            ProfilingEvent("json_loads", "cpu", 0, 2000, 2000, cpu_time_us=2000),
            ProfilingEvent("asyncio_lock_acquire", "sync", 0, 1500, 1500, cpu_time_us=1500),
            ProfilingEvent("socket_send_response", "network", 0, 3000, 3000, cpu_time_us=3000),
        ]
        trace = ProfilingTrace(events=events, total_duration_us=6500)

        report = generator.generate_and_save_all(trace)
        bottlenecks = report.get("bottlenecks", [])

        for b in bottlenecks:
            suggestion = b.get("suggestion", "")
            assert len(suggestion) > 20, f"Suggestion too short for bottleneck '{b['name']}'"

            code_loc = b.get("code_location", "")
            assert code_loc, f"Missing code location for bottleneck '{b['name']}'"

    def test_e2e_deterministic_detection(self, temp_dir):
        config = ProfilerConfig(output_dir=temp_dir)

        events = [
            ProfilingEvent("json_dumps_encode", "cpu", 0, 1000, 1000, cpu_time_us=1000),
            ProfilingEvent("json_dumps_encode", "cpu", 0, 1000, 1000, cpu_time_us=1000),
            ProfilingEvent("json_dumps_encode", "cpu", 0, 1000, 1000, cpu_time_us=1000),
        ]
        trace = ProfilingTrace(events=events, total_duration_us=3000)

        detector = BottleneckDetector(config)
        phase_analyzer = PhaseAnalyzer(config)
        phase_analyzer.analyze_phases(trace)

        bottlenecks_1 = detector.detect(trace)
        bottlenecks_2 = detector.detect(trace)

        assert len(bottlenecks_1) == len(bottlenecks_2)
        for b1, b2 in zip(bottlenecks_1, bottlenecks_2):
            assert b1.name == b2.name
            assert b1.impact_us == b2.impact_us
            assert b1.impact_pct == b2.impact_pct
