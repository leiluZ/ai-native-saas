# Profiling Report (DEMO DATA -- not measured on this machine)

> **NOTE**: This is hand-crafted demonstration data showing what the pipeline WOULD
> produce on a real GPU + vLLM deployment. Metrics here are illustrative, not
> actual measurements from this machine.
>
> To generate real data, run on a machine with NVIDIA GPU + CUDA:
> ```
> python -m profiler.main --target gateway --compare
> ```

Generated: 2026-05-18T12:00:00 (simulated)

## Summary

| Metric | Value |
|--------|-------|
| Total Duration | 1205.33 ms |
| Total Events | 2847 |
| Unique Operations | 312 |
| CPU Time | 856234.1 us |
| CUDA Time | 420156.3 us |
| GPU Memory | 24152 MB |

## Phase Distribution

| Phase | Time (us) | % | Calls |
|-------|-----------|------|-------|
| compute | 425012.1 | 49.6% | 1842 |
| network_io | 156234.5 | 18.2% | 342 |
| serialization | 98567.3 | 11.5% | 215 |
| decode | 87654.2 | 10.2% | 156 |
| prefetch | 45234.8 | 5.3% | 89 |
| kv_cache_alloc | 23891.3 | 2.8% | 124 |
| lock_contention | 15632.4 | 1.8% | 47 |
| kernel | 3345.1 | 0.4% | 28 |
| io_intensive | 1456.0 | 0.2% | 4 |

## Detected Bottlenecks

### #1 CPU Serialization/Deserialization Blocking
- **Category**: io_intensive
- **Phase**: serialization
- **Severity**: 85%
- **Impact**: 98567.3us (11.5%)
- **Detail**: JSON serialization/deserialization is blocking the request pipeline. Each request spends significant time in encode/decode operations before reaching the inference engine. In the chat completions endpoint, `await request.json()` accounts for 3.2ms per request on average, and the response JSON serialization adds another 2.1ms.
- **Code Location**: `gateway/routes/chat.py#L91` and `gateway/proxy.py:_build_headers()`
- **Suggestion**: Replace json.dumps/json.loads with orjson for 3-5x faster serialization. Use `orjson.loads(request_body)` instead of `json.loads(request_body)` for request parsing. Use streaming JSON parsing for large payloads. Consider moving serialization to a separate thread pool to avoid blocking the event loop.
- **Expected Improvement**: 20-35% latency reduction in request parsing (est. 4.8ms → 1.6ms per request)
- **Verification Command**: `python -m profiler.main --target gateway --before-profile serialization_slow_v0 --after-profile serialization_fast_v1`

### #2 Network I/O Contention in Streaming Response
- **Category**: network_bound
- **Phase**: network_io
- **Severity**: 72%
- **Impact**: 156234.5us (18.2%)
- **Detail**: Network I/O is a significant bottleneck, especially in streaming response paths. Multiple concurrent SSE connections create connection pool pressure. The `httpx.AsyncClient` default connection limits (100 connections) are exhausted under high concurrency, causing queuing delays of 12-45ms.
- **Code Location**: `gateway/proxy.py:_stream_request()` and `gateway/routes/chat.py:_stream_with_router()`
- **Suggestion**: Increase HTTP connection pool limits (set `limits=httpx.Limits(max_connections=200, max_keepalive_connections=50)`). Use connection keep-alive strategically by reusing AsyncClient instances across requests. Consider gRPC for internal service communication to reduce per-message overhead.
- **Expected Improvement**: 25-40% reduction in streaming overhead (est. 45ms → 28ms per stream segment)
- **Verification Command**: `python -m profiler.main --target gateway --compare --steps 20`

