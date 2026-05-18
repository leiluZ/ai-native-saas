# Week 9: CI/CD 流水线与生产监控

## 🎯 目标
搭建自动化 CI/CD 与可观测性体系。覆盖 GitHub Actions 持续交付、Docker 多阶段构建与漏洞扫描、Prometheus/Grafana/Loki 监控栈、结构化日志与 TraceID 透传、SLO 告警、蓝绿部署与零停机回滚、Runbook 应急预案编写，最终交付可自动部署、可观测、可自愈的生产级运维体系。

---

## Day 1：GitHub Actions（Lint → Test → Build → Deploy）

- **目标**：搭建 GitHub Actions CI/CD 流水线，实现代码提交到自动部署全链路自动化。
- **实操**：
  1. 编写 `.github/workflows/ci.yml`：PR 触发 lint + type-check + pytest。
  2. 编写 `.github/workflows/cd.yml`：main 分支合并后 build docker image + push registry + deploy。
  3. 配置 Matrix Strategy：并行测试多 Python 版本（3.10/3.11/3.12）。
  4. 配置缓存加速：pip cache、docker layer cache，缩短构建时间。
  5. 集成 Code Coverage：pytest-cov 生成覆盖率报告，PR 评论展示覆盖率变化。
  6. 配置 Secrets 管理：Docker Hub / 云服务凭证通过 GitHub Secrets 注入。
- **Prompt 模板**：

```md
编写 GitHub Actions CI/CD 流水线配置，要求：

1. CI 流水线 (.github/workflows/ci.yml)：
   - 触发器：PR open/sync to main
   - Jobs：lint (ruff) → type-check (mypy) → test (pytest --cov)
   - Matrix：python-version [3.10, 3.11, 3.12]
   - 缓存：pip cache、.mypy_cache
   - 覆盖率报告：pytest-cov，PR comment 展示覆盖变化

2. CD 流水线 (.github/workflows/cd.yml)：
   - 触发器：push to main
   - Jobs：build -> push docker image -> deploy
   - Docker buildx 多架构构建（amd64/arm64）
   - Push to Docker Hub / GHCR
   - Deploy：SSH 远程执行 docker-compose pull && up -d

3. Artifacts 管理：测试报告、覆盖率 HTML、Docker 镜像 tag（git sha + latest）
4. Secrets 管理：DOCKER_USERNAME、DOCKER_TOKEN、SSH_PRIVATE_KEY 通过 GitHub Secrets 注入
5. 通知：失败时 GitHub Issue 自动创建 / Slack 通知
```

- **验收**：
  - PR 提交自动触发 lint + type-check + test
  - main 合并后自动构建镜像并部署
  - 缓存生效，构建时间降低 > 40%

## Day 2：Docker 多阶段构建 + Trivy 扫描

- **目标**：构建轻量、安全的 Docker 镜像，集成漏洞扫描确保镜像安全合规。
- **实操**：
  1. 编写多阶段 Dockerfile：Builder 阶段安装依赖与编译，Runtime 阶段仅保留运行所需文件。
  2. 镜像瘦身策略：使用 alpine/slim 基础镜像、pip --no-cache-dir、清理临时文件。
  3. 安全硬化：非 root 用户运行（USER 1000）、只读文件系统（可选）、健康检查 HEALTHCHECK。
  4. 集成 Trivy 漏洞扫描：CI 流水线中自动扫描镜像，高危漏洞阻断部署。
  5. 镜像体积优化对比：多阶段前 vs 多阶段后，目标体积减少 > 40%。
- **Prompt 模板**：

```md
编写多阶段 Dockerfile 与安全扫描配置，要求：

1. 多阶段 Dockerfile：
   # Stage 1: Builder
   FROM python:3.11-slim AS builder
   COPY requirements.txt .
   RUN pip install --user --no-cache-dir -r requirements.txt

   # Stage 2: Runtime
   FROM python:3.11-slim
   COPY --from=builder /root/.local /home/appuser/.local
   COPY --chown=appuser:appuser . /app
   USER appuser
   HEALTHCHECK --interval=30s CMD curl -f http://localhost:8000/healthz || exit 1

2. 镜像瘦身：
   - 使用 Python slim 基础镜像（alpine 按需）
   - pip --no-cache-dir，.dockerignore 排除 venv/__pycache__/.git
   - 清理 apt-get 缓存、临时文件
   - 目标体积 < 400MB（原镜像 < 1GB）

3. Trivy 扫描集成 (.github/workflows/scan.yml)：
   - aquasecurity/trivy-action@master
   - 扫描分级：CRITICAL/HIGH 阻断部署，MEDIUM 告警
   - 扫描对象：Git repo（fs mode）+ Docker image
   - 结果输出：SARIF 格式，上传至 GitHub Security tab

4. Image SBOM 生成（syft/grype），记录软件物料清单
5. 镜像优化对比报告：多阶段前后体积、层数、漏洞数
```

