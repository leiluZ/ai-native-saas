# AI SaaS Week1 Scaffold

A minimal monorepo scaffold for an AI SaaS starter project.

## Structure

- `app/web`: frontend app (Vite + TS placeholder)
- `app/api`: backend service (Node + TS placeholder)
- `packages/shared`: shared types/utils
- `infra`: docker-related files
- `docs`: architecture and notes
- `scripts`: local helper scripts
- `tests`: integration/e2e placeholders

## Quick Start

1. Copy env template:
   - `cp .env.example .env`
2. Install dependencies in each package.
3. Start services with `docker-compose up --build` (after filling Dockerfiles and package scripts).
