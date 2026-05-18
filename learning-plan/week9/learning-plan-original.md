# Week 9: CI/CD 流水线与生产监控

## 🎯 目标
搭建自动化 CI/CD 与可观测性体系。掌握从代码提交到自动部署、镜像安全加固、指标/日志/链路追踪采集、SLO 告警路由、零停机发布与标准化 Runbook 的全流程，交付高可靠、可观测、易运维的生产级 AI 服务。

---

## Day 1：GitHub Actions（Lint → Test → Build → Deploy）

- **目标**：建立标准化 CI/CD 流水线，实现 PR 合并后自动构建、测试与部署至测试环境。
- **实操**：
  1. 编写 `.github/workflows/ci.yml`：PR 触发 lint（ruff）+ type-check（mypy）+ test（pytest --cov）。
  2. 编写 `.github/workflows/cd.yml`：main 合并后 build docker image + push registry + deploy staging。
  3. 配置 Matrix Strategy：并行测试多 Python 版本（3.10/3.11/3.12），覆盖率阈值拦截（≥ 80%）。
  4. 配置缓存加速：`actions/cache` for pip/docker layers，构建时间降低 > 40%。
  5. 失败自动通知：推送结果至企业微信/Slack/钉钉 Webhook，附 Commit ID 与失败日志链接。
  6. 配置 Secrets 管理：Docker Hub / 云服务凭证通过 GitHub Secrets 注入，禁止硬编码。
- **Prompt 模板**：

```md
编写生产级 GitHub Actions CI/CD 流水线，要求：

1. 严格四阶段：lint（ruff）→ type-check（mypy）→ test（pytest+coverage）→ build（docker）→ deploy-staging
2. Matrix：python-version [3.10, 3.11, 3.12]，并行执行
3. 缓存优化：pip cache + docker layer cache，构建耗时缩短 > 40%
4. 质量门禁：单元测试覆盖率 < 80% 阻断流水线
5. 环境隔离：staging/prod 使用独立 secrets，支持环境变量动态注入与 .env 校验
6. 失败通知：失败时自动推送 Commit 链接、错误堆栈至指定 IM 群组
7. 支持手动触发与定时触发，提供 dry-run 模式供本地调试
```

- **验收**：
  - ✅ PR 提交自动触发 lint + type-check + test
  - ✅ main 合并后自动构建镜像并部署测试环境，健康检查通过
  - ✅ 缓存生效，流水线总耗时 < 5min
  - ✅ 质量门禁生效，失败精准阻断

## Day 2：Docker 多阶段构建 + Trivy 扫描

- **目标**：构建轻量、安全的 Docker 镜像，集成漏洞扫描确保镜像安全合规。
- **实操**：
  1. 编写多阶段 Dockerfile：Builder 阶段编译/安装依赖，Runtime 阶段仅复制必要二进制与 wheels。
  2. 镜像瘦身策略：使用 `python:3.11-slim` 基础镜像、`pip --no-cache-dir`、清理 `__pycache__` 等。
  3. 安全硬化：非 root 用户运行（USER 1000）、健康检查 HEALTHCHECK、权限最小化。
  4. 集成 Trivy 漏洞扫描：CI 中自动扫描镜像，CRITICAL/HIGH 漏洞阻断推送，MEDIUM 告警。
  5. 输出镜像体积对比报告（Before vs After）+ 安全扫描结果与修复建议。
- **Prompt 模板**：

```md
构建安全轻量化 Docker 多阶段构建与 Trivy 扫描流水线，要求：

1. 多阶段设计：builder 负责依赖编译，runtime 仅保留最小运行集，使用 slim/distroless 基座
2. 安全扫描：CI 中集成 trivy image 扫描，CRITICAL/HIGH 漏洞直接阻断推送，输出 HTML/JSON 报告
3. 体积优化：合并 RUN 指令，清理 apt/yum/pip cache，.dockerignore 排除非生产文件
4. 非 root 运行：创建专用用户，设置文件权限，禁用特权模式
5. 提供镜像对比数据：体积缩减比例（目标 > 40%）、依赖数量、启动耗时
6. 支持本地一键构建与推送至私有 Harbor/ECR，自动打标（git sha + version）
```