- **验收**：
  - 多阶段构建成功，镜像体积减少 > 40%
  - Trivy 扫描零高危漏洞，MEDIUM 漏洞有修复计划
  - 非 root 运行 + 健康检查生产标准达标

## Day 3：Prometheus + Grafana + Loki 监控栈

- **目标**：搭建生产级可观测性监控栈，实现指标、日志、追踪三合一。
- **实操**：
  1. 配置 Prometheus：`prometheus.yml` 定义抓取目标（app:8001/metrics、node_exporter、redis_exporter）。
  2. FastAPI 集成 `prometheus_fastapi_instrumentator`，暴露 QPS/延迟/错误率/请求路径指标。
  3. 配置 Grafana：导入预置 Dashboard（FastAPI / PostgreSQL / Redis / Node），自定义关键面板。
  4. 配置 Loki + Promtail：采集应用 JSON 日志，Grafana 中关联指标与日志查询。
  5. 配置 Prometheus Alerting Rules：P95 > 2s、Error Rate > 1%、Queue Depth > 500 触发告警。
- **Prompt 模板**：

```md
搭建 Prometheus + Grafana + Loki 监控栈，要求：

1. Prometheus 配置 (monitoring/prometheus.yml)：
   - scrape_configs：app (8001)、node_exporter (9100)、redis_exporter (9121)、postgres_exporter (9187)
   - scrape_interval: 15s，evaluation_interval: 15s
   - alerting：Alertmanager 集成

2. FastAPI 指标暴露：
   - prometheus_fastapi_instrumentator 自动埋点
   - 自定义指标：active_connections、queue_depth、model_inference_latency
   - /metrics 端点（独立端口 8001）

3. Grafana 配置 (monitoring/grafana/)：
   - 预置 Dashboard JSON（导入即用）
   - 面板：QPS / P50-P95-P99 Latency / Error Rate / CPU-MEM / DB Pool / Redis Hit Rate
   - Loki 数据源关联：Dashboard 内点击 drill-down 至对应日志

4. Loki + Promtail 日志采集：
   - Promtail 采集 /var/log/app/*.json
   - Loki 存储日志，Grafana Explore 查询
   - 保留策略：7 天热数据 + 30 天冷存储

5. Alerting Rules (monitoring/rules.yml)：
   - P95 > 2s（持续 5min）→ Warning
   - ErrorRate > 1%（持续 3min）→ Critical
   - QueueDepth > 500（持续 5min）→ Warning
   - InstanceDown → Critical
```

- **验收**：
  - Prometheus 抓取正常，所有 target UP
  - Grafana Dashboard 实时刷新，关键面板数据正确
  - Loki 日志可查询，指标与日志关联 drill-down 成功

## Day 4：结构化 JSON 日志 + TraceID 透传

- **目标**：实现结构化日志与分布式追踪，保障请求全链路可观测。
- **实操**：
  1. 配置 Python `structlog` 或 `python-json-logger`，输出 JSON 格式日志。
  2. 实现 TraceID 中间件：请求入口生成或从 Header `X-Trace-ID` 继承，透传至所有下游调用。
  3. 日志上下文注入：每个日志条目自动包含 TraceID、UserID、RequestPath、Latency。
  4. 配置日志级别动态调整：通过环境变量 `LOG_LEVEL` 或 admin API 热切换。
  5. 敏感信息脱敏：日志中自动过滤 Token、Password、API Key 等字段。
- **Prompt 模板**：

