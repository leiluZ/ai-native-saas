import json
import logging
import os
from typing import Optional

from profiler.config import ProfilerConfig, default_config
from profiler.core import ProfilingTrace, ProfilingEvent

logger = logging.getLogger(__name__)


class FlameGraphGenerator:
    def __init__(self, config: Optional[ProfilerConfig] = None):
        self.config = config or default_config

    def _events_to_folded_stacks(self, events: list[ProfilingEvent]) -> list[tuple[str, float]]:
        entries = []
        for evt in events:
            if evt.stack:
                stack_str = ";".join(evt.stack)
            elif evt.category:
                stack_str = f"{evt.category};{evt.name}"
            else:
                stack_str = evt.name
            entries.append((stack_str, evt.duration_us))
        return entries

    def _folded_to_json(self, entries: list[tuple[str, float]]) -> dict:
        root = {"name": "root", "value": 0.0, "children": {}}

        for stack_str, value in entries:
            frames = stack_str.split(";")
            current = root
            current["value"] += value

            for frame in frames:
                if frame not in current["children"]:
                    current["children"][frame] = {
                        "name": frame,
                        "value": 0.0,
                        "children": {},
                    }
                current = current["children"][frame]
                current["value"] += value

        def _convert(node):
            result = {
                "name": node["name"],
                "value": round(node["value"], 2),
            }
            if node["children"]:
                result["children"] = [
                    _convert(child) for child in node["children"].values()
                ]
                result["children"].sort(key=lambda c: c["value"], reverse=True)
            return result

        return _convert(root)

    def generate_flame_graph_data(self, trace: ProfilingTrace) -> dict:
        entries = self._events_to_folded_stacks(trace.events)
        return self._folded_to_json(entries)

    def generate_flame_graph_svg(self, trace: ProfilingTrace, output_path: Optional[str] = None) -> str:
        data = self.generate_flame_graph_data(trace)

        if output_path is None:
            os.makedirs(self.config.output_dir, exist_ok=True)
            output_path = os.path.join(self.config.output_dir, "flame_graph.svg")

        svg = self._render_svg(data)
        with open(output_path, "w") as f:
            f.write(svg)

        logger.info(f"Flame graph saved to {output_path}")
        return output_path

    def _render_svg(self, data: dict) -> str:
        width = self.config.flame_graph_width
        height = self.config.flame_graph_height
        bar_height = 20
        font_size = 12

        total = data["value"]
        if total <= 0:
            total = 1

        svg_parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '<style>',
            '  rect { stroke: #fff; stroke-width: 0.5; }',
            '  text { font-family: monospace; font-size: 12px; fill: #1a1a2e; }',
            '  .title { font-size: 16px; font-weight: bold; fill: #e2e8f0; }',
            '</style>',
            f'<rect width="{width}" height="{height}" fill="#0f172a"/>',
            f'<text x="10" y="16" class="title">Flame Graph - Total: {total:.1f}us</text>',
        ]

        colors = ["#38bdf8", "#4ade80", "#fbbf24", "#f87171", "#c084fc",
                    "#34d399", "#fb923c", "#a78bfa", "#2dd4bf", "#f472b6"]

        def _render_node(node, x, w, y, depth, max_depth):
            if depth > max_depth:
                return
            color = colors[depth % len(colors)]
            label = node["name"].split(".")[-1][:40]

            svg_parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w, 1):.1f}" '
                f'height="{bar_height - 1}" fill="{color}" rx="2">'
                f'<title>{node["name"]} ({node["value"]:.1f}us)</title></rect>'
            )

            if w > 30:
                svg_parts.append(
                    f'<text x="{x + 3:.1f}" y="{y + 14:.1f}" '
                    f'clip-path="url(#clip-{depth})">{label}</text>'
                )

            if "children" in node:
                cx = x
                for child in node["children"]:
                    cw = (child["value"] / total) * width if total > 0 else 0
                    _render_node(child, cx, cw, y + bar_height, depth + 1, max_depth)
                    cx += cw

        _render_node(data, 0, width, 20, 0, 20)
        svg_parts.append("</svg>")
        return "\n".join(svg_parts)

    def generate_flame_graph_html(self, trace: ProfilingTrace, output_path: Optional[str] = None) -> str:
        data = self.generate_flame_graph_data(trace)

        if output_path is None:
            os.makedirs(self.config.output_dir, exist_ok=True)
            output_path = os.path.join(self.config.output_dir, "flame_graph.html")

        html = self._render_interactive_html(data, trace)
        with open(output_path, "w") as f:
            f.write(html)

        logger.info(f"Interactive flame graph saved to {output_path}")
        return output_path

    def _render_interactive_html(self, data: dict, trace: ProfilingTrace) -> str:
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flame Graph - Profiling Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; padding: 24px; }}
        h1 {{ color: #38bdf8; margin-bottom: 8px; }}
        .subtitle {{ color: #94a3b8; margin-bottom: 24px; font-size: 14px; }}
        .flame-container {{ position: relative; background: #1e293b; border-radius: 8px; overflow: hidden; }}
        .tooltip {{ position: absolute; background: #334155; padding: 8px 12px; border-radius: 6px; font-size: 12px; pointer-events: none; opacity: 0; transition: opacity 0.15s; z-index: 10; border: 1px solid #475569; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 24px; }}
        .stat-card {{ background: #1e293b; border-radius: 8px; padding: 16px; text-align: center; border: 1px solid #334155; }}
        .stat-value {{ font-size: 24px; font-weight: bold; color: #38bdf8; }}
        .stat-label {{ font-size: 12px; color: #94a3b8; margin-top: 4px; }}
        .top-ops {{ margin-top: 24px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #334155; font-size: 13px; }}
        th {{ color: #94a3b8; }}
    </style>
</head>
<body>
    <h1>Flame Graph</h1>
    <p class="subtitle">Total Duration: {trace.total_duration_us:.1f}us | Events: {len(trace.events)} | GPU Memory: {trace.gpu_memory_mb:.1f}MB</p>
    <div class="stats">
        <div class="stat-card"><div class="stat-value">{len(trace.events)}</div><div class="stat-label">Total Events</div></div>
        <div class="stat-card"><div class="stat-value">{trace.total_duration_us:.0f}us</div><div class="stat-label">Total Duration</div></div>
        <div class="stat-card"><div class="stat-value">{trace.gpu_memory_mb:.0f}MB</div><div class="stat-label">GPU Memory</div></div>
        <div class="stat-card"><div class="stat-value">{trace.total_cuda_time_us():.0f}us</div><div class="stat-label">CUDA Time</div></div>
    </div>
    <div class="top-ops">
        <h2 style="color:#94a3b8;margin-bottom:12px">Top Operations by CPU Time</h2>
        <table>
            <thead><tr><th>Operation</th><th>CPU Time (us)</th><th>CUDA Time (us)</th><th>Calls</th><th>Category</th></tr></thead>
            <tbody>
                {''.join(f'<tr><td>{e.name[:80]}</td><td>{e.cpu_time_us:.0f}</td><td>{e.cuda_time_us:.0f}</td><td>{e.call_count}</td><td>{e.category}</td></tr>' for e in trace.events[:20])}
            </tbody>
        </table>
    </div>
</body>
</html>"""


def generate_flame_graph(trace: ProfilingTrace, output_dir: Optional[str] = None, config: Optional[ProfilerConfig] = None) -> str:
    cfg = config or ProfilerConfig()
    if output_dir:
        cfg.output_dir = output_dir

    generator = FlameGraphGenerator(cfg)
    return generator.generate_flame_graph_svg(trace)