- **验收**：
  - ✅ 镜像体积优化 > 40%，启动时间下降 > 30%
  - ✅ Trivy 扫描零 CRITICAL/HIGH 漏洞，CI 拦截生效
  - ✅ 非 root 运行，权限最小化
  - ✅ 构建过程幂等，支持本地与 CI 一致行为

## Day 3：Prometheus + Grafana + Loki 监控栈

- **目标**：搭建 PLG（Prometheus/Loki/Grafana）可观测性基础设施，实现指标与日志统一采集。
- **实操**：
  1. 配置 Prometheus：`prometheus.yml` 定义抓取目标（app:8001/metrics、node_exporter、redis_exporter）。
  2. FastAPI 集成 `prometheus_fastapi_instrumentator`，暴露 QPS/延迟/错误率/自定义指标。
  3. 配置 Grafana：导入预置 Dashboard（FastAPI/PostgreSQL/Redis/Node），自定义关键面板。
  4. 配置 Loki + Promtail：采集应用 JSON 日志，Promtail pipeline 解析 `trace_id/status_code/endpoint`。
  5. 配置 Alerting Rules：P95 > 2s、Error Rate > 1%、Queue Depth > 500 触发告警。
- **Prompt 模板**：

```md
搭建 PLG 可观测性全栈与 Grafana 自动配置，要求：

1. docker-compose 编排 prometheus + loki + promtail + grafana + node-exporter，网络隔离清晰
2. prometheus.yml 配置 scrape_configs，自动发现容器 label，采集应用 /metrics 与系统指标
3. promtail 配置 pipeline_stages 解析 JSON 日志，提取 trace_id/status_code/endpoint，推送至 loki
4. Grafana provisioning：自动创建数据源，导入官方 FastAPI/Node 仪表盘，设置默认组织与权限
5. 提供数据链路验证脚本：模拟 QPS 请求，校验 Prometheus 指标增量与 Loki 日志写入
6. 持久化配置：Prometheus TSDB、Loki chunks/indexes、Grafana dashboards 挂载 volume
```

- **验收**：
  - ✅ Prometheus 抓取正常，所有 target UP，指标延迟 < 15s
  - ✅ Grafana Dashboard 实时刷新，QPS/延迟/错误率面板数据正确
  - ✅ Loki 日志可搜索，按 trace_id/level/endpoint 过滤流畅
  - ✅ `docker-compose up` 一键拉起 PLG 全栈

## Day 4：结构化 JSON 日志 + TraceID 透传

- **目标**：实现全链路请求追踪与标准化日志输出，支撑跨服务故障快速定位。
- **实操**：
  1. 集成 `structlog` 或 `python-json-logger`，强制输出 JSON 格式日志。
  2. 编写 FastAPI 中间件：请求入口生成 `trace_id`，注入 `contextvars`，透传至下游 HTTP/gRPC 请求头（`X-Trace-Id`）。
  3. 日志字段标准化：包含 `timestamp/level/trace_id/span_id/endpoint/duration_ms/status_code/user_id`。
  4. 配置日志级别动态调整：通过环境变量 `LOG_LEVEL` 或 admin API 热切换。
  5. 敏感信息脱敏：日志中自动过滤 Token、Password、API Key 等字段，替换为 `[REDACTED]`。
  6. 配置 Loki 标签优化：仅将低基数查询字段作为 label，高基数字段存于 JSON body。
- **Prompt 模板**：

```md
实现全链路 TraceID 透传与结构化 JSON 日志中间件，要求：

1. 基于 FastAPI 中间件生成唯一 trace_id，注入 contextvars，自动附加至响应头 X-Trace-Id
2. 集成 structlog，强制 JSON 输出，字段包含 trace_id/span_id/endpoint/duration/status/user
3. 下游调用透传：aiohttp/httpx 请求自动携带 X-Trace-Id，支持异步上下文传递
4. Loki 兼容：日志流按 service/env 打标签，高基数字段存入 JSON body 避免 label 爆炸
5. 采样策略：ERROR/CRITICAL 100% 保留，INFO 按 20% 采样，DEBUG 本地开发开启
6. 敏感数据脱敏：自动过滤 password/token/api_key/secret，替换为 [REDACTED]
```