```md
实现结构化日志与 TraceID 透传系统，要求：

1. 结构化日志配置 (utils/logger.py)：
   - 使用 structlog，输出 JSON 格式
   - 字段：timestamp、level、logger、trace_id、user_id、path、method、latency、message
   - 日志级别：DEBUG/INFO/WARNING/ERROR/CRITICAL，环境变量 LOG_LEVEL 控制

2. TraceID 中间件 (middleware/trace_id.py)：
   - 请求入口：检查 X-Trace-ID Header，存在则继承，不存在则生成 UUID4
   - 全局注入：contextvars 绑定 TraceID，全链路可访问
   - 透传机制：httpx/redis/asyncpg 调用时自动携带 X-Trace-ID

3. 日志上下文绑定：
   - 每个请求自动记录：TraceID + UserID + RequestPath + Method + StatusCode + Latency
   - 中间件自动计算请求耗时，写入 access_log

4. 敏感数据脱敏：
   - 自动过滤字段：password、token、api_key、secret、authorization
   - 替换为 [REDACTED]，保留字段名用于调试

5. 日志级别热切换：
   - PUT /admin/log-level?level=DEBUG 动态调整
   - 单用户/单路径可设置 DEBUG，不影响全局
```

- **验收**：
  - 日志 JSON 格式输出，TraceID 全链路透传
  - 单条日志可追溯完整请求链路（API → DB → Redis → LLM）
  - 敏感字段脱敏生效，日志级别可动态调整

## Day 5：SLO 定义与 PagerDuty/钉钉告警

- **目标**：建立服务等级目标（SLO）体系，配置分级告警与值班通知。
- **实操**：
  1. 定义核心 SLO：可用性 99.9%、P95 < 500ms（非流式）/ P95 < 3s（流式）、错误率 < 0.1%。
  2. 配置 SLI 指标采集：Prometheus Recording Rules 计算 1h/24h/30d 滚动窗口 SLO 达成率。
  3. 配置 Alertmanager：分级路由（Critical → PagerDuty/电话、Warning → 钉钉/企微群）。
  4. 实现告警抑制规则：同一告警 10min 内不重复发送、维护窗口静默。
  5. 配置 Error Budget 燃尽图表：Grafana 面板展示月度错误预算消耗率。
- **Prompt 模板**：

```md
实现 SLO 定义与分级告警系统，要求：

1. SLO 定义 (monitoring/slo.yaml)：
   - 可用性 (Uptime)：≥ 99.9%（月度，含计划维护窗口）
   - P95 Latency：< 500ms（非流式）/ < 3s（流式）
   - Error Rate：< 0.1%（5xx / total）
   - Error Budget：月度允许不可用时间 < 43min

2. SLI 采集 (Prometheus Recording Rules)：
   - 1h / 24h / 30d 滚动窗口计算 SLI
   - 燃尽率监控：error_budget_burn_rate > 5（1h 窗口）→ Warning

3. Alertmanager 配置 (monitoring/alertmanager.yml)：
   - 路由分级：
     - Critical（响应 15min）：PagerDuty Service + 电话 + 钉钉 @all
     - Warning（响应 1h）：钉钉群 + 企微群
     - Info：仅记录，不通知
   - 抑制规则：同一 alertname + instance，10min 内仅发 1 次
   - 静默窗口：计划维护时手动设置 silence

4. Grafana Error Budget 面板：
   - 月度 Error Budget 剩余量（进度条）
   - 燃尽速率（线图，标注 over-budget 红线）
   - 告警事件时间线（Annotations）

5. 告警模板：标题 + 摘要 + 详情 + Runbook 链接 + 操作按钮（ACK/Silence）
```

- **验收**：
  - SLO 指标采集准确，Prometheus Recording Rules 计算正确
  - Alertmanager 分级路由生效，Critical 15min 内通知到位
  - Error Budget 面板燃尽曲线可见

## Day 6：蓝绿部署/滚动更新 + 零停机回滚

- **目标**：实现零停机部署与快速回滚机制，保障发布安全。
- **实操**：
  1. 配置 docker-compose 蓝绿部署：两组容器（blue/green），Nginx upstream 指向 active 组。
  2. 实现切换脚本：健康检查通过后，更新 Nginx upstream → reload，零流量中断。
  3. 实现回滚脚本：保留上一版本镜像 tag，一键切回旧版本 upstream。
  4. 配置预热策略：新版本启动后预热 30s（发送探活请求），确认响应正常再切流。
  5. 实现灰度发布：按 IP/UserID 哈希逐步放量（10% → 50% → 100%）。
- **Prompt 模板**：

