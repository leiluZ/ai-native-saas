import subprocess
import time
import signal
import os
import json
import asyncio
import aiohttp
from dataclasses import dataclass, field
from typing import Optional

from .kv_cache_config import KVCacheConfig


@dataclass
class VLLMInstance:
    config: KVCacheConfig
    process: Optional[subprocess.Popen] = None
    port: int = 8000
    model: str = ""
    host: str = "127.0.0.1"
    pid: Optional[int] = None
    started_at: float = 0.0
    ready: bool = False
    errors: list[str] = field(default_factory=list)

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def health_url(self) -> str:
        return f"{self.base_url}/health"


class VLLMLifecycleManager:
    def __init__(
        self,
        model: str,
        port: int = 8000,
        host: str = "127.0.0.1",
        health_check_timeout: float = 120.0,
        health_check_interval: float = 2.0,
        graceful_shutdown_timeout: float = 30.0,
    ):
        self.model = model
        self.port = port
        self.host = host
        self.health_check_timeout = health_check_timeout
        self.health_check_interval = health_check_interval
        self.graceful_shutdown_timeout = graceful_shutdown_timeout
        self._current_instance: Optional[VLLMInstance] = None

    def build_command(self, config: KVCacheConfig, extra_args: Optional[list[str]] = None) -> list[str]:
        cmd = [
            "python", "-m", "vllm.entrypoints.openai.api_server",
            "--model", self.model,
            "--host", self.host,
            "--port", str(self.port),
        ]
        cmd.extend(config.to_cli_args())
        if extra_args:
            cmd.extend(extra_args)
        return cmd

    def start(self, config: KVCacheConfig, extra_args: Optional[list[str]] = None) -> VLLMInstance:
        if self._current_instance is not None and self._current_instance.process is not None:
            self.stop()

        cmd = self.build_command(config, extra_args)
        instance = VLLMInstance(
            config=config,
            port=self.port,
            host=self.host,
            model=self.model,
            started_at=time.time(),
        )

        try:
            env = os.environ.copy()
            env["VLLM_LOGGING_LEVEL"] = "WARNING"

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None,
            )
            instance.process = process
            instance.pid = process.pid
            self._current_instance = instance
        except Exception as e:
            instance.errors.append(f"Failed to start vLLM: {e}")
            self._current_instance = instance

        return instance

    async def wait_until_ready(self, instance: Optional[VLLMInstance] = None) -> bool:
        if instance is None:
            instance = self._current_instance
        if instance is None:
            return False

        start = time.time()
        while time.time() - start < self.health_check_timeout:
            if instance.process is not None and instance.process.poll() is not None:
                stderr_output = ""
                if instance.process.stderr:
                    try:
                        stderr_output = instance.process.stderr.read()
                    except Exception:
                        pass
                instance.errors.append(f"vLLM process exited with code {instance.process.returncode}: {stderr_output[:500]}")
                return False

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        instance.health_url,
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as resp:
                        if resp.status == 200:
                            instance.ready = True
                            return True
            except Exception:
                pass

            await asyncio.sleep(self.health_check_interval)

        instance.errors.append(f"Health check timed out after {self.health_check_timeout}s")
        return False

    def stop(self, instance: Optional[VLLMInstance] = None):
        if instance is None:
            instance = self._current_instance
        if instance is None or instance.process is None:
            return

        try:
            if hasattr(os, 'killpg') and instance.pid:
                try:
                    os.killpg(os.getpgid(instance.pid), signal.SIGTERM)
                except (ProcessLookupError, OSError):
                    pass
            else:
                instance.process.terminate()

            try:
                instance.process.wait(timeout=self.graceful_shutdown_timeout)
            except subprocess.TimeoutExpired:
                if hasattr(os, 'killpg') and instance.pid:
                    try:
                        os.killpg(os.getpgid(instance.pid), signal.SIGKILL)
                    except (ProcessLookupError, OSError):
                        pass
                else:
                    instance.process.kill()
                instance.process.wait(timeout=5)
        except Exception:
            pass
        finally:
            instance.ready = False
            if self._current_instance is instance:
                self._current_instance = None

    def is_running(self, instance: Optional[VLLMInstance] = None) -> bool:
        if instance is None:
            instance = self._current_instance
        if instance is None or instance.process is None:
            return False
        return instance.process.poll() is None

    async def hot_reload_config(self, config: KVCacheConfig) -> bool:
        if self._current_instance is None or not self.is_running():
            return False

        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "gpu_memory_utilization": config.gpu_memory_utilization,
                    "block_size": config.block_size,
                    "max_num_seqs": config.max_num_seqs,
                    "enable_chunked_prefill": config.enable_chunked_prefill,
                }
                if config.max_num_batched_tokens is not None:
                    payload["max_num_batched_tokens"] = config.max_num_batched_tokens

                async with session.post(
                    f"{self._current_instance.base_url}/v1/reconfigure",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        self._current_instance.config = config
                        return True
                    return False
        except Exception:
            return False

    async def get_server_args(self) -> Optional[dict]:
        if self._current_instance is None or not self.is_running():
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._current_instance.base_url}/v1/server_args",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    return None
        except Exception:
            return None
