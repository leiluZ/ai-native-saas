# Week 1: AI-Native 环境初始化 & 基础 SaaS 骨架

## 🎯 目标
建立 AI 驱动的开发环境，掌握「自然语言 -> 架构 -> 代码」闭环。

## 🛠️ 每日实操
- **D1**: Cursor/Cline 配置 + `.cursorrules` + 项目树生成
- **D2**: FastAPI + SQLAlchemy 2.0 + Redis 连接池 + Alembic 迁移
- **D3**: React/Vue 骨架 + Tailwind + SSE 流式占位
- **D4**: LangChain Agent + Function Calling + 工具路由
- **D5**: 记忆管理 (PostgreSQL/Redis) + 上下文压缩
- **D6**: AI 驱动重构 + pytest 测试 (>75% 覆盖)
- **D7**: Docker Compose 一键部署 + README + Demo 录制

## 💡 核心 Prompt 示例
`你是一位资深 AI-Native 全栈架构师。输出代码必须：1. 类型提示/异步优先 2. 配置走 env 3. 附 pytest 骨架`

## ✅ 验收标准
- `/docs` 可访问，健康检查返回 200
- Agent 自动调用工具，失败有 fallback
- `docker-compose up` 一键跑通全栈
