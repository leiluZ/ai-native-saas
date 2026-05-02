#!/usr/bin/env bash
set -euo pipefail

echo "Run backend and web in separate terminals:"
echo "1) cd app/backend && pip install -e . && uvicorn app.main:app --reload"
echo "2) cd app/web && npm run dev"
