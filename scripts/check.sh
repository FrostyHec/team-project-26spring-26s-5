#!/bin/bash
# =============================================================================
# Agent Project - Developer Check Script
# Run complete code check pipeline before commit
# Usage: bash scripts/check.sh
# =============================================================================

set -e

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}============================================================${NC}"
    echo ""
}

print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_error() { echo -e "${RED}✗ $1${NC}"; }

# Get project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Agent Project Code Check${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Project directory: $PROJECT_ROOT"

# Ensure uv and task are available
export PATH="$HOME/.local/bin:$PATH"

# =============================================================================
# Step 1: Format Python code
# =============================================================================
print_header "Step 1/5: Code Formatting (ruff)"

for pkg in packages/core packages/cli packages/poc_frontend; do
    if [ -d "$pkg/src" ]; then
        echo "Formatting $pkg..."
        cd "$PROJECT_ROOT/$pkg"
        uv run ruff format src/ tests/ 2>/dev/null || true
        uv run ruff check --fix src/ tests/ 2>/dev/null || true
        cd "$PROJECT_ROOT"
    fi
done
print_success "Code formatting complete"

# =============================================================================
# Step 2: Lint Check
# =============================================================================
print_header "Step 2/5: Lint Check (ruff)"

LINT_FAILED=0
for pkg in packages/core packages/cli packages/poc_frontend; do
    if [ -d "$pkg/src" ]; then
        echo "Linting $pkg..."
        cd "$PROJECT_ROOT/$pkg"
        if ! uv run ruff check src/ tests/; then
            LINT_FAILED=1
        fi
        cd "$PROJECT_ROOT"
    fi
done

if [ $LINT_FAILED -ne 0 ]; then
    print_error "Lint check failed"
    exit 1
fi
print_success "Lint check passed"

# =============================================================================
# Step 3: Language Check
# =============================================================================
print_header "Step 3/5: Language Check"

echo "Checking for Chinese characters in source code..."
if python3 scripts/check_language.py --root "$PROJECT_ROOT"; then
    print_success "Language check passed"
else
    print_error "Language check failed"
    exit 1
fi

# =============================================================================
# Step 4: Run Tests (pytest + vitest)
# =============================================================================
print_header "Step 4/5: Run Python Tests (pytest)"

TEST_FAILED=0
for pkg in packages/core packages/cli packages/poc_frontend; do
    if [ -d "$pkg/tests" ]; then
        echo "Testing $pkg..."
        cd "$PROJECT_ROOT/$pkg"
        if ! uv run pytest tests/ -v; then
            TEST_FAILED=1
        fi
        cd "$PROJECT_ROOT"
    fi
done

if [ $TEST_FAILED -ne 0 ]; then
    print_error "Python tests failed"
    exit 1
fi
print_success "Python tests passed"

# =============================================================================
# Step 5: Run Vue Frontend Tests (vitest)
# =============================================================================
print_header "Step 5/5: Run Vue Tests (vitest)"

cd "$PROJECT_ROOT/packages/gui"
if pnpm vitest run; then
    print_success "Vue tests passed"
else
    print_error "Vue tests failed"
    exit 1
fi
cd "$PROJECT_ROOT"

# =============================================================================
# Complete
# =============================================================================
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ✓ All checks passed!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Code is ready to commit."