- **验收**：
  - ✅ 所有日志 JSON 结构化，零非结构化文本落盘
  - ✅ TraceID 全链路透传，跨服务/中间件无断裂
  - ✅ 单条日志可追溯完整请求链路（API → DB → Redis → LLM）
  - ✅ Loki 标签基数受控，Grafana 中 TraceID 串联日志与指标完整可查

## Day 5：SLO 定义与 PagerDuty/钉钉告警

- **目标**：建立服务等级目标（SLO）体系，配置分级告警与值班通知。
- **实操**：
  1. 定义核心 SLO：可用性 ≥ 99.9%、P99 ≤ 2s、错误率 ≤ 1%，计算 Error Budget。
  2. 编写 Prometheus Recording Rules 预聚合指标，配置 Alerting Rules 阈值触发 + `for` 防抖动窗口。
  3. 配置 Alertmanager：按服务/环境分组（`group_by`），设置抑制规则（`inhibit_rules`）、静默窗口、升级策略。
  4. 集成 Webhook：对接 PagerDuty / 钉钉机器人，支持富文本通知、告警去重、ACK 状态回传。
  5. 告警演练：模拟 SLO breach，验证通知触达 < 1min、分组聚合、防抖动与恢复通知。
- **Prompt 模板**：

```md
构建 SLO 告警规则与 Alertmanager 智能路由体系，要求：

1. 定义 3 个核心 SLO：可用性、P99 延迟、错误率，提供 Error Budget 计算 PromQL
2. 告警规则：Recording Rules 降基数，Alerting Rules 配置 threshold + for 防抖动窗口
3. Alertmanager 路由：按 env/service 分组，设置 inhibit_rules 抑制级联告警，配置 repeat_interval
4. 通知集成：钉钉/PagerDuty Webhook 对接，支持 @责任人、告警等级标识、一键 ACK 与升级
5. 防疲劳机制：告警冷却期、静默规则模板、批量压缩通知，避免告警风暴
6. 提供演练脚本：模拟指标超标，验证触达延迟 < 1min，恢复通知准确，无重复告警
```

- **验收**：
  - ✅ SLO 规则准确，Error Budget 可计算与追踪
  - ✅ 告警触发精准，防抖动与抑制规则生效
  - ✅ 钉钉/PD 通知触达 < 1min，格式清晰可操作
  - ✅ 告警风暴抑制有效，零无效/重复通知

## Day 6：蓝绿部署/滚动更新 + 零停机回滚

- **目标**：实现生产环境平滑发布与故障快速回退，保障业务连续性。
- **实操**：
  1. 配置 docker-compose 蓝绿部署：两组容器（blue/green），Nginx upstream 指向 active 组。
  2. 实现切换脚本：健康检查通过后，更新 Nginx upstream → reload，零流量中断。
  3. 实现回滚脚本：保留上一版本镜像 tag，一键切回旧版本 upstream，回切延迟 < 10s。
  4. 配置预热策略：新版本启动后预热 30s（发送探活请求），确认响应正常再切流。
  5. 实现灰度发布：按 IP/UserID 哈希逐步放量（10% → 50% → 100%）。
- **Prompt 模板**：

```md
编写零停机发布与快速回滚流水线，要求：

1. 支持蓝绿/滚动更新：通过 Nginx upstream 权重调整或 Traefik label 实现平滑流量迁移
2. 健康门控：新容器启动后执行 readiness probe（HTTP + 依赖检查），失败自动终止切换
3. 回滚机制：一键切换至上一稳定版本，流量回切延迟 < 10s，状态无损
4. 发布验证：脚本持续发送合成请求，记录切换期间 5xx/超时比例，输出发布报告
5. 版本追溯：镜像打标规范（git-sha + env + build-id），发布元数据写入审计表
6. 兼容 CI/CD：GitHub Actions 可调用，支持人工审批门禁（Production 环境）
```

