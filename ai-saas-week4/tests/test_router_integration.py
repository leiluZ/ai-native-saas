"""Router component integration tests"""

import pytest
import json
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
def test_health_checker():
    checker = HealthChecker(endpoint="http://localhost:8000")
    set_health_checker(checker)
    yield checker
    set_health_checker(HealthChecker(endpoint="http://localhost:8000"))


@pytest.fixture
def test_degradation_trigger():
    trigger = DegradationTrigger()
    set_degradation_trigger(trigger)
    yield trigger
    set_degradation_trigger(DegradationTrigger())


@pytest.fixture
def test_router_engine():
    engine = RouterEngine()
    set_router_engine(engine)
    yield engine
    set_router_engine(RouterEngine())


@pytest.fixture
def test_cost_tracker():
    tracker = CostTracker()
    set_cost_tracker(tracker)
    yield tracker
    set_cost_tracker(CostTracker())


@pytest.fixture
def test_stream_aggregator():
    aggregator = StreamAggregator()
    set_stream_aggregator(aggregator)
    yield aggregator
    set_stream_aggregator(StreamAggregator())


@pytest.fixture
def test_metrics():
    metrics = RouterMetrics()
    set_metrics(metrics)
    yield metrics
    set_metrics(RouterMetrics())


class TestHealthCheckDegradationIntegration:
    """Test integration between health checker and degradation trigger"""

    def test_health_feeds_degradation(self, test_health_checker, test_degradation_trigger):
        for i in range(3):
            test_health_checker.stats.add_snapshot(
                HealthSnapshot(is_healthy=False, error="500")
            )

        decision = test_degradation_trigger.evaluate(test_health_checker.stats)
        assert decision.should_degrade is True
        assert test_degradation_trigger.is_degraded is True

    def test_health_recovery_clears_degradation(self, test_health_checker, test_degradation_trigger):
        for i in range(3):
            test_health_checker.stats.add_snapshot(
                HealthSnapshot(is_healthy=False, error="500")
            )
        test_degradation_trigger.evaluate(test_health_checker.stats)
        assert test_degradation_trigger.is_degraded is True

        test_health_checker.stats.add_snapshot(
            HealthSnapshot(is_healthy=True, latency_ms=50.0, gpu_memory_pct=50.0)
        )
        decision = test_degradation_trigger.evaluate(test_health_checker.stats)
        assert decision.should_degrade is False
        assert test_degradation_trigger.is_degraded is False

    def test_p99_latency_triggers_degradation(self, test_health_checker, test_degradation_trigger):
        for i in range(10):
            test_health_checker.stats.add_snapshot(
                HealthSnapshot(is_healthy=True, latency_ms=900.0)
            )

        decision = test_degradation_trigger.evaluate(test_health_checker.stats)
        assert decision.should_degrade is True

    def test_gpu_memory_triggers_degradation(self, test_health_checker, test_degradation_trigger):
        test_health_checker.stats.add_snapshot(
            HealthSnapshot(is_healthy=True, latency_ms=50.0, gpu_memory_pct=97.0)
        )

        decision = test_degradation_trigger.evaluate(test_health_checker.stats)
        assert decision.should_degrade is True


