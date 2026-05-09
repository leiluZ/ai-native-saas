# Week 1: AI-Native 环境初始化 & 基础 SaaS 骨架

> **本周目标**: 建立 AI 驱动的开发环境，掌握「自然语言 -> 架构 -> 代码」闭环，完成一个具备工具调用与记忆管理的基础 Chat Agent。

---

## 第一部分：本周学习计划与目标

### 7 天学习路线

|   天数    | 主题                                         | 学习目标                                                                |
| :-------: | :------------------------------------------- | :---------------------------------------------------------------------- |
| **Day 1** | AI 编程环境初始化 & Vibe Coding 工作流       | 安装 Cursor/Cline，创建 `.cursorrules` 全局规则，建立 AI 辅助开发工作流 |
| **Day 2** | 异步后端骨架（FastAPI + PostgreSQL + Redis） | 跑通生产级异步 API、DB 连接池、基础路由与错误处理                       |
| **Day 3** | 前端骨架 + 流式交互占位（React + Vite）      | 前端对接后端 API，实现基础聊天 UI 与流式响应占位                        |
| **Day 4** | Agent 核心接入 + Function Calling            | 接入 LLM，实现 Tool 注册与自动路由，构建 Agent 循环                     |
| **Day 5** | 记忆管理 & Context Engineering               | 实现对话历史持久化、上下文压缩、窗口滑动策略                            |
| **Day 6** | AI 驱动重构 & 测试覆盖                       | 用 AI 自动化重构、生成测试、提升代码质量                                |
| **Day 7** | 容器化部署 & 作品集封装                      | 一键部署、编写技术文档、录制 Demo、沉淀 Prompt 库                       |

### 本周核心目标

1. **AI-Native 开发环境**: 掌握 Cursor/Cline 等 AI IDE 的高效使用，建立「Prompt -> 架构 -> 代码」的闭环工作流
2. **全栈基础架构**: 搭建 FastAPI + React + PostgreSQL + Redis 的现代化全栈骨架
3. **Agent 核心能力**: 实现工具注册、自动路由、Function Calling 与记忆管理
4. **工程化实践**: Docker 容器化、测试覆盖 >75%、代码规范与 CI 配置

---

## 第二部分：Sample Project 介绍

### 项目概述

本项目是一个**基础 Chat Agent 全栈应用**，实现了：

- 基于 FastAPI 的异步后端，支持工具调用与记忆管理
- 基于 React + Vite 的前端聊天界面
- LangChain 驱动的 Agent 核心，支持自动工具路由
- PostgreSQL + Redis 数据持久化与会话缓存
- Docker Compose 一键部署

### 系统架构

```mermaid
graph TB
    subgraph External["External"]
        User[("User")]
    end

    subgraph Frontend["Frontend - React + Vite"]
        Web[Web UI<br/>Port 3000]
    end

    subgraph Backend["Backend - FastAPI"]
        API[API Server<br/>Port 8000]
        Agent[Agent Router<br/>agent_router.py]
        LLM[LLM Client<br/>llm_client.py]
        Tools[Tool Registry<br/>tool_registry.py]
        Memory[Memory Manager<br/>memory_manager.py]
    end

    subgraph Data["Data Layer"]
        DB[(PostgreSQL<br/>Port 5432)]
        Redis[(Redis<br/>Port 6379)]
    end

    subgraph LLM_Service["LLM Service"]
        Ollama[(Ollama<br/>Port 11434)]
    end

    User --> Web
    Web --> API
    API --> Agent
    Agent --> LLM
    Agent --> Tools
    Agent --> Memory
    LLM --> Ollama
    Memory --> Redis
    API --> DB

    style User fill:#f9f,stroke:#333,stroke-width:2px
    style Frontend fill:#bbf,stroke:#333,stroke-width:2px
    style Backend fill:#bfb,stroke:#333,stroke-width:2px
    style Data fill:#fbb,stroke:#333,stroke-width:2px
    style LLM_Service fill:#ff9,stroke:#333,stroke-width:2px
```

### 技术栈

