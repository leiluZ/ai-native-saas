# Profiling Report

Generated: 2026-05-18T17:48:21.608889

## Summary

| Metric | Value |
|--------|-------|
| Total Duration | 150.15 ms |
| Total Events | 0 |
| Unique Operations | 0 |
| CPU Time | 0.0 us |
| CUDA Time | 0.0 us |
| GPU Memory | 0 MB |

## Phase Distribution

| Phase | Time (us) | % | Calls |
|-------|-----------|------|-------|

## Detected Bottlenecks

### #1 Insufficient Profiling Data
- **Category**: compute_intensive
- **Phase**: compute
- **Severity**: 30%
- **Impact**: 0.0us (0.0%)
- **Detail**: Not enough data collected for bottleneck analysis. Consider increasing profiling duration or enabling more detailed tracing.
- **Code Location**: `benchmark/metrics.py:compute_metrics() aggregation`
- **Suggestion**: Profile specific compute kernels with Nsight Compute. Consider quantized inference (AWQ/INT8) to reduce compute requirements.
- **Expected Improvement**: 5-15% reduction through quantization


## Natural Language Analysis

# Performance Optimization Analysis

## Executive Summary

The profiling session captured 0 unique operations over 150.15ms of execution time.

## Bottleneck Analysis

### 1. [MEDIUM] Insufficient Profiling Data

**Category**: compute_intensive
**Phase**: compute
**Impact**: 0.0us (0.0% of total)

**Detail**: Not enough data collected for bottleneck analysis. Consider increasing profiling duration or enabling more detailed tracing.

**Optimization Strategy**:
Profile specific compute kernels with Nsight Compute. Consider quantized inference (AWQ/INT8) to reduce compute requirements.

**Affected Code**: `benchmark/metrics.py:compute_metrics() aggregation`
**Expected Improvement**: 5-15% reduction through quantization
**Verification**: `python -m profiler.main --target compute_intensive --before-profile Insufficient Profiling Data --verify-improvement --threshold 5.0`

---

## Priority-Ordered Action Plan

1. **Insufficient Profiling Data** - 5-15% reduction through quantization
   - Modify: `benchmark/metrics.py:compute_metrics() aggregation`
   - Action: Profile specific compute kernels with Nsight Compute. Consider quantized inference (AWQ/INT8) to reduce compute requirem...

## Next Steps

1. Profile after each optimization to measure actual improvement
2. Use the `--compare` flag to generate before/after comparison reports
3. Monitor Prometheus metrics for latency/throughput trends in production
4. Re-run profiling weekly to catch regressions early
