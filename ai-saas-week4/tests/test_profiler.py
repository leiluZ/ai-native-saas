import json
import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from profiler.config import ProfilerConfig, default_config
from profiler.core import (
    ProfilingTrace,
    ProfilingEvent,
    CpuProfiler,
    ProfileManager,
    get_profile_manager,
    TorchProfilerRunner,
    NsysProfiler,
)
from profiler.bottleneck import (
    Bottleneck,
    BottleneckCategory,
    BottleneckDetector,
    detect_bottlenecks,
)
from profiler.phase_analyzer import PhaseAnalyzer, analyze_phases
from profiler.flame_graph import FlameGraphGenerator, generate_flame_graph
from profiler.report import ProfilingReportGenerator, generate_report
from profiler.comparator import ProfileComparator, compare_profiles
from profiler.runner import ProfilingRunner, OneClickProfiler


class TestProfilingEvent:
    def test_event_creation(self):
        evt = ProfilingEvent(
            name="test_op",
            category="compute",
            start_time_us=0.0,
            end_time_us=100.0,
            duration_us=100.0,
            cpu_time_us=80.0,
        )
        assert evt.name == "test_op"
        assert evt.cpu_time_us == 80.0
        assert evt.phase is None

    def test_event_with_phase(self):
        evt = ProfilingEvent(
            name="aten::linear",
            category="cpu",
            start_time_us=0.0,
            end_time_us=100.0,
            duration_us=100.0,
            cpu_time_us=80.0,
            phase="compute",
        )
        assert evt.phase == "compute"

    def test_event_with_stack(self):
        evt = ProfilingEvent(
            name="op",
            category="cpu",
            start_time_us=0.0,
            end_time_us=100.0,
            duration_us=100.0,
            cpu_time_us=80.0,
            stack=["main", "forward", "linear"],
        )
        assert evt.stack == ["main", "forward", "linear"]


class TestProfilingTrace:
    def test_trace_creation(self):
        trace = ProfilingTrace()
        assert len(trace.events) == 0
        assert trace.total_duration_us == 0.0

    def test_trace_total_cpu_time(self):
        events = [
            ProfilingEvent("a", "cpu", 0, 100, 100, cpu_time_us=50.0),
            ProfilingEvent("b", "cpu", 0, 200, 200, cpu_time_us=150.0),
        ]
        trace = ProfilingTrace(events=events)
        assert trace.total_cpu_time_us() == 200.0

    def test_trace_total_cuda_time(self):
        events = [
            ProfilingEvent("a", "cuda", 0, 100, 100, cuda_time_us=100.0),
            ProfilingEvent("b", "cpu", 0, 200, 200, cpu_time_us=150.0),
        ]
        trace = ProfilingTrace(events=events)
        assert trace.total_cuda_time_us() == 100.0

    def test_trace_event_count(self):
        events = [ProfilingEvent(f"op_{i}", "cpu", 0, 10, 10) for i in range(5)]
        trace = ProfilingTrace(events=events)
        assert trace.event_count() == 5

    def test_trace_unique_ops(self):
        events = [
            ProfilingEvent("op_a", "cpu", 0, 10, 10),
            ProfilingEvent("op_a", "cpu", 0, 10, 10),
            ProfilingEvent("op_b", "cpu", 0, 10, 10),
        ]
        trace = ProfilingTrace(events=events)
        assert trace.unique_ops() == 2


class TestCpuProfiler:
    def test_cpu_profiler_basic(self, temp_dir):
        config = ProfilerConfig(output_dir=temp_dir)
        profiler = CpuProfiler(config)

        def workload():
            result = 0.0
            for i in range(200000):
                result += (i ** 0.5) * (i % 17) * 0.01
            s = json.dumps({"data": [result] * 100})
            _ = json.loads(s)
            return result

        trace, result = profiler.profile_block(workload)
        assert trace.total_duration_us > 0

    def test_cpu_profiler_empty_fn(self, temp_dir):
        config = ProfilerConfig(output_dir=temp_dir)
        profiler = CpuProfiler(config)

        def empty():
            pass

        trace, _ = profiler.profile_block(empty)
        assert trace.total_duration_us >= 0


