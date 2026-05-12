import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from benchmark.adapters import InferenceResult


@pytest.fixture
def success_result():
    return InferenceResult(
        request_id="req_0",
        prompt_tokens=50,
        completion_tokens=100,
        ttft=0.5,
        tpot=0.02,
        e2e_latency=2.5,
        total_tokens=150,
        throughput=60.0,
        success=True,
        prompt_length=200,
        completion_length=100,
        timestamp=1000.0
    )


@pytest.fixture
def failed_result():
    return InferenceResult(
        request_id="req_fail",
        prompt_tokens=0,
        completion_tokens=0,
        ttft=0,
        tpot=0,
        e2e_latency=0.1,
        total_tokens=0,
        throughput=0,
        success=False,
        error="Connection timeout"
    )


@pytest.fixture
def mixed_results():
    results = []
    for i in range(10):
        results.append(InferenceResult(
            request_id=f"req_{i}",
            prompt_tokens=50,
            completion_tokens=100 + i * 10,
            ttft=0.3 + i * 0.05,
            tpot=0.01 + i * 0.002,
            e2e_latency=1.0 + i * 0.3,
            total_tokens=150 + i * 10,
            throughput=50.0 + i * 5,
            success=True,
            prompt_length=200 + i * 50,
            completion_length=100 + i * 10,
            timestamp=1000.0 + i * 10
        ))
    results.append(InferenceResult(
        request_id="req_fail_1",
        prompt_tokens=0,
        completion_tokens=0,
        ttft=0,
        tpot=0,
        e2e_latency=0.05,
        total_tokens=0,
        throughput=0,
        success=False,
        error="HTTP 500"
    ))
    results.append(InferenceResult(
        request_id="req_fail_2",
        prompt_tokens=0,
        completion_tokens=0,
        ttft=0,
        tpot=0,
        e2e_latency=0.03,
        total_tokens=0,
        throughput=0,
        success=False,
        error="Timeout"
    ))
    return results


@pytest.fixture
def short_prompt_results():
    results = []
    for i in range(5):
        results.append(InferenceResult(
            request_id=f"short_{i}",
            prompt_tokens=20,
            completion_tokens=50,
            ttft=0.2,
            tpot=0.01,
            e2e_latency=0.7,
            total_tokens=70,
            throughput=100.0,
            success=True,
            prompt_length=80,
            completion_length=50,
            timestamp=1000.0 + i
        ))
    return results


@pytest.fixture
def medium_prompt_results():
    results = []
    for i in range(5):
        results.append(InferenceResult(
            request_id=f"medium_{i}",
            prompt_tokens=80,
            completion_tokens=100,
            ttft=0.5,
            tpot=0.02,
            e2e_latency=2.5,
            total_tokens=180,
            throughput=72.0,
            success=True,
            prompt_length=320,
            completion_length=100,
            timestamp=2000.0 + i
        ))
    return results


@pytest.fixture
def long_prompt_results():
    results = []
    for i in range(5):
        results.append(InferenceResult(
            request_id=f"long_{i}",
            prompt_tokens=300,
            completion_tokens=200,
            ttft=1.0,
            tpot=0.03,
            e2e_latency=7.0,
            total_tokens=500,
            throughput=71.4,
            success=True,
            prompt_length=1200,
            completion_length=200,
            timestamp=3000.0 + i
        ))
    return results
