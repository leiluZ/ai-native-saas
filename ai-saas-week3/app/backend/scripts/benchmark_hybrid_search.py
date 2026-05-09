#!/usr/bin/env python3
"""
混合检索管道性能压测脚本

目标：
- QPS = 50
- 输出 P99 延迟
- 输出缓存命中率

用法：
    python benchmark_hybrid_search.py --qps 50 --duration 60 --queries-file queries.txt
"""

import argparse
import asyncio
import time
import random
import statistics
from typing import List, Dict, Any
from dataclasses import dataclass
import aiohttp


@dataclass
class BenchmarkMetrics:
    total_requests: int = 0
    success_count: int = 0
    error_count: int = 0
    cache_hits: int = 0
    latencies: List[float] = None

    def __post_init__(self):
        if self.latencies is None:
            self.latencies = []

    @property
    def qps(self) -> float:
        if not self.latencies:
            return 0.0
        duration = sum(self.latencies)
        return self.total_requests / duration if duration > 0 else 0.0

    @property
    def p50(self) -> float:
        return self._percentile(50)

    @property
    def p99(self) -> float:
        return self._percentile(99)

    @property
    def cache_hit_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.cache_hits / self.total_requests

    def _percentile(self, p: float) -> float:
        if not self.latencies:
            return 0.0
        sorted_lat = sorted(self.latencies)
        k = (len(sorted_lat) - 1) * (p / 100.0)
        f = int(k)
        c = f + 1 if f + 1 < len(sorted_lat) else f
        if f == c:
            return sorted_lat[f]
        return sorted_lat[f] * (c - k) + sorted_lat[c] * (k - f)

    def report(self) -> Dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "qps": round(self.qps, 2),
            "p50_ms": round(self.p50 * 1000, 2),
            "p99_ms": round(self.p99 * 1000, 2),
            "cache_hit_rate": round(self.cache_hit_rate * 100, 2),
            "avg_latency_ms": round(statistics.mean(self.latencies) * 1000, 2) if self.latencies else 0,
            "min_latency_ms": round(min(self.latencies) * 1000, 2) if self.latencies else 0,
            "max_latency_ms": round(max(self.latencies) * 1000, 2) if self.latencies else 0,
        }


async def worker(
    session: aiohttp.ClientSession,
    base_url: str,
    queries: List[str],
    metrics: BenchmarkMetrics,
    qps: float,
    duration: float,
    warmup: bool = False,
):
    """
    压测工作协程，按目标 QPS 发送请求
    """
    interval = 1.0 / qps if qps > 0 else 0.02
    end_time = time.monotonic() + duration

    while time.monotonic() < end_time:
        query = random.choice(queries)
        url = f"{base_url}/api/v1/rag/search?q={query}&top_k=10"

        start = time.monotonic()
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                latency = time.monotonic() - start
                if not warmup:
                    metrics.latencies.append(latency)
                    metrics.total_requests += 1
                    if resp.status == 200:
                        metrics.success_count += 1
                        data = await resp.json()
                        # 若返回结构包含 cached 字段可统计缓存命中
                        # 这里通过响应头或 body 判断，示例假设 header X-Cache: HIT
                        if resp.headers.get("X-Cache") == "HIT":
                            metrics.cache_hits += 1
                    else:
                        metrics.error_count += 1
        except Exception as e:
            latency = time.monotonic() - start
            if not warmup:
                metrics.latencies.append(latency)
                metrics.total_requests += 1
                metrics.error_count += 1

        # 控制请求间隔以稳定 QPS
        sleep_time = interval - (time.monotonic() - start)
        if sleep_time > 0:
            await asyncio.sleep(sleep_time)


async def run_benchmark(
    base_url: str,
    queries: List[str],
    qps: int,
    duration: int,
    concurrency: int,
    warmup_duration: int = 5,
) -> BenchmarkMetrics:
    """
    运行压测
    """
    metrics = BenchmarkMetrics()
    connector = aiohttp.TCPConnector(limit=concurrency * 2)
    async with aiohttp.ClientSession(connector=connector) as session:
        # 1. Warmup
        print(f"[Benchmark] Warmup for {warmup_duration}s at {qps} QPS...")
        warmup_tasks = [
            worker(session, base_url, queries, metrics, qps, warmup_duration, warmup=True)
            for _ in range(concurrency)
        ]
        await asyncio.gather(*warmup_tasks)

        # 重置指标
        metrics = BenchmarkMetrics()

        # 2. 正式压测
        print(f"[Benchmark] Running benchmark: QPS={qps}, duration={duration}s, concurrency={concurrency}")
        tasks = [
            worker(session, base_url, queries, metrics, qps, duration, warmup=False)
            for _ in range(concurrency)
        ]
        await asyncio.gather(*tasks)

    return metrics


def load_queries(filepath: str) -> List[str]:
    """加载查询文件"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        # 默认查询
        return [
            "什么是人工智能",
            "机器学习基础",
            "深度学习框架对比",
            "自然语言处理应用",
            "向量数据库选型",
            "RAG 系统架构",
            "大模型微调方法",
            "Prompt Engineering",
            "Agent 系统设计",
            "多模态模型介绍",
        ]


def main():
    parser = argparse.ArgumentParser(description="Hybrid Search Benchmark")
    parser.add_argument("--url", default="http://localhost:8000", help="服务地址")
    parser.add_argument("--qps", type=int, default=50, help="目标 QPS")
    parser.add_argument("--duration", type=int, default=60, help="压测时长（秒）")
    parser.add_argument("--concurrency", type=int, default=10, help="并发协程数")
    parser.add_argument("--queries-file", default="", help="查询文本文件路径")
    parser.add_argument("--warmup", type=int, default=5, help="预热时长（秒）")
    args = parser.parse_args()

    queries = load_queries(args.queries_file) if args.queries_file else load_queries("")
    print(f"[Benchmark] Loaded {len(queries)} queries")

    metrics = asyncio.run(
        run_benchmark(
            base_url=args.url,
            queries=queries,
            qps=args.qps,
            duration=args.duration,
            concurrency=args.concurrency,
            warmup_duration=args.warmup,
        )
    )

    report = metrics.report()
    print("\n========== Benchmark Report ==========")
    for key, value in report.items():
        print(f"  {key}: {value}")
    print("======================================\n")


if __name__ == "__main__":
    main()
