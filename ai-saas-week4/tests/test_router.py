"""Router module unit tests"""

import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from gateway.router.config import RouterConfig, router_config
from gateway.router.health_checker import (
    HealthChecker,
    HealthSnapshot,
    HealthStats,
    get_health_checker,
    set_health_checker,
)
from gateway.router.degradation import (
    DegradationDecision,
    DegradationReason,
    DegradationTrigger,
    get_degradation_trigger,
    set_degradation_trigger,
)
from gateway.router.engine import (
    RouteDecision,
    RouteReason,
    RouteTarget,
    RouterEngine,
    get_router_engine,
    set_router_engine,
)
from gateway.router.cost_tracker import (
    CostRecord,
    CostTracker,
    UserCost,
    get_cost_tracker,
    set_cost_tracker,
)
from gateway.router.stream_aggregator import (
    StreamAggregator,
    PrimaryStreamError,
    get_stream_aggregator,
    set_stream_aggregator,
)
from gateway.router.metrics import (
    RouterMetrics,
    get_metrics,
    set_metrics,
)


class TestRouterConfig:
    def test_default_values(self):
        config = RouterConfig()
        assert config.health_check_interval == 5.0
        assert config.degradation_p99_threshold_ms == 800.0
        assert config.degradation_consecutive_5xx == 3
        assert config.degradation_gpu_memory_pct == 95.0
        assert config.cost_monthly_cap_usd == 10.0
        assert config.switch_latency_budget_ms == 50.0

    def test_custom_values(self):
        config = RouterConfig(
            health_check_interval=3.0,
            degradation_p99_threshold_ms=500.0,
            cost_monthly_cap_usd=5.0,
        )
        assert config.health_check_interval == 3.0
        assert config.degradation_p99_threshold_ms == 500.0
        assert config.cost_monthly_cap_usd == 5.0


class TestHealthSnapshot:
    def test_default_snapshot(self):
        snap = HealthSnapshot()
        assert snap.is_healthy is False
        assert snap.latency_ms == 0.0
        assert snap.queue_depth == 0
        assert snap.gpu_memory_pct == 0.0

    def test_healthy_snapshot(self):
        snap = HealthSnapshot(
            is_healthy=True,
            latency_ms=50.0,
            queue_depth=3,
            gpu_memory_pct=60.0,
            cpu_utilization_pct=40.0,
            gpu_utilization_pct=55.0,
        )
        assert snap.is_healthy is True
        assert snap.latency_ms == 50.0
        assert snap.queue_depth == 3
        assert snap.gpu_memory_pct == 60.0


class TestHealthStats:
    def test_empty_stats(self):
        stats = HealthStats(endpoint="http://localhost:8000")
        assert stats.success_rate == 0.0
        assert stats.p50_latency_ms == 0.0
        assert stats.p99_latency_ms == 0.0
        assert stats.avg_queue_depth == 0.0
        assert stats.consecutive_5xx == 0

    def test_success_rate(self):
        stats = HealthStats(endpoint="http://localhost:8000")
        for i in range(8):
            stats.add_snapshot(HealthSnapshot(is_healthy=True, latency_ms=10.0))
        for i in range(2):
            stats.add_snapshot(HealthSnapshot(is_healthy=False, latency_ms=0))
        assert stats.success_rate == 0.8

    def test_percentiles(self):
        stats = HealthStats(endpoint="http://localhost:8000")
        latencies = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        for lat in latencies:
            stats.add_snapshot(HealthSnapshot(is_healthy=True, latency_ms=lat))
        assert stats.p50_latency_ms == 50.0
        assert stats.p99_latency_ms == 100.0

    def test_consecutive_5xx(self):
        stats = HealthStats(endpoint="http://localhost:8000")
        for i in range(3):
            stats.add_snapshot(HealthSnapshot(is_healthy=False, error="500"))
        assert stats.consecutive_5xx == 3

    def test_consecutive_5xx_reset(self):
        stats = HealthStats(endpoint="http://localhost:8000")
        stats.add_snapshot(HealthSnapshot(is_healthy=False, error="500"))
        stats.add_snapshot(HealthSnapshot(is_healthy=True, latency_ms=10.0))
        stats.add_snapshot(HealthSnapshot(is_healthy=False, error="500"))
        assert stats.consecutive_5xx == 1

    def test_max_snapshots(self):
        stats = HealthStats(endpoint="http://localhost:8000", max_snapshots=5)
        for i in range(10):
            stats.add_snapshot(HealthSnapshot(is_healthy=True, latency_ms=float(i)))
        assert len(stats.snapshots) == 5
        assert stats.snapshots[0].latency_ms == 5.0


