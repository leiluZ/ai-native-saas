# Week 7: 高并发与流式架构优化

## 🎯 目标
优化高并发流式架构，实现连接池、降级策略与压测验证。

## 🛠️ 每日实操
- D1: FastAPI 异步深度优化 (asyncpg/redis 连接池)
- D2: SSE/WebSocket 生产化 (心跳/重连/保序)
- D3: Celery/RQ 解耦长耗时任务
- D4: Redis 滑动窗口限流 + IP 封禁
- D5: k6/Locust 压测 (500 VU) + 瓶颈定位
- D6: 降级与熔断 (OOM 自动降级至缓存/轻量模型)
- D7: Uvicorn/Gunicorn/Nginx 生产配置

## ✅ 验收标准
- 500 并发 P95 <2s，错误率 <1%
- 断线重连 <3s 无丢消息
- 限流/熔断全链路生效