- **验收**：
  - ✅ 蓝绿切换零流量中断，客户端无感知
  - ✅ 回滚操作 < 10s 完成，旧版本服务正常
  - ✅ 预热检测拦截异常版本上线
  - ✅ 发布报告完整，版本标签与审计记录可追溯

## Day 7：Runbook 编写（故障排查/应急预案）

- **目标**：编写标准化运维 Runbook，覆盖常见故障排查与应急响应流程。
- **实操**：
  1. 编制 Top 5 故障场景 Runbook：高延迟/SLO breached、OOM/高 CPU、DB/Redis 连接池耗尽、日志暴涨、安全告警。
  2. 标准化排查路径：现象识别 → Grafana/Loki 快速定位 → 关键诊断命令 → 应急止血操作 → 恢复验证。
  3. 集成自动化脚本：一键收集诊断快照（`diag-collect.sh`）、自动扩容/降级开关。
  4. 编写应急预案：P0（全站宕机）/P1（核心功能不可用）/P2（部分功能降级）的响应流程与升级标准。
  5. 编写 Postmortem 模板：故障时间线、根因分析（5 Whys）、影响范围、Action Items + Owner + Deadline。
- **Prompt 模板**：

```md
构建 SRE Runbook 与自动化应急预案体系，要求：

1. 覆盖 5 大核心场景：SLO breach、资源耗尽、依赖宕机、日志风暴、安全事件
2. 标准化排查流：现象 → 看板定位 → 诊断命令 → 止血操作 → 恢复验证，附截图与 PromQL/Loki 查询
3. 自动化脚本：diag-collect.sh 一键导出指标/日志/配置，auto-scale/auto-downgrade 开关集成 CI
4. 应急预案：P0（5min 响应）/P1（15min 响应）/P2（1h 响应），升级标准明确
5. Post-Mortem 模板：时间线、影响面、5 Whys 根因、Action Items 跟踪，支持 Jira/飞书自动创建
6. 版本管理：Markdown 结构，PR 审核发布，变更日志清晰，支持全文检索
```

- **验收**：
  - ✅ Runbook 覆盖 ≥ 5 类常见故障，排查路径清晰可执行
  - ✅ 应急预案 P0/P1/P2 分级清晰，升级标准明确
  - ✅ 诊断与应急脚本一键运行，止血操作标准化
  - ✅ Postmortem 模板完整，改进项可追踪闭环

---

## 每日验收标准

| Day | 验收条件 |
|-----|---------|
| D1 | CI（lint/test）PR 自动触发；CD main 合并自动部署；缓存生效；耗时 < 5min |
| D2 | 镜像体积优化 > 40%；Trivy 零 CRITICAL/HIGH；非 root + 健康检查合规；构建幂等 |
| D3 | PLG 栈 `docker-compose up` 一键拉起；Prometheus/Loki 抓取正常；Grafana 实时刷新 |
| D4 | 全量日志 JSON 结构化；TraceID 跨服务透传无断裂；Loki 标签基数受控；链路一键聚合 |
| D5 | SLO 规则准确；告警防抖动/抑制生效；钉钉/PD 触达 < 1min；零告警风暴 |
| D6 | 蓝绿/滚动发布零 5xx；健康门控严格；一键回滚 < 10s；发布报告与审计完整 |
| D7 | Runbook 覆盖 Top 5 场景；诊断/应急脚本可运行；Post-Mortem 模板可追踪闭环 |

## 最终验收标准

