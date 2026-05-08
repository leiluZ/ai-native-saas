#!/bin/bash
set -e

PROJECT_ROOT="$(git rev-parse --show-toplevel)"
ORIGINAL_DIR="$(pwd)"

# Detect Python and package manager
PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    PYTHON_CMD="python"
fi

echo "========================================"
echo "  Local CI/CD Testing Script"
echo "========================================"
echo "Using Python: $PYTHON_CMD"
echo ""

# Detect changed weeks
CHANGED_WEEKS=$(git diff --cached --name-only | grep -oE 'ai-saas-week[0-9]+' | sort -u)
if [ -z "$CHANGED_WEEKS" ]; then
    CHANGED_WEEKS=$(git diff --name-only | grep -oE 'ai-saas-week[0-9]+' | sort -u)
fi
if [ -z "$CHANGED_WEEKS" ]; then
    echo "No week directories found in changes, using week3 as default"
    CHANGED_WEEKS="ai-saas-week3"
fi

echo "Detected changed weeks: $CHANGED_WEEKS"
echo ""

# ========================================
# Job 1: Lint (Backend)
# ========================================
echo "========================================"
echo "Job 1: Lint (Backend)"
echo "========================================"
for WEEK_DIR in $CHANGED_WEEKS; do
    if [ -d "$WEEK_DIR/app/backend/src/" ]; then
        echo "--- Linting $WEEK_DIR/backend/src/ ---"
        cd "$ORIGINAL_DIR/$WEEK_DIR/app/backend"
        ruff check src/ || { echo "ruff check failed"; exit 1; }
        $PYTHON_CMD -m black --check src/ || { echo "black check failed"; exit 1; }
        echo "✓ $WEEK_DIR/backend lint passed"
    fi
done
echo ""
cd "$ORIGINAL_DIR"

# ========================================
# Job 2: Backend Tests
# ========================================
echo "========================================"
echo "Job 2: Backend Tests"
echo "========================================"
for WEEK_DIR in $CHANGED_WEEKS; do
    if [ -d "$WEEK_DIR/app/backend/tests/" ]; then
        echo "--- Testing $WEEK_DIR/backend ---"
        cd "$ORIGINAL_DIR/$WEEK_DIR/app/backend"
        PYTHONPATH=. $PYTHON_CMD -m pytest tests/ -v --cov=src/ --cov-report=xml || { echo "Backend tests failed"; exit 1; }
        echo "✓ $WEEK_DIR/backend tests passed"
    fi
done
echo ""
cd "$ORIGINAL_DIR"

# ========================================
# Job 3: RAG Pipeline Tests
# ========================================
echo "========================================"
echo "Job 3: RAG Pipeline Tests"
echo "========================================"
RAG_TESTS_PASSED=false
for WEEK_DIR in $CHANGED_WEEKS; do
    if [ -d "$WEEK_DIR/app/backend/src/rag/" ]; then
        echo "--- Testing RAG pipeline for $WEEK_DIR ---"
        cd "$ORIGINAL_DIR/$WEEK_DIR/app/backend"

        # Run document parser script if exists
        if [ -f "scripts/test_document_parser.py" ]; then
            PYTHONPATH=. $PYTHON_CMD scripts/test_document_parser.py || { echo "RAG script test failed"; exit 1; }
            echo "✓ $WEEK_DIR RAG script tests passed"
            RAG_TESTS_PASSED=true
        fi

        # Run RAG-specific pytest tests if any exist
        RAG_TEST_COUNT=$($PYTHON_CMD -m pytest tests/ -v -k "rag" --collect-only 2>/dev/null | grep -c "<Function" || echo "0")
        if [ "$RAG_TEST_COUNT" -gt 0 ] 2>/dev/null; then
            PYTHONPATH=. $PYTHON_CMD -m pytest tests/ -v -k "rag" || { echo "RAG pytest tests failed"; exit 1; }
            echo "✓ $WEEK_DIR RAG pytest tests passed"
            RAG_TESTS_PASSED=true
        else
            echo "⚠ $WEEK_DIR No pytest RAG tests found (skipping)"
        fi

        if [ "$RAG_TESTS_PASSED" = true ]; then
            echo "✓ $WEEK_DIR RAG tests passed"
        else
            echo "⚠ $WEEK_DIR No RAG tests found (skipping)"
        fi
    fi
done
echo ""
cd "$ORIGINAL_DIR"

# ========================================
# Job 4: Frontend Lint
# ========================================
echo "========================================"
echo "Job 4: Frontend Lint"
echo "========================================"
for WEEK_DIR in $CHANGED_WEEKS; do
    if [ -d "$WEEK_DIR/app/web/src/" ]; then
        echo "--- Linting $WEEK_DIR/web ---"
        cd "$ORIGINAL_DIR/$WEEK_DIR/app/web"

        if [ ! -f "package-lock.json" ]; then
            echo "Warning: package-lock.json not found, running npm install..."
            npm install
        fi

        npm ci || npm install
        npm run lint || { echo "ESLint failed"; exit 1; }
        echo "✓ $WEEK_DIR/web lint passed"
    fi
done
echo ""
cd "$ORIGINAL_DIR"

# ========================================
# Job 5: Frontend Build
# ========================================
echo "========================================"
echo "Job 5: Frontend Build"
echo "========================================"
for WEEK_DIR in $CHANGED_WEEKS; do
    if [ -d "$WEEK_DIR/app/web/src/" ]; then
        echo "--- Building $WEEK_DIR/web ---"
        cd "$ORIGINAL_DIR/$WEEK_DIR/app/web"
        npm run build || { echo "Frontend build failed"; exit 1; }
        echo "✓ $WEEK_DIR/web build passed"
    fi
done
echo ""
cd "$ORIGINAL_DIR"

# ========================================
# Summary
# ========================================
echo "========================================"
echo "  All CI Jobs Passed!"
echo "========================================"
echo ""
echo "Summary:"
echo "  - Lint (Backend):  ✓"
echo "  - Backend Tests:   ✓"
echo "  - RAG Tests:       ✓ (skipped if no tests found)"
echo "  - Frontend Lint:  ✓"
echo "  - Frontend Build:  ✓"
echo ""