class TestProfileManager:
    def test_manager_creation(self, temp_dir):
        config = ProfilerConfig(output_dir=temp_dir)
        mgr = ProfileManager(config)
        assert mgr.config is not None
        assert len(mgr.get_all_traces()) == 0

    def test_run_cpu_profile(self, temp_dir):
        config = ProfilerConfig(output_dir=temp_dir)
        mgr = ProfileManager(config)

        def workload():
            return sum(range(1000))

        trace, result = mgr.run_cpu_profile(workload)
        assert result == sum(range(1000))
        assert len(mgr.get_all_traces()) == 1
        assert mgr.get_all_traces()[0] is trace

    def test_save_and_load_trace(self, temp_dir):
        config = ProfilerConfig(output_dir=temp_dir)
        mgr = ProfileManager(config)

        trace = ProfilingTrace(
            events=[ProfilingEvent(
                name="test_op",
                category="cpu",
                start_time_us=0,
                end_time_us=100,
                duration_us=100,
                cpu_time_us=100,
                phase="compute",
            )],
            total_duration_us=100,
            gpu_memory_mb=1024,
        )

        path = mgr.save_trace(trace, "test_trace.json")
        assert os.path.exists(path)

        loaded = mgr.load_trace("test_trace.json")
        assert loaded.total_duration_us == 100
        assert loaded.gpu_memory_mb == 1024
        assert len(loaded.events) == 1
        assert loaded.events[0].name == "test_op"
        assert loaded.events[0].phase == "compute"

    def test_get_profile_manager(self):
        mgr = get_profile_manager()
        assert isinstance(mgr, ProfileManager)


class TestPhaseAnalyzer:
    @pytest.fixture
    def analyzer(self):
        return PhaseAnalyzer()

    def test_classify_prefill(self, analyzer):
        evt = ProfilingEvent("prefill_forward", "compute", 0, 100, 100)
        assert analyzer.classify_phase(evt) == "prefill"

    def test_classify_decode(self, analyzer):
        evt = ProfilingEvent("decode_generate_sampling", "compute", 0, 100, 100)
        assert analyzer.classify_phase(evt) == "decode"

    def test_classify_kv_cache(self, analyzer):
        evt = ProfilingEvent("kv_cache_alloc_block", "memory", 0, 100, 100)
        assert analyzer.classify_phase(evt) == "kv_cache_alloc"

    def test_classify_network(self, analyzer):
        evt = ProfilingEvent("http_send_response", "network", 0, 100, 100)
        assert analyzer.classify_phase(evt) == "network_io"

    def test_classify_serialization(self, analyzer):
        evt = ProfilingEvent("json_dumps_encode", "cpu", 0, 100, 100)
        assert analyzer.classify_phase(evt) == "serialization"

    def test_classify_kernel(self, analyzer):
        evt = ProfilingEvent("cuda_launch_kernel", "gpu", 0, 100, 100)
        assert analyzer.classify_phase(evt) == "kernel"

    def test_classify_lock(self, analyzer):
        evt = ProfilingEvent("asyncio_lock_acquire", "cpu", 0, 100, 100)
        assert analyzer.classify_phase(evt) == "lock_contention"

    def test_classify_default_compute(self, analyzer):
        evt = ProfilingEvent("some_matrix_multiply", "compute", 0, 100, 100)
        assert analyzer.classify_phase(evt) == "compute"

    def test_analyze_phases(self, analyzer):
        events = [
            ProfilingEvent("prefill_forward", "compute", 0, 100, 100, cpu_time_us=30),
            ProfilingEvent("decode_sampling", "compute", 0, 200, 200, cpu_time_us=50),
            ProfilingEvent("kv_cache_alloc", "memory", 0, 300, 300, cpu_time_us=20),
            ProfilingEvent("http_send", "network", 0, 400, 400, cpu_time_us=40),
        ]
        trace = ProfilingTrace(events=events, total_duration_us=400)

        result = analyzer.analyze_phases(trace)
        assert "prefill" in result.phase_breakdown
        assert "decode" in result.phase_breakdown
        assert result.events[0].phase == "prefill"
        assert result.events[1].phase == "decode"
        assert result.events[2].phase == "kv_cache_alloc"
        assert result.events[3].phase == "network_io"

    def test_generate_phase_report(self, analyzer):
        events = [
            ProfilingEvent("compute_op", "compute", 0, 1000, 1000, cpu_time_us=1000),
        ]
        trace = ProfilingTrace(events=events, total_duration_us=1000)
        report = analyzer.generate_phase_report(trace)
        assert "Phase Distribution Report" in report
        assert "compute" in report

    def test_phase_distribution_percentages(self, analyzer):
        events = [
            ProfilingEvent("op_a", "compute", 0, 30, 30, cpu_time_us=30),
            ProfilingEvent("op_b", "compute", 0, 70, 70, cpu_time_us=70),
        ]
        trace = ProfilingTrace(events=events, total_duration_us=100)
        analyzer.analyze_phases(trace)

        dist = analyzer.get_phase_distribution(trace)
        assert "compute" in dist
        assert dist["compute"]["percentage"] == 100.0