- ✅ PR 合并自动部署测试环境，流水线耗时 < 5min，质量门禁拦截准确
- ✅ 生产镜像无高危漏洞（Trivy CRITICAL/HIGH = 0），体积优化 > 40%，非 root 运行
- ✅ Grafana 实时显示 QPS/延迟/错误率，Loki 日志与 TraceID 全链路串联可查
- ✅ SLO 定义清晰，告警路由智能，触达延迟 < 1min，防疲劳机制生效
- ✅ 蓝绿/滚动发布零停机，回滚 < 10s，版本审计完整
- ✅ Runbook 标准化，Top 5 故障可一键诊断/止血，Post-Mortem 流程可闭环

## 高频 Prompt 模板

1. **GitHub Actions CI/CD 流水线 Prompt**
   - Lint/Test/Build/Deploy 四阶段门禁
   - 依赖与 Docker 层缓存优化
   - 失败自动通知与环境隔离

2. **Docker 多阶段构建与 Trivy 安全扫描 Prompt**
   - Slim/Distroless 基座与层合并
   - CRITICAL/HIGH 漏洞 CI 阻断
   - 体积对比与非 root 权限配置

3. **PLG 可观测性栈搭建 Prompt**
   - docker-compose 编排与网络隔离
   - Prometheus scrape_configs 与 Promtail pipeline
   - Grafana Provisioning 与看板自动导入

4. **TraceID 透传与结构化 JSON 日志 Prompt**
   - FastAPI 中间件生成与 contextvars 注入
   - 下游 HTTP/gRPC 自动透传
   - Loki 标签优化与采样策略

5. **SLO 定义与 Alertmanager 智能告警 Prompt**
   - Error Budget PromQL 与防抖动窗口
   - 分组/抑制/升级路由配置
   - 钉钉/PagerDuty 对接与防风暴策略

6. **零停机发布与快速回滚 Prompt**
   - Nginx/Traefik 权重切换与健康门控
   - 一键回滚 < 10s 逻辑
   - 发布验证脚本与版本审计

7. **SRE Runbook 与应急预案 Prompt**
   - Top 5 故障排查路径与诊断命令
   - 自动化止血脚本与 Post-Mortem 模板
   - 文档版本管理与 Chaos 演练指南

## 动态调整建议

- **无 K8s 环境**：
  - Day 3/6 全部基于 `docker-compose + Nginx/Traefik` 实现，逻辑与 K8s 完全等价。
- **日志量极大（TB 级/日）**：
  - Day 4 优先开启 Loki `compactor`，配置日志按天分块与过期清理，降低 INFO 采样率至 5%。
- **告警疲劳严重**：
  - Day 5 强化 `inhibit_rules` 与 `group_wait/group_interval`，合并同源告警，仅保留根因指标。
- **发布审批流程严格**：
  - Day 6 在 GitHub Actions 增加 `environment: production` 人工审批门禁。
- **团队 SRE 经验薄弱**：
  - Day 7 优先跑通"高延迟"与"OOM"两个最高频场景 Runbook，使用 Grafana Alerting 面板替代纯命令行。

## 第 7 天自测清单

- [ ] `ci-cd.yml` 一键运行，PR 合并后自动部署 Staging，零手动干预
- [ ] 生产镜像 Trivy 扫描零高危，体积缩减 > 40%，`docker run` 非 root 启动成功
- [ ] PLG 栈 `docker-compose up` 正常，Prometheus/Loki 数据流稳定，Grafana 面板实时刷新
- [ ] 所有请求日志 JSON 输出，TraceID 跨服务透传，Loki 一键聚合全链路日志
- [ ] SLO 告警规则准确，钉钉/PD 触达 < 1min，无重复/无效告警，抑制规则生效
- [ ] 蓝绿/滚动发布脚本执行，健康检查通过，流量切换零 5xx，回滚 < 10s
- [ ] Runbook 覆盖 Top 5 故障，诊断/应急脚本可运行，Post-Mortem 模板已入库
- [ ] 仓库包含：CI/CD 配置、Dockerfile、Trivy 规则、docker-compose PLG、日志中间件、告警路由、发布脚本、Runbook 文档
- [ ] 能清晰口述：CI/CD 门禁设计、镜像安全基线、PLG 数据链路、SLO/告警路由策略、零停机发布原理与 Runbook 运维闭环
