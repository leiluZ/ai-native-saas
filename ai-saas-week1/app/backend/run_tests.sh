#!/bin/bash
# pytest 运行脚本

set -e

echo "=== 运行所有测试 ==="
cd /Users/leilu/Documents/cursor_projects/ai-native-saas/ai-saas-week1/app/backend

# 确保测试依赖已安装
pip install pytest pytest-asyncio pytest-mock pytest-cov -q

# 运行测试
echo "Running pytest with coverage..."
PYTHONPATH=/Users/leilu/Documents/cursor_projects/ai-native-saas/ai-saas-week1/app/backend \
pytest tests/test_llm_client.py tests/test_tool_registry.py tests/test_memory_manager.py tests/test_agent_router.py \
    -v \
    --cov=src/agents/ \
    --cov-report=term-missing \
    --cov-report=html

echo ""
echo "=== 测试完成 ==="
echo "覆盖率报告已生成在 htmlcov/ 目录中"