| 层级       | 技术                                               | 版本                   |
| ---------- | -------------------------------------------------- | ---------------------- |
| **前端**   | React, TypeScript, Vite, Tailwind CSS, Zustand     | React 19               |
| **后端**   | Python, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic | Python 3.12            |
| **AI/LLM** | LangChain, Ollama                                  | LangChain 0.3          |
| **数据库** | PostgreSQL, Redis                                  | PostgreSQL 16, Redis 7 |
| **部署**   | Docker, Docker Compose                             | -                      |

### 核心功能模块

#### 1. 后端基础架构

| 模块         | 功能描述                       | 关键文件              |
| ------------ | ------------------------------ | --------------------- |
| **API 服务** | FastAPI 异步 API，自动文档生成 | `src/main.py`         |
| **数据模型** | SQLAlchemy 2.0 异步 ORM        | `src/models/chat.py`  |
| **数据迁移** | Alembic 数据库版本管理         | `migrations/`         |
| **配置管理** | Pydantic Settings 环境变量     | `src/config.py`       |
| **依赖注入** | FastAPI Depends 连接池         | `src/dependencies.py` |

#### 2. Agent 核心系统

| 模块           | 功能描述                       | 关键文件                       |
| -------------- | ------------------------------ | ------------------------------ |
| **Agent 路由** | 智能路由用户请求，解析工具调用 | `src/agents/agent_router.py`   |
| **聊天 Agent** | 基础对话，多轮支持             | `src/agents/chat_agent.py`     |
| **LLM 客户端** | Ollama/OpenAI 统一封装         | `src/agents/llm_client.py`     |
| **工具注册**   | 动态工具注册与调用             | `src/agents/tool_registry.py`  |
| **记忆管理**   | 会话记忆与上下文压缩           | `src/agents/memory_manager.py` |

#### 3. 工具系统

- `get_weather` - 获取天气信息
- `get_current_time` - 获取当前时间（支持时区）
- `calculate` - 数学表达式计算

#### 4. 前端骨架

| 模块         | 功能描述         | 关键文件                           |
| ------------ | ---------------- | ---------------------------------- |
| **聊天界面** | 消息展示与输入   | `src/components/ChatContainer.tsx` |
| **消息气泡** | 用户/AI 消息样式 | `src/components/MessageBubble.tsx` |
| **状态管理** | Zustand 全局状态 | `src/store/chatStore.ts`           |

### 项目结构

```
ai-saas-week1/
├── app/
│   ├── backend/
│   │   ├── src/
│   │   │   ├── agents/           # Agent 核心模块
│   │   │   ├── exceptions/       # 异常处理
│   │   │   ├── models/           # SQLAlchemy 数据模型
│   │   │   ├── routes/v1/        # API 路由
│   │   │   ├── schemas/          # Pydantic 数据校验
│   │   │   ├── utils/            # 工具函数
│   │   │   ├── config.py         # 配置管理
│   │   │   ├── dependencies.py   # 依赖注入
│   │   │   └── main.py           # FastAPI 入口
│   │   ├── tests/                # 单元测试
│   │   ├── migrations/           # Alembic 迁移
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   └── web/
│       ├── src/
│       │   ├── components/       # React 组件
│       │   ├── store/            # Zustand 状态管理
│       │   └── types/            # TypeScript 类型
│       ├── e2e/                  # Playwright E2E 测试
│       ├── Dockerfile
│       └── package.json
│
├── infra/                        # Docker 基础设施
├── packages/shared/              # 共享类型定义
├── docker-compose.yml
└── README.md
```

### 快速开始

#### 环境要求

- Docker & Docker Compose
- Python 3.12+ (可选，本地开发)
- Node.js 20+ (可选，本地开发)

#### 启动服务

```bash
# 1. 进入项目目录
cd ai-saas-week1

# 2. 配置环境变量
cp .env.example .env

# 3. 启动所有服务
docker compose up -d

# 4. 查看服务状态
docker compose ps
```

#### 服务端口

