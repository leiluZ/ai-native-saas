# AI SaaS Week1 Scaffold

A minimal monorepo scaffold for an AI SaaS starter project.

## Structure

- `app/web`: frontend app (React + TS + Tailwind)
- `app/backend`: backend service (FastAPI + PostgreSQL + Redis)
- `packages/shared`: shared types/utils
- `infra`: docker-related files
- `docs`: architecture and notes
- `scripts`: local helper scripts
- `tests`: integration/e2e placeholders

## Prerequisites

- Docker & Docker Compose
- (Optional) OpenAI API key if using OpenAI instead of Ollama

## Quick Start

1. Copy env template:

   ```bash
   cp .env.example .env
   ```

2. Start all services:

   ```bash
   docker-compose up --build
   ```

   This will automatically:

   - Start PostgreSQL, Redis, and Ollama containers
   - Ollama will check if the required model (mistral) exists, and pull it if needed

3. Access the web interface at http://localhost:3000

## LLM Configuration

By default, the application uses **Ollama** with the Mistral model running in a Docker container.

### Option A: Ollama (Default)

```env
OLLAMA_MODEL=mistral
OLLAMA_BASE_URL=http://ollama:11434
```

The docker-compose.yml includes an Ollama container that automatically checks for and pulls the configured model on startup.

### Option B: OpenAI

If you prefer using OpenAI instead of Ollama:

```env
OLLAMA_MODEL=
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL=gpt-3.5-turbo
```

**Steps to configure OpenAI:**

1. Get your API key from [OpenAI Platform](https://platform.openai.com/api-keys)
2. In `.env`, set:
   - `OLLAMA_MODEL=` (leave empty)
   - `OPENAI_API_KEY=sk-your-actual-key`
   - `OPENAI_MODEL=gpt-3.5-turbo` (or `gpt-4` if preferred)
3. Restart the backend service:
   ```bash
   docker-compose restart backend
   ```

## Environment Variables

| Variable          | Description                  | Default                                                  |
| ----------------- | ---------------------------- | -------------------------------------------------------- |
| `DATABASE_URL`    | PostgreSQL connection string | `postgresql+asyncpg://postgres:postgres@db:5432/ai_saas` |
| `REDIS_URL`       | Redis connection string      | `redis://redis:6379/0`                                   |
| `OLLAMA_MODEL`    | Ollama model name            | `mistral`                                                |
| `OLLAMA_BASE_URL` | Ollama server URL            | `http://ollama:11434`                                    |
| `OPENAI_API_KEY`  | OpenAI API key               | (empty)                                                  |
| `OPENAI_MODEL`    | OpenAI model name            | `gpt-3.5-turbo`                                          |

## Services

| Service | Port  | Description         |
| ------- | ----- | ------------------- |
| web     | 3000  | React frontend      |
| backend | 8000  | FastAPI backend     |
| db      | 5432  | PostgreSQL database |
| redis   | 6379  | Redis cache         |
| ollama  | 11434 | Ollama LLM server   |