class TestHealthChecker:
    @pytest.mark.asyncio
    async def test_probe_healthy(self):
        checker = HealthChecker(endpoint="http://localhost:8000")
        with patch("httpx.AsyncClient") as mock_client:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "queue_depth": 5,
                "gpu_memory_pct": 60.0,
                "cpu_utilization_pct": 30.0,
                "gpu_utilization_pct": 45.0,
            }
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)

            snapshot = await checker.probe()
            assert snapshot.is_healthy is True
            assert snapshot.queue_depth == 5
            assert snapshot.gpu_memory_pct == 60.0

    @pytest.mark.asyncio
    async def test_probe_unhealthy(self):
        checker = HealthChecker(endpoint="http://localhost:8000")
        with patch("httpx.AsyncClient") as mock_client:
            mock_resp = MagicMock()
            mock_resp.status_code = 500
            mock_resp.text = ""
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)

            snapshot = await checker.probe()
            assert snapshot.is_healthy is False
            assert snapshot.error == "500"

    @pytest.mark.asyncio
    async def test_probe_timeout(self):
        checker = HealthChecker(endpoint="http://localhost:8000")
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=Exception("Connection timeout")
            )
            snapshot = await checker.probe()
            assert snapshot.is_healthy is False
            assert "Connection timeout" in snapshot.error

    def test_is_healthy_no_snapshots(self):
        checker = HealthChecker(endpoint="http://localhost:8000")
        assert checker.is_healthy() is True

    def test_is_healthy_with_snapshots(self):
        checker = HealthChecker(endpoint="http://localhost:8000")
        checker.stats.add_snapshot(HealthSnapshot(is_healthy=True, latency_ms=10.0))
        assert checker.is_healthy() is True
        checker.stats.add_snapshot(HealthSnapshot(is_healthy=False, error="500"))
        assert checker.is_healthy() is False


class TestDegradationTrigger:
    def test_no_degradation_when_healthy(self):
        trigger = DegradationTrigger()
        stats = HealthStats(endpoint="http://localhost:8000")
        stats.add_snapshot(HealthSnapshot(is_healthy=True, latency_ms=50.0, gpu_memory_pct=50.0))

        decision = trigger.evaluate(stats)
        assert decision.should_degrade is False
        assert decision.reason == DegradationReason.NONE

    def test_degradation_p99_latency(self):
        trigger = DegradationTrigger()
        stats = HealthStats(endpoint="http://localhost:8000")
        for i in range(10):
            stats.add_snapshot(HealthSnapshot(is_healthy=True, latency_ms=900.0))

        decision = trigger.evaluate(stats)
        assert decision.should_degrade is True
        assert decision.reason == DegradationReason.P99_LATENCY

    def test_degradation_consecutive_5xx(self):
        trigger = DegradationTrigger()
        stats = HealthStats(endpoint="http://localhost:8000")
        for i in range(3):
            stats.add_snapshot(HealthSnapshot(is_healthy=False, error="500"))

        decision = trigger.evaluate(stats)
        assert decision.should_degrade is True
        assert decision.reason == DegradationReason.CONSECUTIVE_5XX

    def test_degradation_gpu_memory(self):
        trigger = DegradationTrigger()
        stats = HealthStats(endpoint="http://localhost:8000")
        stats.add_snapshot(HealthSnapshot(is_healthy=True, latency_ms=50.0, gpu_memory_pct=97.0))

        decision = trigger.evaluate(stats)
        assert decision.should_degrade is True
        assert decision.reason == DegradationReason.GPU_MEMORY

    def test_degradation_recovery(self):
        trigger = DegradationTrigger()
        stats = HealthStats(endpoint="http://localhost:8000")

        stats.add_snapshot(HealthSnapshot(is_healthy=False, error="500"))
        stats.add_snapshot(HealthSnapshot(is_healthy=False, error="500"))
        stats.add_snapshot(HealthSnapshot(is_healthy=False, error="500"))
        decision = trigger.evaluate(stats)
        assert decision.should_degrade is True
        assert trigger.is_degraded is True

        stats.add_snapshot(HealthSnapshot(is_healthy=True, latency_ms=50.0, gpu_memory_pct=50.0))
        decision = trigger.evaluate(stats)
        assert decision.should_degrade is False
        assert trigger.is_degraded is False

    def test_force_degrade_and_recover(self):
        trigger = DegradationTrigger()
        trigger.force_degrade("test")
        assert trigger.is_degraded is True
        assert trigger.last_decision.reason == DegradationReason.MANUAL

        trigger.force_recover()
        assert trigger.is_degraded is False

    def test_decision_history_limit(self):
        trigger = DegradationTrigger()
        stats = HealthStats(endpoint="http://localhost:8000")
        stats.add_snapshot(HealthSnapshot(is_healthy=True, latency_ms=50.0))

        for _ in range(1100):
            trigger.evaluate(stats)
        assert len(trigger.decision_history) <= 1000


