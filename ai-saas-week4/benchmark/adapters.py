from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import aiohttp
import time


@dataclass
class InferenceResult:
    request_id: str
    prompt_tokens: int
    completion_tokens: int
    ttft: float
    tpot: float
    e2e_latency: float
    total_tokens: int
    throughput: float
    success: bool
    error: Optional[str] = None
    prompt_length: int = 0
    completion_length: int = 0
    timestamp: float = 0.0


class BaseAdapter(ABC):
    def __init__(
        self,
        base_url: str,
        timeout: int = 300,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        self.base_url = base_url.rstrip('/')
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    @abstractmethod
    async def generate(self, prompt: str, request_id: str, max_tokens: int = 512) -> InferenceResult:
        pass

    @abstractmethod
    async def get_gpu_memory(self) -> Optional[float]:
        pass

    async def _retry_request(self, func, *args, **kwargs) -> Any:
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
        raise last_error


class VLLMAdapter(BaseAdapter):
    API_PATH = "/v1/chat/completions"

    async def generate(self, prompt: str, request_id: str, max_tokens: int = 512) -> InferenceResult:
        url = f"{self.base_url}{self.API_PATH}"
        headers = {"Content-Type": "application/json"}

        payload = {
            "model": "default",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "stream": True
        }

        start_time = time.perf_counter()
        first_token_time = None
        token_count = 0
        prompt_length = len(prompt)

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return InferenceResult(
                            request_id=request_id,
                            prompt_tokens=0,
                            completion_tokens=0,
                            ttft=0,
                            tpot=0,
                            e2e_latency=time.perf_counter() - start_time,
                            total_tokens=0,
                            throughput=0,
                            success=False,
                            error=f"HTTP {response.status}: {error_text}"
                        )

                    async for line in response.content:
                        line = line.decode('utf-8').strip()
                        if not line or line == "data: [DONE]":
                            continue

                        if line.startswith("data: "):
                            import json
                            try:
                                data = json.loads(line[6:])
                                if "choices" in data and len(data["choices"]) > 0:
                                    delta = data["choices"][0].get("delta", {})
                                    if delta.get("content"):
                                        if first_token_time is None:
                                            first_token_time = time.perf_counter()
                                            ttft = first_token_time - start_time
                                        token_count += 1
                            except json.JSONDecodeError:
                                continue

            e2e_latency = time.perf_counter() - start_time
            ttft = ttft if first_token_time else e2e_latency
            tpot = (e2e_latency - ttft) / token_count if token_count > 0 else 0
            throughput = token_count / e2e_latency if e2e_latency > 0 else 0

            return InferenceResult(
                request_id=request_id,
                prompt_tokens=0,
                completion_tokens=token_count,
                ttft=ttft,
                tpot=tpot,
                e2e_latency=e2e_latency,
                total_tokens=token_count,
                throughput=throughput,
                success=True,
                prompt_length=prompt_length,
                completion_length=token_count,
                timestamp=start_time
            )

        except Exception as e:
            return InferenceResult(
                request_id=request_id,
                prompt_tokens=0,
                completion_tokens=0,
                ttft=0,
                tpot=0,
                e2e_latency=time.perf_counter() - start_time,
                total_tokens=0,
                throughput=0,
                success=False,
                error=str(e)
            )

    async def get_gpu_memory(self) -> Optional[float]:
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(f"{self.base_url}/v1/model") as response:
                    if response.status == 200:
                        return None
        except:
            pass
        return None


class OllamaAdapter(BaseAdapter):
    API_PATH = "/api/generate"

    async def generate(self, prompt: str, request_id: str, max_tokens: int = 512) -> InferenceResult:
        url = f"{self.base_url}{self.API_PATH}"
        headers = {"Content-Type": "application/json"}

        payload = {
            "prompt": prompt,
            "stream": True,
            "options": {"num_predict": max_tokens}
        }

        start_time = time.perf_counter()
        first_token_time = None
        token_count = 0
        prompt_length = len(prompt)

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return InferenceResult(
                            request_id=request_id,
                            prompt_tokens=0,
                            completion_tokens=0,
                            ttft=0,
                            tpot=0,
                            e2e_latency=time.perf_counter() - start_time,
                            total_tokens=0,
                            throughput=0,
                            success=False,
                            error=f"HTTP {response.status}: {error_text}"
                        )

                    async for line in response.content:
                        line = line.decode('utf-8').strip()
                        if not line:
                            continue

                        import json
                        try:
                            data = json.loads(line)
                            if "response" in data:
                                if first_token_time is None:
                                    first_token_time = time.perf_counter()
                                    ttft = first_token_time - start_time
                                token_count += 1
                        except json.JSONDecodeError:
                            continue

            e2e_latency = time.perf_counter() - start_time
            ttft = ttft if first_token_time else e2e_latency
            tpot = (e2e_latency - ttft) / token_count if token_count > 0 else 0
            throughput = token_count / e2e_latency if e2e_latency > 0 else 0

            return InferenceResult(
                request_id=request_id,
                prompt_tokens=0,
                completion_tokens=token_count,
                ttft=ttft,
                tpot=tpot,
                e2e_latency=e2e_latency,
                total_tokens=token_count,
                throughput=throughput,
                success=True,
                prompt_length=prompt_length,
                completion_length=token_count,
                timestamp=start_time
            )

        except Exception as e:
            return InferenceResult(
                request_id=request_id,
                prompt_tokens=0,
                completion_tokens=0,
                ttft=0,
                tpot=0,
                e2e_latency=time.perf_counter() - start_time,
                total_tokens=0,
                throughput=0,
                success=False,
                error=str(e)
            )

    async def get_gpu_memory(self) -> Optional[float]:
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(f"{self.base_url}/api/ps") as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("memory_total")
        except:
            pass
        return None


def get_adapter(engine: str, **kwargs) -> BaseAdapter:
    adapters = {
        "vllm": VLLMAdapter,
        "ollama": OllamaAdapter
    }
    engine_lower = engine.lower()
    if engine_lower not in adapters:
        raise ValueError(f"Unknown engine: {engine}. Supported: {list(adapters.keys())}")
    return adapters[engine_lower](**kwargs)


import asyncio