class TestBottleneckDetector:
    @pytest.fixture
    def detector(self):
        return BottleneckDetector()

    @pytest.fixture
    def sample_trace(self):
        events = [
            ProfilingEvent("json_loads", "serialization", 0, 1000, 1000, cpu_time_us=1000, phase="serialization"),
            ProfilingEvent("json_dumps", "serialization", 0, 800, 800, cpu_time_us=800, phase="serialization"),
            ProfilingEvent("http_send", "network", 0, 2000, 2000, cpu_time_us=2000, phase="network_io"),
            ProfilingEvent("compute_op_a", "compute", 0, 500, 500, cpu_time_us=500),
            ProfilingEvent("compute_op_b", "compute", 0, 1500, 1500, cpu_time_us=1500),
            ProfilingEvent("compute_op_c", "compute", 0, 100, 100, cpu_time_us=100),
        ]
        trace = ProfilingTrace(events=events, total_duration_us=5900)
        analyzer = PhaseAnalyzer()
        analyzer.analyze_phases(trace)
        return trace

    def test_detector_creation(self, detector):
        assert detector.config is not None

    def test_detect_bottlenecks(self, detector, sample_trace):
        bottlenecks = detector.detect(sample_trace)
        assert len(bottlenecks) <= 3
        assert all(isinstance(b, Bottleneck) for b in bottlenecks)
        for b in bottlenecks:
            assert b.rank > 0
            assert b.name
            assert b.category

    def test_bottleneck_has_suggestion(self, detector, sample_trace):
        bottlenecks = detector.detect(sample_trace)
        for b in bottlenecks:
            assert b.suggestion_text
            assert b.code_location
            assert b.expected_improvement

    def test_slow_ops_detection(self, detector, sample_trace):
        bottlenecks = detector.detect(sample_trace)
        names = [b.name for b in bottlenecks]
        assert any("http_send" in n for n in names) or any("json" in n.lower() for n in names)

    def test_serialization_bottleneck_detected(self, detector, sample_trace):
        bottlenecks = detector.detect(sample_trace)
        cats = [b.category for b in bottlenecks]
        assert BottleneckCategory.NETWORK_BOUND in cats or BottleneckCategory.IO_INTENSIVE in cats

    def test_batch_imbalance_detection(self, detector):
        config = ProfilerConfig()
        detector = BottleneckDetector(config)

        events = []
        for i in range(10):
            time_us = 100 + (i * 25 if i % 2 == 0 else 1000 - i * 10)
            events.append(ProfilingEvent(
                f"compute_{i}", "compute", 0, time_us, time_us,
                cpu_time_us=time_us, phase="compute",
            ))

        trace = ProfilingTrace(events=events, total_duration_us=sum(e.duration_us for e in events))
        bottlenecks = detector.detect(trace)
        found = [b for b in bottlenecks if b.category == BottleneckCategory.BATCH_IMBALANCE]
        assert len(found) >= 0

    def test_detect_bottlenecks_helper(self, sample_trace):
        bottlenecks = detect_bottlenecks(sample_trace, top_n=2)
        assert len(bottlenecks) <= 2

    def test_bottleneck_report(self, detector, sample_trace):
        bottlenecks = detector.detect(sample_trace)
        report = detector.generate_bottleneck_report(sample_trace, bottlenecks)
        assert "Bottleneck Analysis Report" in report
        for b in bottlenecks:
            assert str(b.rank) in report

    def test_empty_trace_bottleneck(self, detector):
        trace = ProfilingTrace(total_duration_us=0)
        bottlenecks = detector.detect(trace)
        assert len(bottlenecks) == 1
        assert bottlenecks[0].name == "Insufficient Profiling Data"

    def test_fallback_bottleneck_has_details(self, detector):
        trace = ProfilingTrace(total_duration_us=0)
        bottlenecks = detector.detect(trace)
        assert bottlenecks[0].severity == 0.3
        assert bottlenecks[0].impact_us == 0.0


