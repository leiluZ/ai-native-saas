import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from benchmark.vllm_lifecycle import VLLMLifecycleManager, VLLMInstance
from benchmark.kv_cache_config import KVCacheConfig


class TestVLLMInstance:
    def test_base_url(self):
        instance = VLLMInstance(
            config=KVCacheConfig(),
            port=8000,
            host="127.0.0.1",
            model="test-model",
        )
        assert instance.base_url == "http://127.0.0.1:8000"
        assert instance.health_url == "http://127.0.0.1:8000/health"

    def test_default_values(self):
        instance = VLLMInstance(
            config=KVCacheConfig(),
            model="test-model",
        )
        assert instance.port == 8000
        assert instance.host == "127.0.0.1"
        assert instance.process is None
        assert instance.ready is False
        assert instance.errors == []


class TestVLLMLifecycleManager:
    @pytest.fixture
    def manager(self):
        return VLLMLifecycleManager(
            model="test-model",
            port=8000,
            host="127.0.0.1",
            health_check_timeout=5.0,
            health_check_interval=0.1,
            graceful_shutdown_timeout=5.0,
        )

    @pytest.fixture
    def config(self):
        return KVCacheConfig(
            gpu_memory_utilization=0.85,
            block_size=16,
            max_num_seqs=64,
        )

    def test_build_command(self, manager, config):
        cmd = manager.build_command(config)
        assert "python" in cmd[0]
        assert "-m" in cmd
        assert "vllm.entrypoints.openai.api_server" in cmd
        assert "--model" in cmd
        assert "test-model" in cmd
        assert "--host" in cmd
        assert "127.0.0.1" in cmd
        assert "--port" in cmd
        assert "8000" in cmd
        assert "--gpu-memory-utilization=0.85" in cmd
        assert "--block-size=16" in cmd
        assert "--max-num-seqs=64" in cmd

    def test_build_command_with_extra_args(self, manager, config):
        cmd = manager.build_command(config, extra_args=["--dtype", "float16"])
        assert "--dtype" in cmd
        assert "float16" in cmd

    def test_start_creates_instance(self, manager, config):
        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_popen.return_value = mock_process

            instance = manager.start(config)
            assert instance is not None
            assert instance.config == config
            assert instance.process is not None
            assert instance.pid == 12345
            assert manager._current_instance is instance

    def test_start_stops_previous(self, manager, config):
        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_popen.return_value = mock_process

            instance1 = manager.start(config)
            instance2 = manager.start(config)
            assert manager._current_instance is instance2

    def test_start_handles_exception(self, manager, config):
        with patch("subprocess.Popen", side_effect=OSError("Cannot start")):
            instance = manager.start(config)
            assert len(instance.errors) > 0
            assert "Cannot start" in instance.errors[0]

    @pytest.mark.asyncio
    async def test_wait_until_ready_success(self, manager, config):
        instance = VLLMInstance(
            config=config,
            port=8000,
            host="127.0.0.1",
            model="test-model",
        )
        instance.process = MagicMock()
        instance.process.poll.return_value = None

        mock_response = MagicMock()
        mock_response.status = 200

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_ctx)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("benchmark.vllm_lifecycle.aiohttp.ClientSession", return_value=mock_session):
            ready = await manager.wait_until_ready(instance)
            assert ready is True
            assert instance.ready is True

    @pytest.mark.asyncio
    async def test_wait_until_ready_process_exited(self, manager, config):
        instance = VLLMInstance(
            config=config,
            port=8000,
            host="127.0.0.1",
            model="test-model",
        )
        instance.process = MagicMock()
        instance.process.poll.return_value = 1
        instance.process.stderr = MagicMock()
        instance.process.stderr.read.return_value = "CUDA out of memory"

        ready = await manager.wait_until_ready(instance)
        assert ready is False
        assert len(instance.errors) > 0

    @pytest.mark.asyncio
    async def test_wait_until_ready_timeout(self, manager, config):
        manager.health_check_timeout = 0.5
        manager.health_check_interval = 0.1

        instance = VLLMInstance(
            config=config,
            port=8000,
            host="127.0.0.1",
            model="test-model",
        )
        instance.process = MagicMock()
        instance.process.poll.return_value = None

        mock_response = AsyncMock()
        mock_response.status = 503
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_response
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            ready = await manager.wait_until_ready(instance)
            assert ready is False

    def test_stop_terminates_process(self, manager, config):
        instance = VLLMInstance(
            config=config,
            port=8000,
            host="127.0.0.1",
            model="test-model",
        )
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        instance.process = mock_process
        instance.ready = True
        manager._current_instance = instance

        manager.stop()
        assert instance.ready is False
        assert manager._current_instance is None

    def test_stop_handles_timeout(self, manager, config):
        instance = VLLMInstance(
            config=config,
            port=8000,
            host="127.0.0.1",
            model="test-model",
        )
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_process.wait.side_effect = [Exception("timeout"), None]
        instance.process = mock_process
        manager._current_instance = instance

        manager.stop()
        assert instance.ready is False

    def test_is_running(self, manager, config):
        instance = VLLMInstance(
            config=config,
            port=8000,
            host="127.0.0.1",
            model="test-model",
        )
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        instance.process = mock_process

        assert manager.is_running(instance) is True

        mock_process.poll.return_value = 0
        assert manager.is_running(instance) is False

    def test_is_running_no_instance(self, manager):
        assert manager.is_running() is False

    @pytest.mark.asyncio
    async def test_hot_reload_config_success(self, manager, config):
        instance = VLLMInstance(
            config=KVCacheConfig(),
            port=8000,
            host="127.0.0.1",
            model="test-model",
        )
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        instance.process = mock_process
        manager._current_instance = instance

        mock_response = MagicMock()
        mock_response.status = 200

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_ctx)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("benchmark.vllm_lifecycle.aiohttp.ClientSession", return_value=mock_session):
            result = await manager.hot_reload_config(config)
            assert result is True
            assert instance.config == config

    @pytest.mark.asyncio
    async def test_hot_reload_config_not_running(self, manager, config):
        result = await manager.hot_reload_config(config)
        assert result is False

    @pytest.mark.asyncio
    async def test_hot_reload_config_failure(self, manager, config):
        instance = VLLMInstance(
            config=KVCacheConfig(),
            port=8000,
            host="127.0.0.1",
            model="test-model",
        )
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        instance.process = mock_process
        manager._current_instance = instance

        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post.return_value = mock_response
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await manager.hot_reload_config(config)
            assert result is False

    @pytest.mark.asyncio
    async def test_get_server_args(self, manager):
        instance = VLLMInstance(
            config=KVCacheConfig(),
            port=8000,
            host="127.0.0.1",
            model="test-model",
        )
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        instance.process = mock_process
        manager._current_instance = instance

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"block_size": 16})

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_ctx)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("benchmark.vllm_lifecycle.aiohttp.ClientSession", return_value=mock_session):
            args = await manager.get_server_args()
            assert args == {"block_size": 16}

    @pytest.mark.asyncio
    async def test_get_server_args_not_running(self, manager):
        args = await manager.get_server_args()
        assert args is None
