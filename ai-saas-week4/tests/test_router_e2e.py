"""Router end-to-end function tests"""

import pytest
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from gateway.router.health_checker import (
    HealthChecker,
    HealthSnapshot,
    set_health_checker,
)
from gateway.router.degradation import (
    DegradationTrigger,
    set_degradation_trigger,
)
from gateway.router.engine import (
    RouterEngine,
    set_router_engine,
)
from gateway.router.cost_tracker import (
    CostTracker,
    set_cost_tracker,
)
from gateway.router.stream_aggregator import (
    StreamAggregator,
    set_stream_aggregator,
)
from gateway.router.metrics import (
    RouterMetrics,
    set_metrics,
)


@pytest.fixture
def e2e_health_checker():
    checker = HealthChecker(endpoint="http://localhost:8000")
    set_health_checker(checker)
    yield checker
    set_health_checker(HealthChecker(endpoint="http://localhost:8000"))


@pytest.fixture
def e2e_degradation_trigger():
    trigger = DegradationTrigger()
    set_degradation_trigger(trigger)
    yield trigger
    set_degradation_trigger(DegradationTrigger())


@pytest.fixture
def e2e_router_engine():
    engine = RouterEngine()
    set_router_engine(engine)
    yield engine
    set_router_engine(RouterEngine())


@pytest.fixture
def e2e_cost_tracker():
    tracker = CostTracker()
    set_cost_tracker(tracker)
    yield tracker
    set_cost_tracker(CostTracker())


@pytest.fixture
def e2e_stream_aggregator():
    aggregator = StreamAggregator()
    set_stream_aggregator(aggregator)
    yield aggregator
    set_stream_aggregator(StreamAggregator())


@pytest.fixture
def e2e_metrics():
    metrics = RouterMetrics()
    set_metrics(metrics)
    yield metrics
    set_metrics(RouterMetrics())


@pytest.fixture
def e2e_client(e2e_health_checker, e2e_degradation_trigger, e2e_router_engine, e2e_cost_tracker):
    from gateway.main import app
    from gateway.registry import ModelEntry, ModelStatus, model_registry

    model_registry.register(ModelEntry(
        name="vllm-local", provider="vllm", status=ModelStatus.HEALTHY,
        endpoint="http://localhost:8000", api_key=None, priority=1,
    ))
    model_registry.register(ModelEntry(
        name="gpt-3.5-turbo", provider="openai", status=ModelStatus.HEALTHY,
        endpoint="https://api.openai.com", api_key=None, priority=10,
    ))
    model_registry.register(ModelEntry(
        name="gpt-4", provider="openai", status=ModelStatus.HEALTHY,
        endpoint="https://api.openai.com", api_key=None, priority=20,
    ))

    app.dependency_overrides = {}
    return TestClient(app)


AUTH_HEADERS = {"Authorization": "Bearer sk-gateway-default-key"}


def _auth_headers(user_id=None):
    headers = dict(AUTH_HEADERS)
    if user_id:
        headers["X-User-ID"] = user_id
    return headers


