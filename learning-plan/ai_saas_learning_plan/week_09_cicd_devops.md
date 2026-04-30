# Week 9: CI/CD 流水线与生产监控

## 🎯 目标
搭建自动化 CI/CD 与可观测性体系。

## 🛠️ 每日实操
- D1: GitHub Actions (Lint->Test->Build->Deploy)
- D2: Docker 多阶段构建 + Trivy 扫描
- D3: Prometheus + Grafana + Loki 监控栈
- D4: 结构化 JSON 日志 + TraceID 透传
- D5: SLO 定义与 PagerDuty/钉钉告警
- D6: 蓝绿部署/滚动更新 + 零停机回滚
- D7: Runbook 编写 (故障排查/应急预案)

## ✅ 验收标准
- PR 合并自动部署测试环境
- 镜像无高危漏洞，体积优化 >40%
- Grafana 实时显示 QPS/延迟/错误率
