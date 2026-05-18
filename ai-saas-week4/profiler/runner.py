import logging
import os
import shutil
import time
from datetime import datetime
from typing import Optional

from profiler.config import ProfilerConfig, default_config
from profiler.core import ProfilingTrace, ProfileManager
from profiler.flame_graph import FlameGraphGenerator
from profiler.phase_analyzer import PhaseAnalyzer
from profiler.bottleneck import BottleneckDetector
from profiler.report import ProfilingReportGenerator
from profiler.comparator import ProfileComparator
from profiler.llm_analyzer import LLMAnalyzer

logger = logging.getLogger(__name__)


class ProfilingRunner:
    def __init__(self, config: Optional[ProfilerConfig] = None):
        self.config = config or default_config
        self.manager = ProfileManager(self.config)
        self._before_trace: Optional[ProfilingTrace] = None
        self._after_trace: Optional[ProfilingTrace] = None

    def archive_existing_results(self):
        if not self.config.auto_archive:
            return

        output_dir = self.config.output_dir
        if not os.path.exists(output_dir):
            return

        contents = os.listdir(output_dir)
        if not contents:
            return

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_dir = os.path.join(output_dir, f"archive_{ts}")
        os.makedirs(archive_dir, exist_ok=True)

        for item in contents:
            if item.startswith("archive_"):
                continue
            src = os.path.join(output_dir, item)
            dst = os.path.join(archive_dir, item)
            try:
                if os.path.isfile(src):
                    shutil.copy2(src, dst)
                elif os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
            except Exception as e:
                logger.warning(f"Failed to archive {item}: {e}")

        logger.info(f"Archived existing results to {archive_dir}")

    def run_before_profile(self, fn, *args, num_steps: int = 10, use_cuda: bool = False, **kwargs) -> ProfilingTrace:
        self.archive_existing_results()

        logger.info("Running BEFORE optimization profile...")
        if use_cuda:
            trace = self.manager.run_torch_profile(fn, *args, num_steps=num_steps, use_cuda=True, **kwargs)
        else:
            trace, _ = self.manager.run_cpu_profile(fn, *args, **kwargs)

        self._before_trace = trace
        self.manager.save_trace(trace, "before_optimization_trace.json")
        return trace

    def run_after_profile(self, fn, *args, num_steps: int = 10, use_cuda: bool = False, **kwargs) -> ProfilingTrace:
        logger.info("Running AFTER optimization profile...")
        if use_cuda:
            trace = self.manager.run_torch_profile(fn, *args, num_steps=num_steps, use_cuda=True, **kwargs)
        else:
            trace, _ = self.manager.run_cpu_profile(fn, *args, **kwargs)

        self._after_trace = trace
        self.manager.save_trace(trace, "after_optimization_trace.json")
        return trace

    def generate_before_reports(self):
        if self._before_trace is None:
            raise RuntimeError("No before-optimization trace available. Run run_before_profile() first.")

        generator = ProfilingReportGenerator(self.config)
        report = generator.generate_and_save_all(self._before_trace)
        return report

    def generate_after_reports(self):
        if self._after_trace is None:
            raise RuntimeError("No after-optimization trace available. Run run_after_profile() first.")

        generator = ProfilingReportGenerator(self.config)
        report = generator.generate_and_save_all(self._after_trace)
        return report

    def generate_comparison_report(self) -> dict:
        if self._before_trace is None:
            raise RuntimeError("No before-optimization trace available.")
        if self._after_trace is None:
            raise RuntimeError("No after-optimization trace available.")

        comparator = ProfileComparator(self.config)
        comparison = comparator.compare(self._before_trace, self._after_trace)
        comparator.save_comparison_report(comparison)
        comparator.save_markdown_comparison(comparison)
        return comparison

    def run_full_pipeline(
        self,
        fn_before,
        fn_after=None,
        fn_args=(),
        num_steps: int = 10,
        use_cuda: bool = False,
    ) -> dict:
        self.run_before_profile(fn_before, *fn_args, num_steps=num_steps, use_cuda=use_cuda)
        before_report = self.generate_before_reports()

        if fn_after:
            self.run_after_profile(fn_after, *fn_args, num_steps=num_steps, use_cuda=use_cuda)
        else:
            self.run_after_profile(fn_before, *fn_args, num_steps=num_steps, use_cuda=use_cuda)

        after_report = self.generate_after_reports()
        comparison = self.generate_comparison_report()

        return {
            "before_report": before_report,
            "after_report": after_report,
            "comparison": comparison,
        }

    def get_output_files(self) -> list[str]:
        output_dir = self.config.output_dir
        if not os.path.exists(output_dir):
            return []

        files = []
        for root, _, filenames in os.walk(output_dir):
            for fn in filenames:
                files.append(os.path.join(root, fn))
        return sorted(files)


class OneClickProfiler:
    def __init__(self, config: Optional[ProfilerConfig] = None):
        self.config = config or default_config
        self.runner = ProfilingRunner(self.config)

    def start_profile(self, target: str, duration: int = 60):
        os.makedirs(self.config.output_dir, exist_ok=True)

        pid_file = os.path.join(self.config.output_dir, "profiler.pid")
        with open(pid_file, "w") as f:
            f.write(str(os.getpid()))

        status_file = os.path.join(self.config.output_dir, "profiler_status.txt")
        with open(status_file, "w") as f:
            f.write(f"started:{datetime.now().isoformat()}\ntarget:{target}\nduration:{duration}\n")

        logger.info(f"Profiler started for target={target}, duration={duration}s")
        return status_file

    def stop_profile(self) -> str:
        status_file = os.path.join(self.config.output_dir, "profiler_status.txt")
        archive_dir = os.path.join(self.config.output_dir, f"stopped_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

        os.makedirs(archive_dir, exist_ok=True)

        for item in os.listdir(self.config.output_dir):
            if item.startswith("stopped_") or item.startswith("archive_"):
                continue
            src = os.path.join(self.config.output_dir, item)
            dst = os.path.join(archive_dir, item)
            try:
                if os.path.isfile(src):
                    shutil.move(src, dst)
            except Exception as e:
                logger.warning(f"Failed to archive {item}: {e}")

        with open(status_file, "w") as f:
            f.write(f"stopped:{datetime.now().isoformat()}")

        logger.info(f"Profiler stopped. Results archived to {archive_dir}")
        return archive_dir

    def status(self) -> str:
        status_file = os.path.join(self.config.output_dir, "profiler_status.txt")
        if not os.path.exists(status_file):
            return "idle"

        with open(status_file) as f:
            content = f.read()
            if content.startswith("started:"):
                return "running"
            elif content.startswith("stopped:"):
                return "stopped"
        return "unknown"


def one_click_start(target: str = "gateway", duration: int = 60, config: Optional[ProfilerConfig] = None):
    profiler = OneClickProfiler(config)
    return profiler.start_profile(target, duration)


def one_click_stop(config: Optional[ProfilerConfig] = None):
    profiler = OneClickProfiler(config)
    return profiler.stop_profile()


def one_click_status(config: Optional[ProfilerConfig] = None):
    profiler = OneClickProfiler(config)
    return profiler.status()