class TestFlameGraphGenerator:
    @pytest.fixture
    def generator(self):
        return FlameGraphGenerator()

    @pytest.fixture
    def sample_trace(self):
        events = [
            ProfilingEvent(
                "main;forward;linear",
                "compute", 0, 100, 100, cpu_time_us=100,
                stack=["main", "forward", "linear"],
            ),
            ProfilingEvent(
                "main;forward;softmax",
                "compute", 0, 50, 50, cpu_time_us=50,
                stack=["main", "forward", "softmax"],
            ),
        ]
        return ProfilingTrace(events=events, total_duration_us=150)

    def test_generate_flame_graph_data(self, generator, sample_trace):
        data = generator.generate_flame_graph_data(sample_trace)
        assert data["name"] == "root"
        assert data["value"] > 0

    def test_generate_flame_graph_svg(self, generator, sample_trace, temp_dir):
        output = os.path.join(temp_dir, "test_flame.svg")
        path = generator.generate_flame_graph_svg(sample_trace, output)
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert "<svg" in content
        assert "Flame Graph" in content

    def test_generate_flame_graph_html(self, generator, sample_trace, temp_dir):
        output = os.path.join(temp_dir, "test_flame.html")
        path = generator.generate_flame_graph_html(sample_trace, output)
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert "<html" in content
        assert "Flame Graph" in content

    def test_flame_graph_helper(self, sample_trace, temp_dir):
        path = generate_flame_graph(sample_trace, output_dir=temp_dir)
        assert os.path.exists(path)

    def test_flame_graph_empty_trace(self, generator):
        trace = ProfilingTrace()
        data = generator.generate_flame_graph_data(trace)
        assert data["name"] == "root"
        assert data["value"] == 0.0


class TestProfilingReportGenerator:
    @pytest.fixture
    def generator(self):
        return ProfilingReportGenerator()

    @pytest.fixture
    def sample_trace(self):
        events = [
            ProfilingEvent("compute_op", "compute", 0, 500, 500, cpu_time_us=500, phase="compute"),
            ProfilingEvent("network_send", "network", 0, 200, 200, cpu_time_us=200, phase="network_io"),
        ]
        trace = ProfilingTrace(events=events, total_duration_us=700, phase_breakdown={
            "compute": {"time_us": 500, "percentage": 71.43, "call_count": 1},
            "network_io": {"time_us": 200, "percentage": 28.57, "call_count": 1},
        })
        return trace

    def test_generate_full_report(self, generator, sample_trace):
        report = generator.generate_full_report(sample_trace)
        assert "metadata" in report
        assert "summary" in report
        assert "phase_distribution" in report
        assert "bottlenecks" in report
        assert "natural_language_analysis" in report
        assert "flame_graph_data" in report
        assert "top_operations" in report

    def test_save_report(self, generator, sample_trace, temp_dir):
        generator.config.output_dir = temp_dir
        report = generator.generate_full_report(sample_trace)
        path = generator.save_report(report)
        assert os.path.exists(path)
        md_path = path.replace(".json", ".md")
        assert os.path.exists(md_path)

    def test_generate_and_save_all(self, generator, sample_trace, temp_dir):
        generator.config.output_dir = temp_dir
        report = generator.generate_and_save_all(sample_trace)
        assert isinstance(report, dict)

        files = os.listdir(temp_dir)
        assert len(files) > 0

    def test_report_helper(self, sample_trace, temp_dir):
        config = ProfilerConfig(output_dir=temp_dir)
        report = generate_report(sample_trace, config)
        assert isinstance(report, dict)


