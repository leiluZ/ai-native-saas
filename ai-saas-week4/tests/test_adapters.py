import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from benchmark.adapters import (
    InferenceResult,
    BaseAdapter,
    VLLMAdapter,
    OllamaAdapter,
    get_adapter
)


class TestInferenceResult:
    def test_create_success_result(self):
        result = InferenceResult(
            request_id="req_1",
            prompt_tokens=50,
            completion_tokens=100,
            ttft=0.5,
            tpot=0.02,
            e2e_latency=2.5,
            total_tokens=150,
            throughput=60.0,
            success=True
        )
        assert result.request_id == "req_1"
        assert result.success is True
        assert result.error is None
        assert result.ttft == 0.5
        assert result.tpot == 0.02
        assert result.e2e_latency == 2.5

    def test_create_failed_result(self):
        result = InferenceResult(
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
        assert result.success is False
        assert result.error == "Connection timeout"

    def test_default_values(self):
        result = InferenceResult(
            request_id="req_default",
            prompt_tokens=0,
            completion_tokens=0,
            ttft=0,
            tpot=0,
            e2e_latency=0,
            total_tokens=0,
            throughput=0,
            success=True
        )
        assert result.prompt_length == 0
        assert result.completion_length == 0
        assert result.timestamp == 0.0


class TestGetAdapter:
    def test_get_vllm_adapter(self):
        adapter = get_adapter("vllm", base_url="http://localhost:8000")
        assert isinstance(adapter, VLLMAdapter)
        assert adapter.base_url == "http://localhost:8000"

    def test_get_ollama_adapter(self):
        adapter = get_adapter("ollama", base_url="http://localhost:11434")
        assert isinstance(adapter, OllamaAdapter)
        assert adapter.base_url == "http://localhost:11434"

    def test_get_adapter_case_insensitive(self):
        adapter = get_adapter("VLLM", base_url="http://localhost:8000")
        assert isinstance(adapter, VLLMAdapter)

        adapter = get_adapter("Ollama", base_url="http://localhost:11434")
        assert isinstance(adapter, OllamaAdapter)

    def test_get_unknown_adapter(self):
        with pytest.raises(ValueError, match="Unknown engine"):
            get_adapter("unknown", base_url="http://localhost:8000")


class TestVLLMAdapter:
    def test_init_defaults(self):
        adapter = VLLMAdapter(base_url="http://localhost:8000")
        assert adapter.base_url == "http://localhost:8000"
        assert adapter.max_retries == 3
        assert adapter.retry_delay == 1.0

    def test_init_custom(self):
        adapter = VLLMAdapter(
            base_url="http://localhost:8000",
            timeout=120,
            max_retries=5,
            retry_delay=2.0
        )
        assert adapter.max_retries == 5
        assert adapter.retry_delay == 2.0

    def test_url_trailing_slash_removed(self):
        adapter = VLLMAdapter(base_url="http://localhost:8000/")
        assert adapter.base_url == "http://localhost:8000"


class TestOllamaAdapter:
    def test_init_defaults(self):
        adapter = OllamaAdapter(base_url="http://localhost:11434")
        assert adapter.base_url == "http://localhost:11434"
        assert adapter.max_retries == 3

    def test_init_custom(self):
        adapter = OllamaAdapter(
            base_url="http://localhost:11434",
            timeout=60,
            max_retries=2,
            retry_delay=0.5
        )
        assert adapter.max_retries == 2
        assert adapter.retry_delay == 0.5
