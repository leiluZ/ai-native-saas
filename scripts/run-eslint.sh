#!/bin/bash
set -e

cd "$(git rev-parse --show-toplevel)"

CHANGED_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep -E '^ai-saas-week\d+/app/web/src/' | head -20)

if [ -z "$CHANGED_FILES" ]; then
    echo "No frontend source files changed, skipping ESLint"
    exit 0
fi

WEEK_DIR=$(echo "$CHANGED_FILES" | head -1 | sed -E 's|(ai-saas-week[0-9]+)/.*|\1|')
WEB_DIR="$WEEK_DIR/app/web"

if [ -d "$WEB_DIR" ] && [ -f "$WEB_DIR/package.json" ]; then
    echo "Running ESLint for $WEB_DIR..."
    cd "$WEB_DIR"
    npm run lint
else
    echo "Warning: $WEB_DIR not found or package.json missing, skipping ESLint"
    exit 0
fi