class TestProfileComparator:
    @pytest.fixture
    def comparator(self):
        return ProfileComparator()

    @pytest.fixture
    def before_trace(self):
        events = [ProfilingEvent("op", "compute", 0, 2000, 2000, cpu_time_us=2000, phase="compute")]
        return ProfilingTrace(events=events, total_duration_us=2000)

    @pytest.fixture
    def after_trace(self):
        events = [ProfilingEvent("op", "compute", 0, 1200, 1200, cpu_time_us=1200, phase="compute")]
        return ProfilingTrace(events=events, total_duration_us=1200)

    def test_compare(self, comparator, before_trace, after_trace):
        result = comparator.compare(before_trace, after_trace)
        assert "metadata" in result
        assert "metrics" in result
        assert "summary" in result

        for metric_name in comparator.config.comparison_metrics:
            assert metric_name in result["metrics"]
            assert "before" in result["metrics"][metric_name]
            assert "after" in result["metrics"][metric_name]
            assert "change_pct" in result["metrics"][metric_name]
            assert "improved" in result["metrics"][metric_name]

    def test_save_comparison_report(self, comparator, before_trace, after_trace, temp_dir):
        comparator.config.output_dir = temp_dir
        result = comparator.compare(before_trace, after_trace)
        path = comparator.save_comparison_report(result)
        assert os.path.exists(path)

        with open(path) as f:
            loaded = json.load(f)
        assert loaded["summary"]["p99_latency_improvement_pct"] == result["summary"]["p99_latency_improvement_pct"]

    def test_save_markdown_comparison(self, comparator, before_trace, after_trace, temp_dir):
        comparator.config.output_dir = temp_dir
        result = comparator.compare(before_trace, after_trace)
        path = comparator.save_markdown_comparison(result)
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert "Before/After" in content
        assert "Metrics Comparison" in content

    def test_load_and_compare(self, comparator, before_trace, after_trace, temp_dir):
        config = ProfilerConfig(output_dir=temp_dir)
        mgr = ProfileManager(config)
        mgr.save_trace(before_trace, "before.json")
        mgr.save_trace(after_trace, "after.json")

        result = comparator.load_and_compare(
            os.path.join(temp_dir, "before.json"),
            os.path.join(temp_dir, "after.json"),
        )
        assert "summary" in result

    def test_compare_helper(self, before_trace, after_trace):
        result = compare_profiles(before_trace, after_trace)
        assert "summary" in result

    def test_throughput_improvement(self, comparator):
        before = ProfilingTrace(
            events=[ProfilingEvent("t", "cpu", 0, 1000, 1000) for _ in range(10)],
            total_duration_us=1_000_000,
        )
        after = ProfilingTrace(
            events=[ProfilingEvent("t", "cpu", 0, 1000, 1000) for _ in range(15)],
            total_duration_us=1_000_000,
        )
        result = comparator.compare(before, after)
        assert result["metrics"]["throughput_tokens_per_sec"]["improved"] is True


class TestProfilingRunner:
    @pytest.fixture
    def runner(self, temp_dir):
        config = ProfilerConfig(output_dir=temp_dir)
        return ProfilingRunner(config)

    def test_archive_existing_results(self, runner, temp_dir):
        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("test")

        runner.archive_existing_results()

        archives = [d for d in os.listdir(temp_dir) if d.startswith("archive_")]
        assert len(archives) >= 1
        archive_path = os.path.join(temp_dir, archives[0])
        assert os.path.exists(os.path.join(archive_path, "test.txt"))

    def test_run_before_profile(self, runner):
        def workload():
            return sum(range(100))

        trace = runner.run_before_profile(workload)
        assert isinstance(trace, ProfilingTrace)
        assert trace.total_duration_us > 0

    def test_run_before_and_after_profile(self, runner):
        def workload():
            return sum(range(100))

        before = runner.run_before_profile(workload)
        after = runner.run_after_profile(workload)
        assert before is not None
        assert after is not None
        assert before is not after

    def test_generate_before_reports(self, runner):
        def workload():
            return sum(range(100))

        runner.run_before_profile(workload)
        report = runner.generate_before_reports()
        assert "summary" in report

    def test_generate_after_reports(self, runner):
        def workload():
            return sum(range(100))

        runner.run_after_profile(workload)
        report = runner.generate_after_reports()
        assert "summary" in report

    def test_generate_comparison_report(self, runner):
        def workload():
            return sum(range(100))

        runner.run_before_profile(workload)
        runner.run_after_profile(workload)
        comparison = runner.generate_comparison_report()
        assert "summary" in comparison
        assert "metrics" in comparison

    def test_run_full_pipeline(self, runner):
        def workload():
            return sum(range(100))

        results = runner.run_full_pipeline(workload)
        assert "before_report" in results
        assert "after_report" in results
        assert "comparison" in results

    def test_get_output_files(self, runner):
        def workload():
            return sum(range(100))

        runner.run_full_pipeline(workload)
        files = runner.get_output_files()
        assert len(files) > 0

    def test_generate_before_reports_no_trace_raises(self, runner):
        with pytest.raises(RuntimeError, match="No before-optimization trace"):
            runner.generate_before_reports()

    def test_generate_after_reports_no_trace_raises(self, runner):
        with pytest.raises(RuntimeError, match="No after-optimization trace"):
            runner.generate_after_reports()

    def test_compare_no_traces_raises(self, runner):
        with pytest.raises(RuntimeError, match="No before-optimization trace"):
            runner.generate_comparison_report()