class TestCostTracker:
    def test_record_usage(self):
        tracker = CostTracker()
        tracker.record_usage("user1", "gpt-4", 1000, 500)
        user_cost = tracker.get_user_cost("user1")
        assert user_cost is not None
        assert user_cost.monthly_cost_usd > 0
        assert user_cost.total_tokens == 1500

    def test_local_model_no_cost(self):
        tracker = CostTracker()
        tracker.record_usage("user1", "vllm-local", 1000, 500)
        user_cost = tracker.get_user_cost("user1")
        assert user_cost.monthly_cost_usd == 0.0

    def test_over_budget(self):
        tracker = CostTracker()
        tracker.record_usage("user1", "gpt-4", 350000, 0)
        assert tracker.is_over_budget("user1") is True

    def test_under_budget(self):
        tracker = CostTracker()
        tracker.record_usage("user1", "gpt-4", 1000, 500)
        assert tracker.is_over_budget("user1") is False

    def test_unknown_user_not_over_budget(self):
        tracker = CostTracker()
        assert tracker.is_over_budget("unknown") is False

    def test_multiple_users(self):
        tracker = CostTracker()
        tracker.record_usage("user1", "gpt-4", 1000, 500)
        tracker.record_usage("user2", "gpt-3.5-turbo", 2000, 1000)
        all_costs = tracker.get_all_costs()
        assert len(all_costs) == 2
        assert all_costs["user1"].monthly_cost_usd > all_costs["user2"].monthly_cost_usd

    def test_monthly_total(self):
        tracker = CostTracker()
        tracker.record_usage("user1", "gpt-4", 1000, 500)
        tracker.record_usage("user2", "gpt-3.5-turbo", 2000, 1000)
        total = tracker.get_monthly_total()
        assert total > 0

    def test_records_limit(self):
        tracker = CostTracker()
        for i in range(11000):
            tracker.record_usage("user1", "gpt-4", 10, 10)
        user_cost = tracker.get_user_cost("user1")
        assert len(user_cost.records) <= 10000


