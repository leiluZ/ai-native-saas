"""模型注册表单元测试"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from gateway.registry import (
    ModelEntry,
    ModelRegistry,
    ModelStatus,
    model_registry,
)


class TestModelEntry:
    def test_create_entry(self):
        entry = ModelEntry(
            name="gpt-4",
            provider="openai",
            endpoint="https://api.openai.com",
            api_key="sk-test",
            priority=10,
        )
        assert entry.name == "gpt-4"
        assert entry.provider == "openai"
        assert entry.endpoint == "https://api.openai.com"
        assert entry.api_key == "sk-test"
        assert entry.priority == 10
        assert entry.status == ModelStatus.UNKNOWN

    def test_to_openai_model(self):
        entry = ModelEntry(
            name="test-model",
            provider="vllm",
            endpoint="http://localhost:8000",
            priority=1,
        )
        entry.last_checked = 1677652288.0
        result = entry.to_openai_model()
        assert result["id"] == "test-model"
        assert result["object"] == "model"
        assert result["owned_by"] == "vllm"
        assert result["created"] == 1677652288

    def test_default_values(self):
        entry = ModelEntry(
            name="minimal",
            provider="test",
            endpoint="http://localhost:8000",
        )
        assert entry.api_key is None
        assert entry.priority == 0
        assert entry.status == ModelStatus.UNKNOWN
        assert entry.consecutive_failures == 0
        assert entry.max_consecutive_failures == 3


class TestModelRegistry:
    def test_register_and_get(self, clean_registry, gateway_model_entry):
        clean_registry.register(gateway_model_entry)
        retrieved = clean_registry.get("test-model")
        assert retrieved is not None
        assert retrieved.name == "test-model"
        assert retrieved.provider == "vllm"

    def test_get_nonexistent(self, clean_registry):
        assert clean_registry.get("nonexistent") is None

    def test_unregister(self, clean_registry, gateway_model_entry):
        clean_registry.register(gateway_model_entry)
        assert clean_registry.get("test-model") is not None
        clean_registry.unregister("test-model")
        assert clean_registry.get("test-model") is None

    def test_list_models(self, populated_registry):
        models = populated_registry.list_models()
        assert len(models) == 3
        names = {m.name for m in models}
        assert names == {"test-model", "unhealthy-model", "degraded-model"}

    def test_list_healthy_models(self, populated_registry):
        healthy = populated_registry.list_healthy_models()
        assert len(healthy) == 2
        names = {m.name for m in healthy}
        assert names == {"test-model", "degraded-model"}

    def test_get_best_model_preferred(self, populated_registry):
        best = populated_registry.get_best_model("test-model")
        assert best is not None
        assert best.name == "test-model"

    def test_get_best_model_preferred_unhealthy(self, populated_registry):
        best = populated_registry.get_best_model("unhealthy-model")
        assert best is not None
        assert best.name == "test-model"

    def test_get_best_model_no_preference(self, populated_registry):
        best = populated_registry.get_best_model()
        assert best is not None
        assert best.name == "test-model"

    def test_get_best_model_empty_registry(self, clean_registry):
        assert clean_registry.get_best_model() is None

    def test_get_best_model_all_unhealthy(self, clean_registry):
        from gateway.registry import ModelEntry, ModelStatus

        entry = ModelEntry(
            name="only-model",
            provider="test",
            endpoint="http://localhost:8000",
            status=ModelStatus.UNHEALTHY,
        )
        clean_registry.register(entry)
        assert clean_registry.get_best_model() is None

    @pytest.mark.asyncio
    async def test_check_model_health_success(self, clean_registry, gateway_model_entry):
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_instance.get.return_value = mock_response

            result = await clean_registry.check_model_health(gateway_model_entry)
            assert result is True

    @pytest.mark.asyncio
    async def test_check_model_health_failure(self, clean_registry, gateway_model_entry):
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_instance.get.return_value = mock_response

            result = await clean_registry.check_model_health(gateway_model_entry)
            assert result is False

    @pytest.mark.asyncio
    async def test_check_model_health_exception(self, clean_registry, gateway_model_entry):
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.get.side_effect = Exception("Connection refused")

            result = await clean_registry.check_model_health(gateway_model_entry)
            assert result is False

    @pytest.mark.asyncio
    async def test_update_model_status_healthy(self, clean_registry, gateway_model_entry):
        gateway_model_entry.status = ModelStatus.DEGRADED
        gateway_model_entry.consecutive_failures = 2
        await clean_registry._update_model_status(gateway_model_entry, True)
        assert gateway_model_entry.status == ModelStatus.HEALTHY
        assert gateway_model_entry.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_update_model_status_degraded(self, clean_registry, gateway_model_entry):
        gateway_model_entry.status = ModelStatus.HEALTHY
        gateway_model_entry.consecutive_failures = 2
        await clean_registry._update_model_status(gateway_model_entry, False)
        assert gateway_model_entry.status == ModelStatus.DEGRADED
        assert gateway_model_entry.consecutive_failures == 3

    @pytest.mark.asyncio
    async def test_update_model_status_unhealthy(self, clean_registry, gateway_model_entry):
        gateway_model_entry.status = ModelStatus.DEGRADED
        gateway_model_entry.consecutive_failures = 2
        await clean_registry._update_model_status(gateway_model_entry, False)
        assert gateway_model_entry.status == ModelStatus.UNHEALTHY
        assert gateway_model_entry.consecutive_failures == 3

    @pytest.mark.asyncio
    async def test_run_health_checks(self, clean_registry, gateway_model_entry, gateway_model_entry_unhealthy):
        clean_registry.register(gateway_model_entry)
        clean_registry.register(gateway_model_entry_unhealthy)

        async def mock_check(entry):
            return entry.name == "test-model"

        with patch.object(clean_registry, "check_model_health", side_effect=mock_check):
            await clean_registry.run_health_checks()

        assert clean_registry.get("test-model").status == ModelStatus.HEALTHY
        assert clean_registry.get("unhealthy-model").status == ModelStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_start_stop_health_check_loop(self, clean_registry):
        await clean_registry.start_health_check_loop()
        assert clean_registry._health_check_task is not None
        await clean_registry.stop_health_check_loop()
        assert clean_registry._health_check_task is None


class TestGlobalModelRegistry:
    def test_global_registry_is_singleton(self):
        from gateway.registry import model_registry as mr1
        from gateway.registry import model_registry as mr2
        assert mr1 is mr2