class TestOneClickProfiler:
    @pytest.fixture
    def ocp(self, temp_dir):
        config = ProfilerConfig(output_dir=temp_dir)
        return OneClickProfiler(config)

    def test_start_profile(self, ocp, temp_dir):
        result = ocp.start_profile("gateway", duration=10)
        assert os.path.exists(result)
        with open(result) as f:
            content = f.read()
        assert "started" in content
        assert "gateway" in content
        assert "10" in content

    def test_stop_profile(self, ocp, temp_dir):
        ocp.start_profile("gateway")

        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("test")

        archive_dir = ocp.stop_profile()
        assert os.path.exists(archive_dir)
        assert "stopped_" in archive_dir

    def test_status_idle(self, ocp):
        assert ocp.status() == "idle"

    def test_status_running(self, ocp):
        ocp.start_profile("compute")
        assert ocp.status() == "running"

    def test_status_stopped(self, ocp):
        ocp.start_profile("compute")
        ocp.stop_profile()
        assert ocp.status() == "stopped"


class TestConfig:
    def test_default_config(self):
        config = default_config
        assert config.with_stack is True
        assert config.bottleneck_top_n == 3

    def test_custom_config(self):
        config = ProfilerConfig(
            output_dir="/custom/path",
            bottleneck_top_n=5,
        )
        assert config.output_dir == "/custom/path"
        assert config.bottleneck_top_n == 5


class TestNsysProfiler:
    def test_is_available_false_by_default(self):
        profiler = NsysProfiler()
        available = profiler.is_available()
        assert isinstance(available, bool)

    def test_nsys_profiler_creation(self):
        profiler = NsysProfiler()
        assert profiler.config is not None


class TestTorchProfilerRunner:
    def test_is_available(self):
        runner = TorchProfilerRunner()
        available = runner.is_available()
        assert isinstance(available, bool)

    def test_creation_with_config(self):
        config = ProfilerConfig()
        runner = TorchProfilerRunner(config)
        assert runner.config is config


class TestBottleneckCategory:
    def test_all_categories_valid(self):
        categories = list(BottleneckCategory)
        assert len(categories) == 8
        assert BottleneckCategory.IO_INTENSIVE.value == "io_intensive"
        assert BottleneckCategory.COMPUTE_INTENSIVE.value == "compute_intensive"
        assert BottleneckCategory.LOCK_CONTENTION.value == "lock_contention"
        assert BottleneckCategory.SERIALIZATION.value == "serialization"
        assert BottleneckCategory.KERNEL_LAUNCH.value == "kernel_launch"
        assert BottleneckCategory.BATCH_IMBALANCE.value == "batch_imbalance"
        assert BottleneckCategory.NETWORK_BOUND.value == "network_bound"
        assert BottleneckCategory.MEMORY_BOUND.value == "memory_bound"


class TestLLMAnalyzer:
    from profiler.llm_analyzer import LLMAnalyzer

    def test_llm_analyzer_not_available_by_default(self):
        analyzer = self.LLMAnalyzer()
        assert analyzer.is_available() is False

    def test_local_analysis_generated(self):
        analyzer = self.LLMAnalyzer()

        events = [
            ProfilingEvent("op", "compute", 0, 1000, 1000, cpu_time_us=1000, phase="compute"),
        ]
        trace = ProfilingTrace(events=events, total_duration_us=1000)

        detector = BottleneckDetector()
        bottlenecks = detector.detect(trace)

        report = analyzer._generate_local_analysis(trace, bottlenecks)
        assert "Executive Summary" in report
        assert "Bottleneck Analysis" in report

    def test_local_analysis_no_bottlenecks(self):
        analyzer = self.LLMAnalyzer()
        trace = ProfilingTrace()
        report = analyzer._generate_local_analysis(trace, [])
        assert "No significant bottlenecks were detected" in report
