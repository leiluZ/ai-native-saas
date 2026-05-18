"""Admin dashboard routes - /admin/routes for visualizing routing decisions, cost, latency"""

import logging
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, HTMLResponse

from gateway.router.cost_tracker import get_cost_tracker
from gateway.router.degradation import get_degradation_trigger
from gateway.router.engine import get_router_engine
from gateway.router.health_checker import get_health_checker
from gateway.router.metrics import get_metrics

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin"], prefix="/admin")


@router.get("/routes")
async def admin_routes_dashboard():
    engine = get_router_engine()
    health = get_health_checker()
    degradation = get_degradation_trigger()
    cost_tracker = get_cost_tracker()

    recent_decisions = engine.decision_history[-50:]

    decisions_data = []
    for d in reversed(recent_decisions):
        decisions_data.append({
            "timestamp": d.timestamp,
            "target": d.target.value,
            "reason": d.reason.value,
            "detail": d.detail,
            "switch_latency_ms": round(d.switch_latency_ms, 2),
            "user_id": d.user_id,
            "model_requested": d.model_requested,
        })

    health_data = {
        "is_healthy": health.is_healthy(),
        "success_rate": round(health.stats.success_rate * 100, 1),
        "p50_latency_ms": round(health.stats.p50_latency_ms, 2),
        "p99_latency_ms": round(health.stats.p99_latency_ms, 2),
        "avg_queue_depth": round(health.stats.avg_queue_depth, 1),
        "gpu_memory_pct": round(health.stats.latest_gpu_memory_pct, 1),
        "cpu_pct": round(health.stats.latest_cpu_pct, 1),
        "gpu_pct": round(health.stats.latest_gpu_pct, 1),
        "consecutive_5xx": health.stats.consecutive_5xx,
    }

    degradation_data = {
        "is_degraded": degradation.is_degraded,
        "last_decision": {
            "should_degrade": degradation.last_decision.should_degrade,
            "reason": degradation.last_decision.reason.value,
            "detail": degradation.last_decision.detail,
            "timestamp": degradation.last_decision.timestamp,
        },
    }

    cost_data = {
        "total_monthly_cost": round(cost_tracker.get_monthly_total(), 4),
        "users": [],
    }
    for user_id, user_cost in cost_tracker.get_all_costs().items():
        cost_data["users"].append({
            "user_id": user_id,
            "monthly_cost_usd": round(user_cost.monthly_cost_usd, 4),
            "total_tokens": user_cost.total_tokens,
            "over_budget": cost_tracker.is_over_budget(user_id),
        })

    switch_data = {
        "switch_count": engine._switch_count,
        "switch_failure_count": engine._switch_failure_count,
        "switch_failure_rate": round(engine.switch_failure_rate * 100, 2),
    }

    return JSONResponse({
        "health": health_data,
        "degradation": degradation_data,
        "cost": cost_data,
        "switch_stats": switch_data,
        "recent_decisions": decisions_data,
    })