class TestRouterEngine:
    def test_default_route_local(self):
        engine = RouterEngine()
        with patch("gateway.router.engine.get_health_checker") as mock_hc, \
             patch("gateway.router.engine.get_degradation_trigger") as mock_dt, \
             patch("gateway.router.engine.get_cost_tracker") as mock_ct:

            mock_hc.return_value.stats.latest_cpu_pct = 30.0
            mock_hc.return_value.stats.latest_gpu_pct = 40.0
            mock_dt.return_value.is_degraded = False
            mock_ct.return_value.is_over_budget.return_value = False

            decision = engine.decide(user_id="user1")
            assert decision.target == RouteTarget.LOCAL_VLLM
            assert decision.reason == RouteReason.DEFAULT

    def test_vip_route_to_gpt4(self):
        engine = RouterEngine()
        engine.add_vip_user("vip_user")

        with patch("gateway.router.engine.get_health_checker"), \
             patch("gateway.router.engine.get_degradation_trigger"), \
             patch("gateway.router.engine.get_cost_tracker"):

            decision = engine.decide(user_id="vip_user")
            assert decision.target == RouteTarget.CLOUD_GPT4
            assert decision.reason == RouteReason.VIP_USER

    def test_degradation_route_to_cloud(self):
        engine = RouterEngine()
        with patch("gateway.router.engine.get_health_checker") as mock_hc, \
             patch("gateway.router.engine.get_degradation_trigger") as mock_dt, \
             patch("gateway.router.engine.get_cost_tracker") as mock_ct:

            mock_hc.return_value.stats.latest_cpu_pct = 30.0
            mock_hc.return_value.stats.latest_gpu_pct = 40.0
            mock_dt.return_value.is_degraded = True
            mock_dt.return_value.last_decision.detail = "P99 latency high"
            mock_ct.return_value.is_over_budget.return_value = False

            decision = engine.decide(user_id="user1")
            assert decision.target == RouteTarget.CLOUD_GPT35
            assert decision.reason == RouteReason.DEGRADATION

    def test_over_budget_route_to_local(self):
        engine = RouterEngine()
        with patch("gateway.router.engine.get_health_checker") as mock_hc, \
             patch("gateway.router.engine.get_degradation_trigger") as mock_dt, \
             patch("gateway.router.engine.get_cost_tracker") as mock_ct:

            mock_hc.return_value.stats.latest_cpu_pct = 30.0
            mock_hc.return_value.stats.latest_gpu_pct = 40.0
            mock_dt.return_value.is_degraded = False
            mock_ct.return_value.is_over_budget.return_value = True

            decision = engine.decide(user_id="user1")
            assert decision.target == RouteTarget.LOCAL_VLLM
            assert decision.reason == RouteReason.OVER_BUDGET

    def test_load_balance_route_to_cloud(self):
        engine = RouterEngine()
        with patch("gateway.router.engine.get_health_checker") as mock_hc, \
             patch("gateway.router.engine.get_degradation_trigger") as mock_dt, \
             patch("gateway.router.engine.get_cost_tracker") as mock_ct:

            mock_hc.return_value.stats.latest_cpu_pct = 90.0
            mock_hc.return_value.stats.latest_gpu_pct = 40.0
            mock_dt.return_value.is_degraded = False
            mock_ct.return_value.is_over_budget.return_value = False

            decision = engine.decide(user_id="user1")
            assert decision.target == RouteTarget.CLOUD_GPT35
            assert decision.reason == RouteReason.LOAD_BALANCE

    def test_vip_user(self):
        engine = RouterEngine()
        assert engine.is_vip("user1") is False
        engine.add_vip_user("user1")
        assert engine.is_vip("user1") is True
        engine.remove_vip_user("user1")
        assert engine.is_vip("user1") is False

    def test_switch_failure_rate(self):
        engine = RouterEngine()
        assert engine.switch_failure_rate == 0.0

        engine.record_switch_success()
        engine.record_switch_success()
        engine.record_switch_failure()
        assert engine.switch_failure_rate == 1.0 / 3.0

    def test_decision_history(self):
        engine = RouterEngine()
        with patch("gateway.router.engine.get_health_checker") as mock_hc, \
             patch("gateway.router.engine.get_degradation_trigger") as mock_dt, \
             patch("gateway.router.engine.get_cost_tracker") as mock_ct:

            mock_hc.return_value.stats.latest_cpu_pct = 30.0
            mock_hc.return_value.stats.latest_gpu_pct = 40.0
            mock_dt.return_value.is_degraded = False
            mock_ct.return_value.is_over_budget.return_value = False

            engine.decide(user_id="user1")
            engine.decide(user_id="user2")
            assert len(engine.decision_history) == 2

    def test_switch_latency_recorded(self):
        engine = RouterEngine()
        with patch("gateway.router.engine.get_health_checker") as mock_hc, \
             patch("gateway.router.engine.get_degradation_trigger") as mock_dt, \
             patch("gateway.router.engine.get_cost_tracker") as mock_ct:

            mock_hc.return_value.stats.latest_cpu_pct = 30.0
            mock_hc.return_value.stats.latest_gpu_pct = 40.0
            mock_dt.return_value.is_degraded = False
            mock_ct.return_value.is_over_budget.return_value = False

            decision = engine.decide(user_id="user1")
            assert decision.switch_latency_ms >= 0
            assert decision.user_id == "user1"


class TestStreamAggregator:
    def test_primary_stream_error(self):
        error = PrimaryStreamError(500, "Server error")
        assert error.status_code == 500
        assert error.message == "Server error"

    @pytest.mark.asyncio
    async def test_stream_with_fallback_on_primary_error(self):
        aggregator = StreamAggregator()
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
                async for chunk in aggregator.stream_with_fallback(
                    primary_endpoint="http://localhost:8000",
                    fallback_endpoint="https://api.openai.com",
                    request_body={"model": "test", "messages": []},
                ):
                    chunks.append(chunk)

                assert len(chunks) > 0