| 服务       | 端口  | 说明           |
| ---------- | ----- | -------------- |
| Web UI     | 3000  | React 前端     |
| API        | 8000  | FastAPI 后端   |
| PostgreSQL | 5432  | 关系数据库     |
| Redis      | 6379  | 缓存与会话存储 |
| Ollama     | 11434 | 本地 LLM 服务  |

#### 本地开发

**后端开发**:

```bash
cd app/backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 运行开发服务器
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

**前端开发**:

```bash
cd app/web
npm install

# 运行开发服务器
npm run dev
```

### API 文档

启动服务后访问：

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **健康检查**: http://localhost:8000/api/v1/health/

#### 主要 API 端点

| 端点              | 方法 | 说明         |
| ----------------- | ---- | ------------ |
| `/api/v1/chat/`   | POST | 聊天对话     |
| `/api/v1/health/` | GET  | 服务健康检查 |

#### 使用示例

```bash
# 发送聊天请求
curl -X POST http://localhost:8000/api/v1/chat/ \
  -H "Content-Type: application/json" \
  -d '{
    "message": "北京天气怎么样？",
    "session_id": "session_123"
  }'

# 健康检查
curl http://localhost:8000/api/v1/health/
```

### 测试

#### 后端单元测试

```bash
cd app/backend
PYTHONPATH=. pytest tests/ -v

# 运行特定测试
PYTHONPATH=. pytest tests/test_agent_router.py -v
PYTHONPATH=. pytest tests/test_memory_manager.py -v
PYTHONPATH=. pytest tests/test_tool_registry.py -v
```

#### 前端 E2E 测试

```bash
cd app/web
npm run test:e2e

# 带 UI 的测试
npm run test:ui
```

### 验收标准

- ✅ `/docs` 可访问，健康检查返回 200
- ✅ Agent 自动调用工具，失败有 fallback
- ✅ `docker-compose up` 一键跑通全栈
- ✅ 单元测试覆盖率 >75%

---

## 第三部分：总结

### 学习目标实现情况

本项目通过构建一个完整的 Chat Agent 全栈应用，实现了 Week 1 的所有学习目标：

| 学习目标               | 实现方式                                      | 关键代码                       |
| ---------------------- | --------------------------------------------- | ------------------------------ |
| **AI-Native 开发环境** | 使用 Cursor/Cline 生成项目骨架、组件、测试    | `.cursorrules` 配置            |
| **异步后端骨架**       | FastAPI + SQLAlchemy 2.0 + Alembic + Redis    | `src/main.py`, `src/models/`   |
| **前端骨架**           | React + Vite + Tailwind + Zustand             | `app/web/src/components/`      |
| **Agent 核心**         | LangChain Agent + Function Calling + 工具路由 | `src/agents/agent_router.py`   |
| **记忆管理**           | 对话历史持久化 + 上下文压缩 + 窗口滑动        | `src/agents/memory_manager.py` |
| **容器化部署**         | Docker Compose 一键部署                       | `docker-compose.yml`           |
| **测试覆盖**           | pytest 单元测试 + Playwright E2E              | `tests/`, `e2e/`               |

### 知识重点

1. **AI-Native 开发工作流**: 掌握「自然语言描述 -> AI 生成架构 -> 人工审查 -> AI 生成代码 -> 测试验证」的闭环
2. **FastAPI 异步架构**: lifespan 管理、依赖注入、分层路由、全局异常处理
3. **LangChain Agent 设计**: 工具注册、自动路由、ReAct 循环、fallback 机制
4. **记忆管理策略**: 短期缓存（Redis）+ 长期存储（PostgreSQL）+ 上下文压缩
5. **工程化实践**: Docker 容器化、类型提示、异常边界、测试驱动

### Reference Links

- [Week 1 详细学习计划](../learning-plan/week1/learning-plan-original.md)
- [AI SaaS 全景路线图](../learning-plan/ai_saas_learning_plan/overall_learning_plan.md)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [LangChain 文档](https://python.langchain.com/)
- [SQLAlchemy 2.0 文档](https://docs.sqlalchemy.org/en/20/)
- [Alembic 文档](https://alembic.sqlalchemy.org/en/latest/)
