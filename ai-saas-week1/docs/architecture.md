# Architecture (Draft)

## 项目概述

本项目是一个 AI SaaS 应用，包含以下核心组件：

| 组件              | 说明                     | 技术栈               |
| ----------------- | ------------------------ | -------------------- |
| `app/api`         | Node.js 后端 API 服务    | Node.js / TypeScript |
| `app/web`         | 前端 Web 应用            | React / TypeScript   |
| `app/backend`     | FastAPI 后端服务（新增） | Python / FastAPI     |
| `packages/shared` | 通用契约和辅助类型       | TypeScript           |

---

## 目录结构

```
ai-saas-week1/
├── app/
│   ├── api/                 # Node.js API 服务
│   │   ├── src/
│   │   ├── package.json
│   │   └── tsconfig.json
│   ├── web/                 # React 前端应用
│   │   ├── src/
│   │   ├── index.html
│   │   ├── package.json
│   │   └── tsconfig.json
│   └── backend/             # FastAPI 后端服务
│       ├── src/
│       │   ├── __init__.py
│       │   ├── main.py              # FastAPI 入口，含 lifespan 管理
│       │   ├── config.py            # 配置管理（Pydantic Settings）
│       │   ├── dependencies.py      # 依赖注入（DB/Redis）
│       │   ├── exceptions/          # 全局异常处理器
│       │   │   ├── __init__.py
│       │   │   └── handlers.py      # 统一异常处理
│       │   ├── routes/              # 路由分层
│       │   │   ├── __init__.py
│       │   │   └── v1/              # API v1 版本
│       │   │       ├── __init__.py
│       │   │       ├── health.py    # 健康检查端点
│       │   │       └── chat.py      # 聊天端点
│       │   ├── schemas/             # Pydantic 模型
│       │   │   ├── __init__.py
│       │   │   ├── common.py        # 通用响应模型
│       │   │   └── chat.py          # 聊天相关模型
│       │   └── utils/               # 工具函数
│       │       └── __init__.py
│       ├── .env.example             # 环境变量示例
│       ├── Dockerfile               # Docker 配置
│       └── requirements.txt         # Python 依赖
├── packages/
│   └── shared/               # 共享类型定义
│       ├── src/
│       ├── package.json
│       └── tsconfig.json
├── docs/
│   └── architecture.md       # 架构文档
├── infra/
│   ├── Dockerfile.api
│   └── Dockerfile.web
├── scripts/
│   └── dev.sh                # 开发脚本
├── .env.example
├── .gitignore
├── README.md
└── docker-compose.yml        # 容器编排
```

---

## FastAPI 后端架构

### 核心特性

#### 1. Lifespan 管理

使用 FastAPI 0.100+ 的 lifespan 特性管理资源生命周期：

- 启动时初始化数据库连接池和 Redis 客户端
- 关闭时优雅释放资源

#### 2. 路由分层设计

```
/api/v1/
├── health/       # GET - 健康检查
└── chat/
    ├── message   # POST - 发送消息
    └── history/  # GET - 获取聊天历史
```

#### 3. 全局异常处理器

统一返回 JSON 格式错误响应：

```json
{
  "code": 500,
  "message": "Internal Server Error",
  "detail": "错误详情"
}
```

#### 4. Pydantic 模型

- `ResponseBase[T]` - 通用响应包装器
- `ChatMessageRequest` - 消息请求模型
- `ChatMessageResponse` - 消息响应模型
- `ChatHistoryResponse` - 聊天历史响应模型

#### 5. 依赖注入

- `get_db()` - 获取 SQLAlchemy 异步会话
- `get_redis()` - 获取 Redis 异步客户端

### 技术栈

| 组件     | 版本                        |
| -------- | --------------------------- |
| 框架     | FastAPI 0.110.0             |
| 数据库   | PostgreSQL + SQLAlchemy 2.0 |
| 缓存     | Redis                       |
| 异步驱动 | asyncpg, redis-py async     |
| 配置     | Pydantic Settings           |

---

## Docker 服务

`docker-compose.yml` 包含以下服务：

| 服务      | 说明                             | 端口 |
| --------- | -------------------------------- | ---- |
| `api`     | Node.js API 服务（保留作为过渡） | 4000 |
| `web`     | React 前端应用                   | 3000 |
| `backend` | **FastAPI 主后端服务**           | 8000 |
| `db`      | PostgreSQL 数据库                | 5432 |
| `redis`   | Redis 缓存                       | 6379 |

### 服务依赖关系

```
web (React) ──> backend (FastAPI) ──> db (PostgreSQL)
                                      └──> redis (缓存)

api (Node.js) ──> [逐步迁移到 backend]
```

### 架构说明

**核心设计原则**：FastAPI `backend` 作为主 API 服务，前端 `web` 通过 `REACT_APP_API_URL` 环境变量连接到 `backend`。

| 服务      | 职责                        | 技术栈               |
| --------- | --------------------------- | -------------------- |
| `web`     | 用户界面                    | React                |
| `backend` | 业务逻辑、AI 集成、数据访问 | FastAPI + SQLAlchemy |
| `db`      | 持久化存储                  | PostgreSQL           |
| `redis`   | 缓存和会话管理              | Redis                |

**迁移策略**：当前保留 `api` 服务作为过渡，新功能应优先在 `backend` 中实现，旧功能可逐步迁移。