class TestRouterEngineIntegration:
    """Test integration between router engine and other components"""

    def test_router_respects_degradation(
        self, test_health_checker, test_degradation_trigger, test_router_engine, test_cost_tracker
    ):
        test_health_checker.stats.add_snapshot(
            HealthSnapshot(is_healthy=True, latency_ms=50.0, cpu_utilization_pct=30.0, gpu_utilization_pct=40.0)
        )
        test_degradation_trigger.force_degrade("test")

        decision = test_router_engine.decide(user_id="user1")
        assert decision.reason.value == "degradation"

    def test_router_respects_cost_budget(
        self, test_health_checker, test_degradation_trigger, test_router_engine, test_cost_tracker
    ):
        test_health_checker.stats.add_snapshot(
            HealthSnapshot(is_healthy=True, latency_ms=50.0, cpu_utilization_pct=30.0, gpu_utilization_pct=40.0)
        )
        test_cost_tracker.record_usage("user1", "gpt-4", 350000, 0)

        decision = test_router_engine.decide(user_id="user1")
        assert decision.reason.value == "over_budget"

    def test_router_respects_load_balance(
        self, test_health_checker, test_degradation_trigger, test_router_engine, test_cost_tracker
    ):
        test_health_checker.stats.add_snapshot(
            HealthSnapshot(is_healthy=True, latency_ms=50.0, cpu_utilization_pct=90.0, gpu_utilization_pct=40.0)
        )

        decision = test_router_engine.decide(user_id="user1")
        assert decision.reason.value == "load_balance"

    def test_vip_overrides_all(
        self, test_health_checker, test_degradation_trigger, test_router_engine, test_cost_tracker
    ):
        test_router_engine.add_vip_user("vip_user")
        test_degradation_trigger.force_degrade("test")
        test_cost_tracker.record_usage("vip_user", "gpt-4", 350000, 0)

        decision = test_router_engine.decide(user_id="vip_user")
        assert decision.reason.value == "vip_user"
        assert decision.target.value == "gpt-4"

    def test_decision_logging_complete(
        self, test_health_checker, test_degradation_trigger, test_router_engine, test_cost_tracker
    ):
        test_health_checker.stats.add_snapshot(
            HealthSnapshot(is_healthy=True, latency_ms=50.0, cpu_utilization_pct=30.0, gpu_utilization_pct=40.0)
        )

        decision = test_router_engine.decide(user_id="user1")
        assert decision.target is not None
        assert decision.reason is not None
        assert decision.detail != ""
        assert decision.switch_latency_ms >= 0
        assert decision.user_id == "user1"
        assert decision.timestamp > 0

    def test_switch_latency_under_budget(
        self, test_health_checker, test_degradation_trigger, test_router_engine, test_cost_tracker
    ):
        test_health_checker.stats.add_snapshot(
            HealthSnapshot(is_healthy=True, latency_ms=50.0, cpu_utilization_pct=30.0, gpu_utilization_pct=40.0)
        )

        decision = test_router_engine.decide(user_id="user1")
        assert decision.switch_latency_ms < 50.0, f"Switch latency {decision.switch_latency_ms}ms exceeds 50ms budget"


class TestCostTrackerIntegration:
    """Test cost tracker integration with router"""

    def test_cost_accumulates_correctly(self, test_cost_tracker):
        test_cost_tracker.record_usage("user1", "gpt-4", 1000, 500)
        test_cost_tracker.record_usage("user1", "gpt-4", 500, 250)

        user_cost = test_cost_tracker.get_user_cost("user1")
        assert user_cost.total_tokens == 2250

    def test_cost_tracking_accurate(self, test_cost_tracker):
        test_cost_tracker.record_usage("user1", "gpt-4", 1000, 0)
        cost = test_cost_tracker.get_user_cost("user1").monthly_cost_usd
        expected = 1000 / 1000 * 0.03
        assert abs(cost - expected) < 0.0001

    def test_local_model_zero_cost(self, test_cost_tracker):
        test_cost_tracker.record_usage("user1", "vllm-local", 1000000, 1000000)
        assert test_cost_tracker.get_user_cost("user1").monthly_cost_usd == 0.0

    def test_budget_enforcement(self, test_cost_tracker, test_router_engine):
        test_cost_tracker.record_usage("user1", "gpt-4", 350000, 0)
        assert test_cost_tracker.is_over_budget("user1") is True

        test_health_checker = HealthChecker(endpoint="http://localhost:8000")
        test_health_checker.stats.add_snapshot(
            HealthSnapshot(is_healthy=True, latency_ms=50.0, cpu_utilization_pct=30.0, gpu_utilization_pct=40.0)
        )
        set_health_checker(test_health_checker)

        decision = test_router_engine.decide(user_id="user1")
        assert decision.reason.value == "over_budget"


