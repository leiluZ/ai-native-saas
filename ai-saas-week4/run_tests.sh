#!/bin/bash
set -e

echo "=== 运行 Benchmark 测试 ==="
cd "$(dirname "$0")/.."

pip install pytest pytest-asyncio pytest-mock -q 2>/dev/null

PYTHONPATH="$(pwd)" pytest tests/ \
    -v \
    --tb=short \
    --timeout=60

echo ""
echo "=== 测试完成 ==="