### #3 Batch Size Imbalance Causing Straggler Delays
- **Category**: batch_imbalance
- **Phase**: compute
- **Severity**: 65%
- **Impact**: 67890.2us (7.9%)
- **Detail**: Compute operations show high variance (CV=0.68). Some batches are significantly larger than average (max 512 tokens vs avg 178 tokens), causing straggler delays where the entire batch waits for the longest sequence to complete. This is most pronounced during the decode phase with variable-length outputs.
- **Code Location**: `benchmark/kv_cache_runner.py:run_benchmark_round()`
- **Suggestion**: Implement dynamic batching with `max_batch_size=256` and `max_num_batched_tokens=4096` constraints. Add batch padding to equalize sizes with padding mask optimization. Enable `enable_chunked_prefill=True` in vLLM config and set `max_num_batched_tokens=4096` to chunk long Prefill into manageable segments. Use continuous batching to smooth workload distribution.
- **Expected Improvement**: 15-25% improvement in overall throughput (est. 85 → 106 tokens/s)
- **Verification Command**: `python -m benchmark.kv_cache_tuner --model Qwen/Qwen2.5-7B-Instruct --gmu-values 0.85 0.90 --bs-values 16 32`

---

## Optimization Action Plan (Priority-Ordered)

### Priority 1: CPU Serialization Optimization
- **Action**: Replace `json` with `orjson` in gateway routes and proxy
- **Code Changes**:
  - `gateway/routes/chat.py#L91`: `body = orjson.loads(await request.body())` replace `await request.json()`
  - `gateway/proxy.py#L33-L39`: Use `orjson.dumps()` for header construction
  - Add `import orjson` to these files
- **Expected Impact**: 12% end-to-end latency reduction
- **Risk**: Low - orjson is a drop-in replacement for json

### Priority 2: Network Connection Pool Optimization
- **Action**: Increase httpx connection pool limits and reuse client instances
- **Code Changes**:
  - `gateway/proxy.py#L98`: Add `limits=httpx.Limits(max_connections=200)` to AsyncClient
  - Create a module-level client pool with proper lifecycle management
- **Expected Impact**: 18% streaming throughput improvement
- **Risk**: Medium - increased memory usage per connection

### Priority 3: Batch Size Optimization
- **Action**: Enable chunked prefill and tune max_num_batched_tokens
- **Code Changes**:
  - `benchmark/kv_cache_config.py`: Add `enable_chunked_prefill=True` default
  - `benchmark/kv_cache_runner.py`: Add batch padding logic
- **Expected Impact**: 8% throughput improvement
- **Risk**: Low - these are well-tested vLLM features

## Natural Language Analysis

### Executive Summary

The profiling session captured 2,847 unique operations over 1,205ms of execution time. Three significant bottlenecks were identified that collectively account for 37.6% of total execution time. Addressing all three would yield approximately 26-38% latency improvement and 30-45% throughput improvement.

### Bottleneck Analysis

**Bottleneck #1 (CPU Serialization):** The most impactful bottleneck is JSON serialization/deserialization blocking in the gateway request path. This is classified as an I/O-intensive bottleneck occurring in the serialization phase with 85% severity. The primary cause is repeated json.loads/json.dumps calls in the hot path of every chat completion request. Switching to orjson (which is 3-5x faster for these operations) would directly reduce per-request overhead from ~5.3ms to ~1.6ms.

**Bottleneck #2 (Network I/O):** Network I/O contention in the streaming response path is the second most significant bottleneck. The httpx AsyncClient default connection pool limits create queuing delays under high concurrency, particularly in SSE streaming scenarios. Increasing pool limits and reusing client instances is the most effective remediation.

**Bottleneck #3 (Batch Imbalance):** Variable-length sequences create batch size imbalance, where compute operations show a coefficient of variation of 0.68. This means some batches contain disproportionately large sequences, causing all parallel requests in the batch to wait for the slowest member. Enabling chunked prefill and constraining max batch sizes effectively addresses this.

### Next Steps
1. Profile after each optimization to measure actual improvement
2. Use the `--compare` flag to generate before/after comparison reports
3. Monitor Prometheus metrics for latency/throughput trends in production
4. Re-run profiling weekly to catch regressions early