class TestMetricsIntegration:
    """Test metrics integration"""

    def test_metrics_record_full_pipeline(self, test_metrics, test_router_engine):
        if not test_metrics._enabled:
            pytest.skip("prometheus_client not installed")

        test_metrics.record_route_decision("vllm-local", "default")
        test_metrics.record_route_switch(True, 10.0)
        test_metrics.set_degradation_status(False)
        test_metrics.record_health_check(True)
        test_metrics.update_health_metrics(50.0, 200.0)
        test_metrics.update_resource_metrics(60.0, 30.0, 45.0)
        test_metrics.update_user_cost("user1", 5.0)
        test_metrics.update_total_cost(15.0)
        test_metrics.record_stream_fallback(True)

        text = test_metrics.get_metrics_text()
        assert "gateway_route_decisions_total" in text
        assert "gateway_route_switch_total" in text
        assert "gateway_degradation_active" in text
        assert "gateway_health_check_total" in text
        assert "gateway_health_latency_p50_ms" in text
        assert "gateway_health_latency_p99_ms" in text
        assert "gateway_gpu_memory_pct" in text
        assert "gateway_cpu_utilization_pct" in text
        assert "gateway_gpu_utilization_pct" in text
        assert "gateway_user_cost_usd" in text
        assert "gateway_total_monthly_cost_usd" in text
        assert "gateway_stream_fallback_total" in text


