import pytest
import sys
import os
import json
import tempfile
import yaml

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


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def temp_model_dir(temp_dir):
    model_dir = os.path.join(temp_dir, "mock_model")
    os.makedirs(model_dir, exist_ok=True)

    config = {
        "architectures": ["LlamaForCausalLM"],
        "model_type": "llama",
        "hidden_size": 4096,
        "num_hidden_layers": 32,
        "num_attention_heads": 32,
        "vocab_size": 32000
    }
    with open(os.path.join(model_dir, "config.json"), "w") as f:
        json.dump(config, f)

    tokenizer_config = {"model_type": "llama"}
    with open(os.path.join(model_dir, "tokenizer_config.json"), "w") as f:
        json.dump(tokenizer_config, f)

    return model_dir


@pytest.fixture
def temp_config_file(temp_dir):
    config_path = os.path.join(temp_dir, "test_config.yaml")
    config = {
        "engine": "vllm",
        "base_url": "http://localhost:8000",
        "vllm_url": "http://localhost:8000",
        "ollama_url": "http://localhost:11434",
        "prompt_length": "short",
        "total_requests": 10,
        "concurrency": 2,
        "max_tokens": 128,
        "timeout": 60,
        "max_retries": 1,
        "output": os.path.join(temp_dir, "results")
    }
    with open(config_path, "w") as f:
        yaml.dump(config, f)
    return config_path
