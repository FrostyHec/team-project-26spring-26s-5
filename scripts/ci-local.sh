#!/bin/bash
# =============================================================================
# CI Local Simulation Script
# Purpose: Run all CI checks locally before creating a PR
# Usage: bash scripts/ci-local.sh
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
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_error() { echo -e "${RED}✗ $1${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

export PATH="$HOME/.local/bin:$PATH"

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Agent Project CI Simulation${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# =============================================================================
# Step 1: Lint & Format Check (no auto-fix)
# =============================================================================
print_header "Step 1/5: Lint & Format Check"

LINT_FAILED=0
for pkg in packages/core packages/cli packages/poc_frontend; do
    if [ -d "$pkg/src" ]; then
        echo "Checking $pkg..."
        cd "$PROJECT_ROOT/$pkg"
        if ! uv run ruff format --check src/ tests/; then
            LINT_FAILED=1
        fi
        if ! uv run ruff check src/ tests/; then
            LINT_FAILED=1
        fi
        cd "$PROJECT_ROOT"
    fi
done

echo "Checking Vue formatting..."
cd "$PROJECT_ROOT/packages/gui"
if ! pnpm prettier --check --experimental-cli src/; then
    LINT_FAILED=1
fi
cd "$PROJECT_ROOT"

if [ $LINT_FAILED -ne 0 ]; then
    print_error "Lint/format check failed"
    echo "Run 'task format' to auto-fix formatting issues"
    exit 1
fi
print_success "Lint & format check passed"

# =============================================================================
# Step 2: Language Check
# =============================================================================
print_header "Step 2/5: Language Check"

if python3 scripts/check_language.py --root "$PROJECT_ROOT"; then
    print_success "Language check passed"
else
    print_error "Language check failed"
    exit 1
fi

# =============================================================================
# Step 3: Run Python Tests
# =============================================================================
print_header "Step 3/5: Run Python Tests"

TEST_FAILED=0
for pkg in packages/core packages/cli packages/poc_frontend; do
    if [ -d "$pkg/tests" ]; then
        echo "Testing $pkg..."
        cd "$PROJECT_ROOT/$pkg"
        if ! uv run pytest tests/ -v --tb=short; then
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
# Step 4: Run Vue Frontend Tests
# =============================================================================
print_header "Step 4/5: Run Vue Tests"

cd "$PROJECT_ROOT/packages/gui"
if pnpm vitest run; then
    print_success "Vue tests passed"
else
    print_error "Vue tests failed"
    exit 1
fi
cd "$PROJECT_ROOT"

# =============================================================================
# Step 5: Vue Type Check & Build
# =============================================================================
print_header "Step 5/5: Vue Type Check & Build"

cd "$PROJECT_ROOT/packages/gui"
if pnpm run type-check && pnpm build; then
    print_success "Vue type check and build passed"
else
    print_error "Vue type check or build failed"
    exit 1
fi
cd "$PROJECT_ROOT"

# =============================================================================
# Summary
# =============================================================================
print_header "Summary"

echo -e "${GREEN}✓ All CI checks passed!${NC}"
echo ""
print_success "Code is ready to create a Pull Request"