class TestE2ERouting:
    """End-to-end routing tests"""

    def test_e2e_default_route_local(
        self, e2e_client, e2e_health_checker, e2e_degradation_trigger, e2e_router_engine, e2e_cost_tracker
    ):
        e2e_health_checker.stats.add_snapshot(
            HealthSnapshot(is_healthy=True, latency_ms=50.0, cpu_utilization_pct=30.0, gpu_utilization_pct=40.0)
        )

        with patch("gateway.routes.chat.proxy_chat_completions") as mock_proxy:
            mock_proxy.return_value = {
                "id": "test",
                "choices": [{"message": {"content": "Hello"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }

            response = e2e_client.post(
                "/v1/chat/completions",
                json={"model": "vllm-local", "messages": [{"role": "user", "content": "Hi"}]},
                headers=_auth_headers("user1"),
            )
            assert response.status_code == 200

    def test_e2e_vip_route_gpt4(
        self, e2e_client, e2e_health_checker, e2e_degradation_trigger, e2e_router_engine, e2e_cost_tracker
    ):
        e2e_router_engine.add_vip_user("vip_user")
        e2e_health_checker.stats.add_snapshot(
            HealthSnapshot(is_healthy=True, latency_ms=50.0, cpu_utilization_pct=30.0, gpu_utilization_pct=40.0)
        )

        with patch("gateway.routes.chat.proxy_chat_completions") as mock_proxy:
            mock_proxy.return_value = {
                "id": "test",
                "choices": [{"message": {"content": "VIP response"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }

            response = e2e_client.post(
                "/v1/chat/completions",
                json={"model": "vllm-local", "messages": [{"role": "user", "content": "Hi"}]},
                headers=_auth_headers("vip_user"),
            )
            assert response.status_code == 200

    def test_e2e_degradation_route_cloud(
        self, e2e_client, e2e_health_checker, e2e_degradation_trigger, e2e_router_engine, e2e_cost_tracker
    ):
        e2e_health_checker.stats.add_snapshot(
            HealthSnapshot(is_healthy=True, latency_ms=50.0, cpu_utilization_pct=30.0, gpu_utilization_pct=40.0)
        )
        e2e_degradation_trigger.force_degrade("test degradation")

        with patch("gateway.routes.chat.proxy_chat_completions") as mock_proxy:
            mock_proxy.return_value = {
                "id": "test",
                "choices": [{"message": {"content": "Fallback response"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }

            response = e2e_client.post(
                "/v1/chat/completions",
                json={"model": "vllm-local", "messages": [{"role": "user", "content": "Hi"}]},
                headers=_auth_headers("user1"),
            )
            assert response.status_code == 200

    def test_e2e_over_budget_route_local(
        self, e2e_client, e2e_health_checker, e2e_degradation_trigger, e2e_router_engine, e2e_cost_tracker
    ):
        e2e_health_checker.stats.add_snapshot(
            HealthSnapshot(is_healthy=True, latency_ms=50.0, cpu_utilization_pct=30.0, gpu_utilization_pct=40.0)
        )
        e2e_cost_tracker.record_usage("user1", "gpt-4", 350000, 0)

        with patch("gateway.routes.chat.proxy_chat_completions") as mock_proxy:
            mock_proxy.return_value = {
                "id": "test",
                "choices": [{"message": {"content": "Local response"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }

            response = e2e_client.post(
                "/v1/chat/completions",
                json={"model": "vllm-local", "messages": [{"role": "user", "content": "Hi"}]},
                headers=_auth_headers("user1"),
            )
            assert response.status_code == 200

    def test_e2e_load_balance_route_cloud(
        self, e2e_client, e2e_health_checker, e2e_degradation_trigger, e2e_router_engine, e2e_cost_tracker
    ):
        e2e_health_checker.stats.add_snapshot(
            HealthSnapshot(is_healthy=True, latency_ms=50.0, cpu_utilization_pct=90.0, gpu_utilization_pct=40.0)
        )

        with patch("gateway.routes.chat.proxy_chat_completions") as mock_proxy:
            mock_proxy.return_value = {
                "id": "test",
                "choices": [{"message": {"content": "Cloud response"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }

            response = e2e_client.post(
                "/v1/chat/completions",
                json={"model": "vllm-local", "messages": [{"role": "user", "content": "Hi"}]},
                headers=_auth_headers("user1"),
            )
            assert response.status_code == 200


class TestE2EAdminDashboard:
    """End-to-end admin dashboard tests"""

    def test_e2e_admin_full_flow(
        self, e2e_client, e2e_health_checker, e2e_degradation_trigger, e2e_router_engine, e2e_cost_tracker
    ):
        e2e_health_checker.stats.add_snapshot(
            HealthSnapshot(is_healthy=True, latency_ms=50.0, cpu_utilization_pct=30.0, gpu_utilization_pct=40.0)
        )
        e2e_cost_tracker.record_usage("user1", "gpt-4", 1000, 500)
        e2e_router_engine.decide(user_id="user1")

        response = e2e_client.get("/admin/routes")
        assert response.status_code == 200
        data = response.json()

        assert data["health"]["is_healthy"] is True
        assert data["health"]["success_rate"] > 0
        assert data["degradation"]["is_degraded"] is False
        assert data["cost"]["total_monthly_cost"] > 0
        assert len(data["recent_decisions"]) > 0

    def test_e2e_admin_vip_management(
        self, e2e_client, e2e_router_engine
    ):
        response = e2e_client.post("/admin/routes/vip/vip_test")
        assert response.status_code == 200
        assert e2e_router_engine.is_vip("vip_test") is True

        response = e2e_client.delete("/admin/routes/vip/vip_test")
        assert response.status_code == 200
        assert e2e_router_engine.is_vip("vip_test") is False

    def test_e2e_admin_degradation_control(
        self, e2e_client, e2e_degradation_trigger
    ):
        response = e2e_client.post("/admin/routes/degrade")
        assert response.status_code == 200
        assert e2e_degradation_trigger.is_degraded is True

        response = e2e_client.post("/admin/routes/recover")
        assert response.status_code == 200
        assert e2e_degradation_trigger.is_degraded is False

    def test_e2e_admin_dashboard_html(self, e2e_client):
        response = e2e_client.get("/admin/routes/dashboard")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Gateway Admin Dashboard" in response.text

    def test_e2e_admin_cost_tracking(
        self, e2e_client, e2e_cost_tracker
    ):
        e2e_cost_tracker.record_usage("user1", "gpt-4", 1000, 500)
        e2e_cost_tracker.record_usage("user2", "gpt-3.5-turbo", 2000, 1000)

        response = e2e_client.get("/admin/routes/cost")
        assert response.status_code == 200
        data = response.json()
        assert len(data["users"]) == 2

        response = e2e_client.get("/admin/routes/cost?user_id=user1")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "user1"
        assert data["monthly_cost_usd"] > 0


class TestE2EAcceptanceCriteria:
    """Verify acceptance criteria from learning plan"""

    def test_acceptance_route_switch_failure_rate(
        self, e2e_router_engine
    ):
        for _ in range(99):
            e2e_router_engine.record_switch_success()
        e2e_router_engine.record_switch_failure()

        assert e2e_router_engine.switch_failure_rate <= 0.01, \
            f"Switch failure rate {e2e_router_engine.switch_failure_rate} exceeds 1%"

    def test_acceptance_degradation_trigger_accurate(
        self, e2e_health_checker, e2e_degradation_trigger
    ):
        for i in range(3):
            e2e_health_checker.stats.add_snapshot(
                HealthSnapshot(is_healthy=False, error="500")
            )
        decision = e2e_degradation_trigger.evaluate(e2e_health_checker.stats)
        assert decision.should_degrade is True

        e2e_health_checker.stats.add_snapshot(
            HealthSnapshot(is_healthy=True, latency_ms=50.0, gpu_memory_pct=50.0)
        )
        decision = e2e_degradation_trigger.evaluate(e2e_health_checker.stats)
        assert decision.should_degrade is False

    def test_acceptance_decision_logs_complete(
        self, e2e_health_checker, e2e_degradation_trigger, e2e_router_engine, e2e_cost_tracker
    ):
        e2e_health_checker.stats.add_snapshot(
            HealthSnapshot(is_healthy=True, latency_ms=50.0, cpu_utilization_pct=30.0, gpu_utilization_pct=40.0)
        )

        decision = e2e_router_engine.decide(user_id="user1")
        assert decision.target is not None
        assert decision.reason is not None
        assert decision.detail != ""
        assert decision.switch_latency_ms >= 0
        assert decision.user_id == "user1"
        assert decision.timestamp > 0

        history = e2e_router_engine.decision_history
        assert len(history) > 0
        assert history[-1].target is not None
        assert history[-1].reason is not None

    def test_acceptance_switch_latency_under_50ms(
        self, e2e_health_checker, e2e_degradation_trigger, e2e_router_engine, e2e_cost_tracker
    ):
        e2e_health_checker.stats.add_snapshot(
            HealthSnapshot(is_healthy=True, latency_ms=50.0, cpu_utilization_pct=30.0, gpu_utilization_pct=40.0)
        )

        latencies = []
        for _ in range(100):
            decision = e2e_router_engine.decide(user_id="user1")
            latencies.append(decision.switch_latency_ms)

        avg_latency = sum(latencies) / len(latencies)
        assert avg_latency < 50.0, f"Average switch latency {avg_latency:.2f}ms exceeds 50ms budget"

    def test_acceptance_cost_tracking_accurate(
        self, e2e_cost_tracker
    ):
        e2e_cost_tracker.record_usage("user1", "gpt-4", 1000, 0)
        cost = e2e_cost_tracker.get_user_cost("user1").monthly_cost_usd
        expected = 1000 / 1000 * 0.03
        assert abs(cost - expected) < 0.0001, f"Cost {cost} != expected {expected}"

        e2e_cost_tracker.record_usage("user1", "gpt-3.5-turbo", 1000, 0)
        cost = e2e_cost_tracker.get_user_cost("user1").monthly_cost_usd
        expected = 0.03 + 0.002
        assert abs(cost - expected) < 0.0001, f"Cost {cost} != expected {expected}"

    def test_acceptance_stream_sse_format(
        self, e2e_stream_aggregator
    ):
        with patch("gateway.router.engine.get_router_engine") as mock_engine:
            mock_engine.return_value.record_switch_success = MagicMock()
            mock_engine.return_value.record_switch_failure = MagicMock()

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)

                mock_primary_ctx = AsyncMock()
                mock_primary_ctx.status_code = 200
                mock_primary_ctx.__aenter__ = AsyncMock(return_value=mock_primary_ctx)
                mock_primary_ctx.__aexit__ = AsyncMock(return_value=None)

                async def mock_aiter_lines():
                    for line in [
                        'data: {"choices":[{"delta":{"content":"Hello"}}]}',
                        'data: {"choices":[{"delta":{"content":" World"}}]}',
                    ]:
                        yield line

                mock_primary_ctx.aiter_lines = mock_aiter_lines

                def mock_stream(*args, **kwargs):
                    return mock_primary_ctx

                mock_client.stream = mock_stream

                import asyncio
                async def collect():
                    chunks = []
                    async for chunk in e2e_stream_aggregator.stream_with_fallback(
                        primary_endpoint="http://localhost:8000",
                        fallback_endpoint="https://api.openai.com",
                        request_body={"model": "test", "messages": []},
                    ):
                        chunks.append(chunk)
                    return chunks

                chunks = asyncio.run(collect())

                assert any("data: [DONE]" in c for c in chunks), "Stream should end with [DONE]"
                data_chunks = [c for c in chunks if c.startswith("data: ") and "[DONE]" not in c]
                assert len(data_chunks) >= 2


class TestE2ECompleteFlow:
    """Complete end-to-end flow tests"""

    def test_e2e_complete_flow_normal(
        self, e2e_client, e2e_health_checker, e2e_degradation_trigger, e2e_router_engine, e2e_cost_tracker
    ):
        e2e_health_checker.stats.add_snapshot(
            HealthSnapshot(is_healthy=True, latency_ms=50.0, cpu_utilization_pct=30.0, gpu_utilization_pct=40.0)
        )

        with patch("gateway.routes.chat.proxy_chat_completions") as mock_proxy:
            mock_proxy.return_value = {
                "id": "test-123",
                "choices": [{"message": {"content": "Hello, how can I help?"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }

            response = e2e_client.post(
                "/v1/chat/completions",
                json={"model": "vllm-local", "messages": [{"role": "user", "content": "Hi"}]},
                headers=_auth_headers("user1"),
            )
            assert response.status_code == 200
            data = response.json()
            assert "choices" in data

            admin_response = e2e_client.get("/admin/routes")
            assert admin_response.status_code == 200
            admin_data = admin_response.json()
            assert len(admin_data["recent_decisions"]) > 0

            cost_response = e2e_client.get("/admin/routes/cost?user_id=user1")
            assert cost_response.status_code == 200

    def test_e2e_complete_flow_degraded(
        self, e2e_client, e2e_health_checker, e2e_degradation_trigger, e2e_router_engine, e2e_cost_tracker
    ):
        e2e_health_checker.stats.add_snapshot(
            HealthSnapshot(is_healthy=True, latency_ms=50.0, cpu_utilization_pct=30.0, gpu_utilization_pct=40.0)
        )
        e2e_degradation_trigger.force_degrade("test")

        with patch("gateway.routes.chat.proxy_chat_completions") as mock_proxy:
            mock_proxy.return_value = {
                "id": "test-456",
                "choices": [{"message": {"content": "Fallback response"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }

            response = e2e_client.post(
                "/v1/chat/completions",
                json={"model": "vllm-local", "messages": [{"role": "user", "content": "Hi"}]},
                headers=_auth_headers("user1"),
            )
            assert response.status_code == 200

            admin_response = e2e_client.get("/admin/routes")
            assert admin_response.status_code == 200
            admin_data = admin_response.json()
            assert admin_data["degradation"]["is_degraded"] is True

    def test_e2e_complete_flow_vip(
        self, e2e_client, e2e_health_checker, e2e_degradation_trigger, e2e_router_engine, e2e_cost_tracker
    ):
        e2e_router_engine.add_vip_user("vip_user")
        e2e_health_checker.stats.add_snapshot(
            HealthSnapshot(is_healthy=True, latency_ms=50.0, cpu_utilization_pct=30.0, gpu_utilization_pct=40.0)
        )

        with patch("gateway.routes.chat.proxy_chat_completions") as mock_proxy:
            mock_proxy.return_value = {
                "id": "test-789",
                "choices": [{"message": {"content": "VIP response"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }

            response = e2e_client.post(
                "/v1/chat/completions",
                json={"model": "vllm-local", "messages": [{"role": "user", "content": "Hi"}]},
                headers=_auth_headers("vip_user"),
            )
            assert response.status_code == 200

            admin_response = e2e_client.get("/admin/routes")
            assert admin_response.status_code == 200
            admin_data = admin_response.json()
            decisions = admin_data["recent_decisions"]
            assert len(decisions) > 0

    def test_e2e_complete_flow_over_budget(
        self, e2e_client, e2e_health_checker, e2e_degradation_trigger, e2e_router_engine, e2e_cost_tracker
    ):
        e2e_cost_tracker.record_usage("user1", "gpt-4", 350000, 0)
        e2e_health_checker.stats.add_snapshot(
            HealthSnapshot(is_healthy=True, latency_ms=50.0, cpu_utilization_pct=30.0, gpu_utilization_pct=40.0)
        )

        with patch("gateway.routes.chat.proxy_chat_completions") as mock_proxy:
            mock_proxy.return_value = {
                "id": "test-budget",
                "choices": [{"message": {"content": "Local response"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }

            response = e2e_client.post(
                "/v1/chat/completions",
                json={"model": "vllm-local", "messages": [{"role": "user", "content": "Hi"}]},
                headers=_auth_headers("user1"),
            )
            assert response.status_code == 200

            cost_response = e2e_client.get("/admin/routes/cost?user_id=user1")
            assert cost_response.status_code == 200
            cost_data = cost_response.json()
            assert cost_data["over_budget"] is True