@router.get("/routes/dashboard", response_class=HTMLResponse)
async def admin_routes_html():
    return HTMLResponse("""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gateway Admin Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; padding: 24px; }
        h1 { font-size: 24px; margin-bottom: 24px; color: #38bdf8; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; margin-bottom: 24px; }
        .card { background: #1e293b; border-radius: 12px; padding: 20px; border: 1px solid #334155; }
        .card h2 { font-size: 16px; color: #94a3b8; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
        .metric { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #1e293b; }
        .metric:last-child { border-bottom: none; }
        .metric-label { color: #94a3b8; }
        .metric-value { font-weight: 600; }
        .metric-value.good { color: #4ade80; }
        .metric-value.warn { color: #fbbf24; }
        .metric-value.bad { color: #f87171; }
        table { width: 100%; border-collapse: collapse; margin-top: 12px; }
        th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #334155; font-size: 13px; }
        th { color: #94a3b8; font-weight: 500; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
        .badge-local { background: #1e40af; color: #93c5fd; }
        .badge-cloud { background: #7c3aed; color: #c4b5fd; }
        .badge-vip { background: #b45309; color: #fcd34d; }
        .refresh { color: #38bdf8; font-size: 12px; cursor: pointer; }
    </style>
</head>
<body>
    <h1>Gateway Admin Dashboard</h1>
    <div class="grid" id="dashboard"></div>
    <div class="card">
        <h2>Recent Route Decisions <span class="refresh" onclick="load()">Refresh</span></h2>
        <table id="decisions"><thead><tr><th>Time</th><th>Target</th><th>Reason</th><th>User</th><th>Latency</th><th>Detail</th></tr></thead><tbody></tbody></table>
    </div>
    <script>
        async function load() {
            const resp = await fetch('/admin/routes');
            const data = await resp.json();
            document.getElementById('dashboard').innerHTML = `
                <div class="card">
                    <h2>Health</h2>
                    <div class="metric"><span class="metric-label">Status</span><span class="metric-value ${data.health.is_healthy ? 'good' : 'bad'}">${data.health.is_healthy ? 'Healthy' : 'Unhealthy'}</span></div>
                    <div class="metric"><span class="metric-label">Success Rate</span><span class="metric-value">${data.health.success_rate}%</span></div>
                    <div class="metric"><span class="metric-label">P50 Latency</span><span class="metric-value">${data.health.p50_latency_ms}ms</span></div>
                    <div class="metric"><span class="metric-label">P99 Latency</span><span class="metric-value ${data.health.p99_latency_ms > 800 ? 'bad' : 'good'}">${data.health.p99_latency_ms}ms</span></div>
                    <div class="metric"><span class="metric-label">GPU Memory</span><span class="metric-value ${data.health.gpu_memory_pct > 95 ? 'bad' : 'good'}">${data.health.gpu_memory_pct}%</span></div>
                    <div class="metric"><span class="metric-label">CPU</span><span class="metric-value">${data.health.cpu_pct}%</span></div>
                    <div class="metric"><span class="metric-label">GPU Util</span><span class="metric-value">${data.health.gpu_pct}%</span></div>
                    <div class="metric"><span class="metric-label">Consecutive 5xx</span><span class="metric-value ${data.health.consecutive_5xx >= 3 ? 'bad' : 'good'}">${data.health.consecutive_5xx}</span></div>
                </div>
                <div class="card">
                    <h2>Degradation</h2>
                    <div class="metric"><span class="metric-label">Status</span><span class="metric-value ${data.degradation.is_degraded ? 'bad' : 'good'}">${data.degradation.is_degraded ? 'DEGRADED' : 'Normal'}</span></div>
                    <div class="metric"><span class="metric-label">Reason</span><span class="metric-value">${data.degradation.last_decision.reason}</span></div>
                    <div class="metric"><span class="metric-label">Detail</span><span class="metric-value">${data.degradation.last_decision.detail}</span></div>
                </div>
                <div class="card">
                    <h2>Cost</h2>
                    <div class="metric"><span class="metric-label">Monthly Total</span><span class="metric-value">$${data.cost.total_monthly_cost}</span></div>
                    ${data.cost.users.map(u => `<div class="metric"><span class="metric-label">${u.user_id}</span><span class="metric-value ${u.over_budget ? 'bad' : 'good'}">$${u.monthly_cost_usd} (${u.total_tokens} tokens)</span></div>`).join('')}
                </div>
                <div class="card">
                    <h2>Switch Stats</h2>
                    <div class="metric"><span class="metric-label">Total Switches</span><span class="metric-value">${data.switch_stats.switch_count}</span></div>
                    <div class="metric"><span class="metric-label">Failures</span><span class="metric-value ${data.switch_stats.switch_failure_rate > 1 ? 'bad' : 'good'}">${data.switch_stats.switch_failure_count}</span></div>
                    <div class="metric"><span class="metric-label">Failure Rate</span><span class="metric-value ${data.switch_stats.switch_failure_rate > 1 ? 'bad' : 'good'}">${data.switch_stats.switch_failure_rate}%</span></div>
                </div>
            `;
            const tbody = document.querySelector('#decisions tbody');
            tbody.innerHTML = data.recent_decisions.map(d => `
                <tr>
                    <td>${new Date(d.timestamp * 1000).toLocaleTimeString()}</td>
                    <td><span class="badge ${d.target.includes('local') ? 'badge-local' : 'badge-cloud'}">${d.target}</span></td>
                    <td>${d.reason}</td>
                    <td>${d.user_id || '-'}</td>
                    <td>${d.switch_latency_ms}ms</td>
                    <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${d.detail}</td>
                </tr>
            `).join('');
        }
        load();
        setInterval(load, 5000);
    </script>
</body>
</html>
""")


