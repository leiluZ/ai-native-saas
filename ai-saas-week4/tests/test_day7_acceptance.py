#!/usr/bin/env python3
"""Day 7 验收测试 - 容器化部署与可观测性"""

import json
import subprocess
import sys
import time
import urllib.request
import urllib.error
from typing import Any


class AcceptanceTest:
    def __init__(self):
        self.results: list[dict[str, Any]] = []
        self.gateway_url = "http://localhost:8080"
        self.prometheus_url = "http://localhost:9090"
        self.grafana_url = "http://localhost:3000"
        self.alertmanager_url = "http://localhost:9093"

    def _request(self, url: str, method: str = "GET", data: bytes | None = None, timeout: int = 10) -> tuple[int, bytes]:
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Accept", "application/json")
        req.add_header("User-Agent", "Day7-Acceptance-Test/1.0")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
        except urllib.error.URLError as e:
            return -1, str(e).encode()

    def _pass(self, name: str, detail: str = ""):
        self.results.append({"name": name, "status": "PASS", "detail": detail})
        print(f"  [PASS] {name}")

    def _fail(self, name: str, detail: str = ""):
        self.results.append({"name": name, "status": "FAIL", "detail": detail})
        print(f"  [FAIL] {name}: {detail}")

    def _warn(self, name: str, detail: str = ""):
        self.results.append({"name": name, "status": "WARN", "detail": detail})
        print(f"  [WARN] {name}: {detail}")

    def test_healthz(self):
        print("\n--- 1. /healthz endpoint ---")
        status, body = self._request(f"{self.gateway_url}/healthz")
        if status == 200:
            self._pass("GET /healthz returns 200", body.decode().strip())
        else:
            self._fail("GET /healthz returns 200", f"got status {status}, body: {body.decode()[:200]}")

    def test_metrics_endpoint(self):
        print("\n--- 2. /metrics endpoint ---")
        status, body = self._request(f"{self.gateway_url}/metrics")
        if status == 200:
            body_str = body.decode()
            required_metrics = [
                "gateway_requests_total",
                "gateway_request_latency_seconds",
                "gateway_errors_total",
                "gateway_queue_depth",
                "gateway_vram_usage_mb",
                "gateway_cache_hit_rate",
            ]
            missing = [m for m in required_metrics if m not in body_str]
            if not missing:
                self._pass("GET /metrics returns all required Prometheus metrics")
            else:
                self._fail("GET /metrics missing metrics", f"missing: {', '.join(missing)}")
        else:
            self._fail("GET /metrics returns 200", f"got status {status}")

    def test_health_detail(self):
        print("\n--- 3. /health endpoint ---")
        status, body = self._request(f"{self.gateway_url}/health")
        if status == 200:
            try:
                data = json.loads(body)
                if "gateway" in data and data.get("gateway") == "running":
                    self._pass("GET /health returns gateway running status", json.dumps(data, indent=2))
                else:
                    self._fail("GET /health gateway not running", json.dumps(data))
            except json.JSONDecodeError as e:
                self._fail("GET /health returns valid JSON", str(e))
        else:
            self._fail("GET /health returns 200", f"got status {status}")

    def test_prometheus_up(self):
        print("\n--- 4. Prometheus scraping ---")
        max_wait = 60
        interval = 2
        waited = 0
        while waited < max_wait:
            try:
                status, body = self._request(f"{self.prometheus_url}/api/v1/query?query=up", timeout=5)
                if status == 200:
                    data = json.loads(body)
                    if data.get("status") == "success" and data["data"]["result"]:
                        targets_up = [r["metric"].get("job", "unknown") for r in data["data"]["result"] if r["value"][1] == "1"]
                        if targets_up:
                            self._pass("Prometheus scraping targets", f"up targets: {targets_up}")
                            return
                print(f"    Waiting for Prometheus scrape... ({waited}s)")
            except Exception:
                pass
            time.sleep(interval)
            waited += interval
        self._fail("Prometheus scraping", "no targets up after 60s")

    def test_grafana_up(self):
        print("\n--- 5. Grafana accessibility ---")
        max_wait = 30
        interval = 2
        waited = 0
        while waited < max_wait:
            try:
                status, _ = self._request(f"{self.grafana_url}/api/health", timeout=5)
                if status == 200:
                    self._pass("Grafana API health check")
                    return
                print(f"    Waiting for Grafana... ({waited}s)")
            except Exception:
                pass
            time.sleep(interval)
            waited += interval
        self._fail("Grafana API health check", f"not accessible after {max_wait}s")

    def test_grafana_dashboard(self):
        print("\n--- 6. Grafana dashboard provisioned ---")
        status, body = self._request(f"{self.grafana_url}/api/search?query=AI%20Gateway", timeout=10)
        if status == 200:
            try:
                data = json.loads(body)
                if data:
                    dashboard_titles = [d["title"] for d in data]
                    self._pass("Grafana dashboard found", f"Dashboards: {dashboard_titles}")
                else:
                    self._fail("Grafana dashboard provisioned", "no dashboards found")
            except json.JSONDecodeError as e:
                self._fail("Grafana dashboard API returns JSON", str(e))
        else:
            self._fail("Grafana dashboard API accessible", f"got status {status}")

    def test_alertmanager_up(self):
        print("\n--- 7. Alertmanager accessibility ---")
        max_wait = 30
        interval = 2
        waited = 0
        while waited < max_wait:
            try:
                status, body = self._request(f"{self.alertmanager_url}/api/v2/status", timeout=5)
                if status == 200:
                    self._pass("Alertmanager API accessible")
                    return
                print(f"    Waiting for Alertmanager... ({waited}s)")
            except Exception:
                pass
            time.sleep(interval)
            waited += interval
        self._fail("Alertmanager API accessible", f"not accessible after {max_wait}s")

    def test_prometheus_alerts(self):
        print("\n--- 8. Prometheus alerts configured ---")
        status, body = self._request(f"{self.prometheus_url}/api/v1/rules", timeout=10)
        if status == 200:
            try:
                data = json.loads(body)
                if data.get("status") == "success":
                    groups = data["data"]["groups"]
                    alert_count = sum(len(g.get("rules", [])) for g in groups)
                    if alert_count > 0:
                        alert_names = [r.get("name", "unknown") for g in groups for r in g.get("rules", [])]
                        self._pass("Prometheus alert rules loaded", f"{alert_count} rules: {alert_names}")
                    else:
                        self._fail("Prometheus alert rules loaded", "no rules found")
                else:
                    self._fail("Prometheus rules API", str(data))
            except json.JSONDecodeError as e:
                self._fail("Prometheus rules API JSON", str(e))
        else:
            self._fail("Prometheus rules API accessible", f"got status {status}")

    def test_simulated_fault(self):
        print("\n--- 9. Fault simulation (requests to /metrics) ---")
        for i in range(10):
            status, _ = self._request(f"{self.gateway_url}/metrics")
            time.sleep(0.5)
        time.sleep(5)

        status, body = self._request(
            f"{self.prometheus_url}/api/v1/query?query=rate(gateway_requests_total[1m])", timeout=10
        )
        if status == 200:
            data = json.loads(body)
            if data.get("status") == "success" and data["data"]["result"]:
                self._pass("Gateway request metrics recorded after traffic generation")
            else:
                self._warn("Gateway request metrics after traffic", "no results yet, may need more time")
        else:
            self._warn("Gateway request metrics query", f"status {status}")

    def run_all(self):
        print("=" * 60)
        print("Day 7 Acceptance Tests - Containerization & Observability")
        print("=" * 60)

        self.test_healthz()
        self.test_metrics_endpoint()
        self.test_health_detail()
        self.test_prometheus_up()
        self.test_grafana_up()
        self.test_grafana_dashboard()
        self.test_alertmanager_up()
        self.test_prometheus_alerts()
        self.test_simulated_fault()

        print("\n" + "=" * 60)
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        warned = sum(1 for r in self.results if r["status"] == "WARN")
        total = len(self.results)

        print(f"\nResults: {passed} passed, {failed} failed, {warned} warnings (of {total} total)")

        if failed == 0:
            print("\n[SUCCESS] All acceptance tests passed!")
            return 0
        else:
            print(f"\n[FAILURE] {failed} test(s) failed!")
            return 1


if __name__ == "__main__":
    sys.exit(AcceptanceTest().run_all())