```md
实现蓝绿部署与零停机回滚方案，要求：

1. 蓝绿部署配置 (deploy/blue-green/)：
   - docker-compose.blue.yml / docker-compose.green.yml 两组配置
   - Nginx upstream 动态指向 active 组
   - 部署脚本 deploy.sh：
     1) docker-compose -f green.yml up -d（新版本）
     2) 健康检查等待（curl /healthz 连续 3 次 200）
     3) 更新 Nginx upstream → GREEN → nginx -s reload
     4) 旧版本保持 5min 热备，确认无异常后 docker-compose -f blue.yml down

2. 回滚脚本 rollback.sh：
   - 切换 Nginx upstream 回上一版本 → nginx -s reload
   - 无需重建容器，秒级完成
   - 保留最近 3 个版本镜像

3. 预热策略：
   - 新版本启动后，脚本自动发送 20 个探活请求（覆盖 /healthz + /api/v1/chat）
   - 确认 P95 < 目标值，无 5xx，再切流

4. 灰度发布（可选）：
   - Nginx split_clients 按 IP hash 分流：
     split_clients "${remote_addr}AAA" $variant {
       10%  green;
       *    blue;
     }
   - 逐步调整比例：10% → 50% → 100%，每步观察 15min

5. 发布日志：记录切流时间、版本、操作人，支持审计
```

- **验收**：
  - 蓝绿切换零流量中断，客户端无感知
  - 回滚操作秒级完成，旧版本服务正常
  - 预热检测拦截异常版本上线

## Day 7：Runbook 编写（故障排查/应急预案）

- **目标**：编写标准化运维 Runbook，覆盖常见故障排查与应急响应流程。
- **实操**：
  1. 编写故障排查 Runbook：常见故障（502/高延迟/内存泄漏/DB 连接池耗尽）的诊断步骤。
  2. 编写应急预案：P0（全站宕机）/P1（核心功能不可用）/P2（部分功能降级）的响应流程。
  3. 编写升级标准（Escalation Policy）：P0 15min 内升级、P1 30min 内升级。
  4. 编写 Postmortem 模板：故障时间线、根因分析、修复措施、预防改进。
  5. 编写值班手册：日常巡检清单、监控面板链接、关键命令速查表。
- **Prompt 模板**：

```md
编写生产运维 Runbook 与应急预案，要求：

1. Runbook 结构 (docs/runbook/)：
   - runbook-502.md：502 Bad Gateway 排查（Nginx log → app log → health check → resource）
   - runbook-high-latency.md：P95 飙升排查（慢查询 → 队列积压 → GC → OOM）
   - runbook-db-pool.md：DB 连接池耗尽（pool stats → active queries → kill → 扩容）
   - runbook-oom.md：OOM 应急（降级开关 → 限流 → 扩容 → 重启）

   每条 Runbook 格式：
   - Symptom（表象）：用户反馈/告警触发
   - Diagnosis（诊断）：
     1) Grafana Dashboard 检查 → 定位异常指标
     2) Loki 日志查询 → `{app="api"} |= "ERROR"` 定位错误
     3) 服务器 SSH → htop / nvidia-smi / docker stats
   - Resolution（解决）：Step-by-step 命令
   - Verification（验证）：如何确认已修复

2. 应急预案 (docs/incident-response.md)：
   - P0（全站宕机）：5min 响应 → 15min 升级 → 30min 恢复或切备
   - P1（核心功能不可用）：15min 响应 → 30min 升级
   - P2（部分降级）：1h 响应 → 记录 → 下次修复
   - 响应角色：Incident Commander、Ops Lead、Comms Lead

3. Postmortem 模板 (docs/postmortem-template.md)：
   - 故障时间线（UTC）
   - 根因分析（5 Whys）
   - 影响范围（用户数、持续时间、数据丢失量）
   - 修复措施与预防改进（Action Items + Owner + Deadline）

4. 值班手册 (docs/on-call-guide.md)：
   - 日常巡检：Grafana Dashboard 截图 + 资源水位 + Error Budget 检查
   - 告警处理流程：接收 → ACK → 诊断 → 修复/升级 → 关闭
   - 常用命令速查：SSH、docker logs、kubectl、redis-cli、psql
```

- **验收**：
  - Runbook 覆盖 ≥ 5 类常见故障
  - 应急预案 P0/P1/P2 分级清晰，升级标准明确
  - Postmortem 模板完整，值班手册实操可用

---

## 每日验收标准

| Day | 验收条件 |
|-----|---------|
| D1 | CI 流水线（lint/test）PR 自动触发；CD 流水线 main 合并自动部署；缓存生效 |
| D2 | 多阶段镜像体积减少 > 40%；Trivy 零 CRITICAL/HIGH；非 root + 健康检查合规 |
| D3 | Prometheus 所有 target UP；Grafana Dashboard 实时刷新；Loki 日志可查 |
| D4 | JSON 日志输出；TraceID 全链路透传；敏感字段脱敏；日志级别可热切换 |
| D5 | SLO 指标采集正确；Alertmanager 分级路由生效；Error Budget 面板可见 |
| D6 | 蓝绿切换零中断；回滚秒级完成；预热检测拦截异常版本 |
| D7 | Runbook ≥ 5 类故障；应急预案分级清晰；Postmortem 模板 + 值班手册完整 |