@router.get("/routes/health")
async def admin_health_detail():
    health = get_health_checker()
    degradation = get_degradation_trigger()
    degradation.evaluate(health.stats)

    return JSONResponse({
        "endpoint": health.endpoint,
        "is_healthy": health.is_healthy(),
        "stats": {
            "success_rate": round(health.stats.success_rate * 100, 1),
            "p50_latency_ms": round(health.stats.p50_latency_ms, 2),
            "p99_latency_ms": round(health.stats.p99_latency_ms, 2),
            "avg_queue_depth": round(health.stats.avg_queue_depth, 1),
            "gpu_memory_pct": round(health.stats.latest_gpu_memory_pct, 1),
            "cpu_pct": round(health.stats.latest_cpu_pct, 1),
            "gpu_pct": round(health.stats.latest_gpu_pct, 1),
            "consecutive_5xx": health.stats.consecutive_5xx,
            "snapshot_count": len(health.stats.snapshots),
        },
        "degradation": {
            "is_degraded": degradation.is_degraded,
            "reason": degradation.last_decision.reason.value,
            "detail": degradation.last_decision.detail,
        },
    })


@router.get("/routes/cost")
async def admin_cost_detail(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
):
    cost_tracker = get_cost_tracker()

    if user_id:
        user_cost = cost_tracker.get_user_cost(user_id)
        if user_cost is None:
            return JSONResponse({"error": f"User {user_id} not found"}, status_code=404)
        return JSONResponse({
            "user_id": user_id,
            "monthly_cost_usd": round(user_cost.monthly_cost_usd, 4),
            "total_tokens": user_cost.total_tokens,
            "over_budget": cost_tracker.is_over_budget(user_id),
            "recent_records": [
                {
                    "model": r.model,
                    "prompt_tokens": r.prompt_tokens,
                    "completion_tokens": r.completion_tokens,
                    "cost_usd": round(r.cost_usd, 6),
                    "timestamp": r.timestamp,
                }
                for r in user_cost.records[-20:]
            ],
        })

    return JSONResponse({
        "total_monthly_cost": round(cost_tracker.get_monthly_total(), 4),
        "users": [
            {
                "user_id": uid,
                "monthly_cost_usd": round(uc.monthly_cost_usd, 4),
                "total_tokens": uc.total_tokens,
                "over_budget": cost_tracker.is_over_budget(uid),
            }
            for uid, uc in cost_tracker.get_all_costs().items()
        ],
    })


@router.post("/routes/vip/{user_id}")
async def admin_add_vip(user_id: str):
    engine = get_router_engine()
    engine.add_vip_user(user_id)
    return JSONResponse({"status": "ok", "user_id": user_id, "is_vip": True})


@router.delete("/routes/vip/{user_id}")
async def admin_remove_vip(user_id: str):
    engine = get_router_engine()
    engine.remove_vip_user(user_id)
    return JSONResponse({"status": "ok", "user_id": user_id, "is_vip": False})


@router.post("/routes/degrade")
async def admin_force_degrade():
    degradation = get_degradation_trigger()
    degradation.force_degrade("admin manual trigger")
    return JSONResponse({"status": "ok", "degraded": True})


@router.post("/routes/recover")
async def admin_force_recover():
    degradation = get_degradation_trigger()
    degradation.force_recover()
    return JSONResponse({"status": "ok", "degraded": False})


@router.get("/routes/metrics")
async def admin_metrics():
    metrics = get_metrics()
    return JSONResponse({
        "prometheus_enabled": metrics._enabled,
        "metrics_text": metrics.get_metrics_text() if metrics._enabled else "disabled",
    })