class TestAdminRoutesIntegration:
    """Test admin routes integration"""

    @pytest.fixture
    def admin_client(self, test_health_checker, test_degradation_trigger, test_router_engine, test_cost_tracker):
        from gateway.main import app
        app.dependency_overrides = {}
        return TestClient(app)

    def test_admin_routes_endpoint(self, admin_client):
        response = admin_client.get("/admin/routes")
        assert response.status_code == 200
        data = response.json()
        assert "health" in data
        assert "degradation" in data
        assert "cost" in data
        assert "switch_stats" in data
        assert "recent_decisions" in data

    def test_admin_health_detail(self, admin_client):
        response = admin_client.get("/admin/routes/health")
        assert response.status_code == 200
        data = response.json()
        assert "is_healthy" in data
        assert "stats" in data
        assert "degradation" in data

    def test_admin_cost_detail(self, admin_client):
        response = admin_client.get("/admin/routes/cost")
        assert response.status_code == 200
        data = response.json()
        assert "total_monthly_cost" in data

    def test_admin_cost_by_user(self, admin_client, test_cost_tracker):
        test_cost_tracker.record_usage("user1", "gpt-4", 1000, 500)
        response = admin_client.get("/admin/routes/cost?user_id=user1")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "user1"
        assert data["monthly_cost_usd"] > 0

    def test_admin_cost_user_not_found(self, admin_client):
        response = admin_client.get("/admin/routes/cost?user_id=nonexistent")
        assert response.status_code == 404

    def test_admin_add_vip(self, admin_client, test_router_engine):
        response = admin_client.post("/admin/routes/vip/vip_user_1")
        assert response.status_code == 200
        assert test_router_engine.is_vip("vip_user_1") is True

    def test_admin_remove_vip(self, admin_client, test_router_engine):
        test_router_engine.add_vip_user("vip_user_1")
        response = admin_client.delete("/admin/routes/vip/vip_user_1")
        assert response.status_code == 200
        assert test_router_engine.is_vip("vip_user_1") is False

    def test_admin_force_degrade(self, admin_client, test_degradation_trigger):
        response = admin_client.post("/admin/routes/degrade")
        assert response.status_code == 200
        assert test_degradation_trigger.is_degraded is True

    def test_admin_force_recover(self, admin_client, test_degradation_trigger):
        test_degradation_trigger.force_degrade("test")
        response = admin_client.post("/admin/routes/recover")
        assert response.status_code == 200
        assert test_degradation_trigger.is_degraded is False

    def test_admin_dashboard_html(self, admin_client):
        response = admin_client.get("/admin/routes/dashboard")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_admin_metrics(self, admin_client):
        response = admin_client.get("/admin/routes/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "prometheus_enabled" in data


class TestStreamAggregatorIntegration:
    """Test stream aggregator integration"""

    @pytest.mark.asyncio
    async def test_stream_fallback_preserves_content(self, test_stream_aggregator):
        with patch("gateway.router.engine.get_router_engine") as mock_engine:
            mock_engine.return_value.record_switch_success = MagicMock()
            mock_engine.return_value.record_switch_failure = MagicMock()

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)

                mock_primary_ctx = AsyncMock()
                mock_primary_ctx.status_code = 500
                mock_primary_ctx.__aenter__ = AsyncMock(return_value=mock_primary_ctx)
                mock_primary_ctx.__aexit__ = AsyncMock(return_value=None)

                async def mock_aiter_text():
                    yield "Internal Server Error"

                mock_primary_ctx.aiter_text = mock_aiter_text

                mock_fallback_ctx = AsyncMock()
                mock_fallback_ctx.status_code = 200
                mock_fallback_ctx.__aenter__ = AsyncMock(return_value=mock_fallback_ctx)
                mock_fallback_ctx.__aexit__ = AsyncMock(return_value=None)

                async def mock_aiter_lines():
                    for line in [
                        'data: {"choices":[{"delta":{"content":"Hello"}}]}',
                        'data: {"choices":[{"delta":{"content":" World"}}]}',
                    ]:
                        yield line

                mock_fallback_ctx.aiter_lines = mock_aiter_lines

                call_count = [0]

                def mock_stream(*args, **kwargs):
                    call_count[0] += 1
                    if call_count[0] == 1:
                        return mock_primary_ctx
                    return mock_fallback_ctx

                mock_client.stream = mock_stream

                chunks = []
                async for chunk in test_stream_aggregator.stream_with_fallback(
                    primary_endpoint="http://localhost:8000",
                    fallback_endpoint="https://api.openai.com",
                    request_body={"model": "test", "messages": []},
                ):
                    chunks.append(chunk)

                content_chunks = [c for c in chunks if "data:" in c and "[DONE]" not in c]
                assert len(content_chunks) >= 2

    @pytest.mark.asyncio
    async def test_stream_both_fail(self, test_stream_aggregator):
        with patch("gateway.router.engine.get_router_engine") as mock_engine:
            mock_engine.return_value.record_switch_success = MagicMock()
            mock_engine.return_value.record_switch_failure = MagicMock()

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)

                mock_primary_ctx = AsyncMock()
                mock_primary_ctx.status_code = 500
                mock_primary_ctx.__aenter__ = AsyncMock(return_value=mock_primary_ctx)
                mock_primary_ctx.__aexit__ = AsyncMock(return_value=None)

                mock_fallback_ctx = AsyncMock()
                mock_fallback_ctx.status_code = 500
                mock_fallback_ctx.__aenter__ = AsyncMock(return_value=mock_fallback_ctx)
                mock_fallback_ctx.__aexit__ = AsyncMock(return_value=None)

                call_count = [0]

                def mock_stream(*args, **kwargs):
                    call_count[0] += 1
                    if call_count[0] == 1:
                        return mock_primary_ctx
                    return mock_fallback_ctx

                mock_client.stream = mock_stream

                chunks = []
                async for chunk in test_stream_aggregator.stream_with_fallback(
                    primary_endpoint="http://localhost:8000",
                    fallback_endpoint="https://api.openai.com",
                    request_body={"model": "test", "messages": []},
                ):
                    chunks.append(chunk)

                error_chunks = [c for c in chunks if "error" in c.lower()]
                assert len(error_chunks) > 0