class TestRouterMetrics:
    def test_metrics_disabled_without_prometheus(self):
        with patch("gateway.router.metrics.HAS_PROMETHEUS", False):
            metrics = RouterMetrics()
            assert metrics._enabled is False
            metrics.record_route_decision("test", "test")
            metrics.record_route_switch(True, 10.0)
            assert "prometheus_client not installed" in metrics.get_metrics_text()

    def test_metrics_record_route_decision(self):
        metrics = RouterMetrics()
        if metrics._enabled:
            metrics.record_route_decision("vllm-local", "default")
            text = metrics.get_metrics_text()
            assert "gateway_route_decisions_total" in text

    def test_metrics_record_route_switch(self):
        metrics = RouterMetrics()
        if metrics._enabled:
            metrics.record_route_switch(True, 25.0)
            text = metrics.get_metrics_text()
            assert "gateway_route_switch_total" in text

    def test_metrics_degradation_status(self):
        metrics = RouterMetrics()
        if metrics._enabled:
            metrics.set_degradation_status(True)
            text = metrics.get_metrics_text()
            assert "gateway_degradation_active" in text

    def test_metrics_health_check(self):
        metrics = RouterMetrics()
        if metrics._enabled:
            metrics.record_health_check(True)
            text = metrics.get_metrics_text()
            assert "gateway_health_check_total" in text

    def test_metrics_update_health(self):
        metrics = RouterMetrics()
        if metrics._enabled:
            metrics.update_health_metrics(50.0, 200.0)
            text = metrics.get_metrics_text()
            assert "gateway_health_latency_p50_ms" in text
            assert "gateway_health_latency_p99_ms" in text

    def test_metrics_update_resource(self):
        metrics = RouterMetrics()
        if metrics._enabled:
            metrics.update_resource_metrics(60.0, 30.0, 45.0)
            text = metrics.get_metrics_text()
            assert "gateway_gpu_memory_pct" in text

    def test_metrics_update_cost(self):
        metrics = RouterMetrics()
        if metrics._enabled:
            metrics.update_user_cost("user1", 5.0)
            metrics.update_total_cost(15.0)
            text = metrics.get_metrics_text()
            assert "gateway_user_cost_usd" in text
            assert "gateway_total_monthly_cost_usd" in text

    def test_metrics_stream_fallback(self):
        metrics = RouterMetrics()
        if metrics._enabled:
            metrics.record_stream_fallback(True)
            text = metrics.get_metrics_text()
            assert "gateway_stream_fallback_total" in text


class TestSingletonPatterns:
    def test_health_checker_singleton(self):
        hc1 = get_health_checker()
        hc2 = get_health_checker()
        assert hc1 is hc2

    def test_degradation_trigger_singleton(self):
        dt1 = get_degradation_trigger()
        dt2 = get_degradation_trigger()
        assert dt1 is dt2

    def test_router_engine_singleton(self):
        re1 = get_router_engine()
        re2 = get_router_engine()
        assert re1 is re2

    def test_cost_tracker_singleton(self):
        ct1 = get_cost_tracker()
        ct2 = get_cost_tracker()
        assert ct1 is ct2

    def test_stream_aggregator_singleton(self):
        sa1 = get_stream_aggregator()
        sa2 = get_stream_aggregator()
        assert sa1 is sa2

    def test_metrics_singleton(self):
        m1 = get_metrics()
        m2 = get_metrics()
        assert m1 is m2

    def test_set_health_checker(self):
        original = get_health_checker()
        new = HealthChecker(endpoint="http://test:8000")
        set_health_checker(new)
        assert get_health_checker() is new
        set_health_checker(original)

    def test_set_router_engine(self):
        original = get_router_engine()
        new = RouterEngine()
        set_router_engine(new)
        assert get_router_engine() is new
        set_router_engine(original)

    def test_set_cost_tracker(self):
        original = get_cost_tracker()
        new = CostTracker()
        set_cost_tracker(new)
        assert get_cost_tracker() is new
        set_cost_tracker(original)

    def test_set_degradation_trigger(self):
        original = get_degradation_trigger()
        new = DegradationTrigger()
        set_degradation_trigger(new)
        assert get_degradation_trigger() is new
        set_degradation_trigger(original)

    def test_set_stream_aggregator(self):
        original = get_stream_aggregator()
        new = StreamAggregator()
        set_stream_aggregator(new)
        assert get_stream_aggregator() is new
        set_stream_aggregator(original)

    def test_set_metrics(self):
        original = get_metrics()
        new = RouterMetrics()
        set_metrics(new)
        assert get_metrics() is new
        set_metrics(original)