## 最终验收标准

- PR 合并自动 Lint → Test → Build → Deploy，CI/CD 流水线完整运行
- Docker 多阶段镜像零高危漏洞，体积优化 > 40%，非 root 运行合规
- Prometheus + Grafana + Loki 监控栈实时可观测，QPS/延迟/错误率面板正确
- 结构化 JSON 日志 + TraceID 全链路透传，分布式追踪完整
- SLO 定义清晰，Alertmanager 分级告警生效，Critical 15min 内通知
- 蓝绿部署零停机，回滚秒级完成，灰度发布可控
- Runbook + 应急预案 + Postmortem 体系完整

## 高频 Prompt 模板

1. **GitHub Actions CI/CD 流水线 Prompt**
   - CI：PR 触发 lint/test/coverage Matrix
   - CD：main merge 触发 build/push/deploy
   - Secrets 管理 + 缓存加速 + 通知集成

2. **Docker 多阶段构建与 Trivy 扫描 Prompt**
   - 多阶段 Dockerfile（Builder → Runtime）
   - 镜像瘦身 + 安全硬化（非 root/HEALTHCHECK）
   - Trivy + SBOM + 漏洞阻断策略

3. **Prometheus + Grafana + Loki 监控栈 Prompt**
   - Prometheus scrape + FastAPI 指标暴露
   - Grafana Dashboard 预置面板
   - Loki + Promtail 日志采集 + 关联查询

4. **结构化日志与 TraceID 透传 Prompt**
   - structlog JSON 输出 + TraceID 中间件
   - TraceID 全链路注入（httpx/redis/asyncpg）
   - 敏感字段脱敏 + 日志级别热切换

5. **SLO 定义与分级告警 Prompt**
   - SLO（可用性/延迟/错误率）+ Error Budget
   - Prometheus Recording Rules SLI 计算
   - Alertmanager 分级路由（PagerDuty/钉钉）

6. **蓝绿部署与零停机回滚 Prompt**
   - docker-compose 蓝绿 + Nginx upstream 动态切换
   - 预热检测（health check + 探活请求）
   - 灰度发布（split_clients） + 秒级回滚

7. **Runbook 与应急预案 Prompt**
   - 故障排查 Runbook（502/延迟/DB/OOM）
   - 应急响应（P0/P1/P2 升级标准）
   - Postmortem 模板 + 值班手册

## 动态调整建议

- **无 CI/CD 经验**：Day 1 先跑通 GitHub Actions 基础（lint + test），逐步添加 Docker build + deploy。
- **已有监控体系**：Day 3 Graphana 导入社区 Dashboard 即可，聚焦自定义指标与 Loki 日志关联。
- **单机部署场景**：Day 6 蓝绿部署简化为 docker-compose + Nginx upstream 切换，不涉及 K8s。
- **团队规模小（< 5 人）**：Day 5 告警可简化至钉钉/企微单通道，Day 7 Runbook 聚焦前 3 类高频故障。
- **安全合规要求高**：Day 2 Trivy 扫描 + SBOM 为重点，Day 4 日志脱敏与保留策略需对齐合规。

## 第 7 天自测清单

- [ ] GitHub Actions CI/CD 流水线完整运行（lint → test → build → deploy）
- [ ] Docker 镜像体积优化 > 40%，Trivy 零高危漏洞，非 root + 健康检查合规
- [ ] Prometheus 抓取正常，Grafana Dashboard 实时刷新，Loki 日志可查询
- [ ] JSON 日志输出 + TraceID 全链路透传 + 敏感字段脱敏 + 日志级别可调
- [ ] SLO 指标采集正确，Alertmanager 分级告警生效，Error Budget 面板可见
- [ ] 蓝绿切换零中断，回滚秒级完成，预热检测拦截异常版本
- [ ] Runbook ≥ 5 类故障，应急预案 P0/P1/P2 分级，Postmortem 模板完整
- [ ] 仓库包含：CI/CD 配置、Dockerfile、监控配置、日志中间件、告警规则、部署脚本、Runbook
- [ ] 能清晰口述 CI/CD 流程、容器化最佳实践、可观测性三支柱与发布回滚策略
