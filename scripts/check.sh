#!/bin/bash
# =============================================================================
# Agent Project - Check Script
# Run code check and format pipeline
# 
# Usage:
#   bash scripts/check.sh              # Full check + auto-format (dev mode)
#   bash scripts/check.sh --check-only # Only check, no auto-format (CI mode)
#   bash scripts/check.sh --help       # Show this help message
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
print_info() { echo -e "${YELLOW}ℹ $1${NC}"; }

# Get project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Parse command line arguments
CHECK_ONLY=false
SHOW_HELP=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --check-only)
            CHECK_ONLY=true
            shift
            ;;
        --help)
            SHOW_HELP=true
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            SHOW_HELP=true
            shift
            ;;
    esac
done

if [ "$SHOW_HELP" = true ]; then
    echo ""
    echo "Usage: bash scripts/check.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --check-only   Only check code style, do not auto-format (CI mode)"
    echo "  --help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  bash scripts/check.sh              # Dev mode: check + auto-format"
    echo "  bash scripts/check.sh --check-only # CI mode: check only"
    echo ""
    exit 0
fi

MODE_TEXT="dev mode (auto-format enabled)"
if [ "$CHECK_ONLY" = true ]; then
    MODE_TEXT="CI mode (check only, no auto-format)"
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Agent Project Code Check${NC}"
echo -e "${BLUE}  Mode: $MODE_TEXT${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Project directory: $PROJECT_ROOT"

# Ensure uv and task are available
export PATH="$HOME/.local/bin:$PATH"

# =============================================================================
# Step 1: Format code (Python + Vue) - only if not --check-only
# =============================================================================
if [ "$CHECK_ONLY" = false ]; then
    print_header "Step 1/6: Code Formatting (ruff + prettier)"

    for pkg in packages/core packages/cli; do
        if [ -d "$pkg/src" ]; then
            echo "Formatting $pkg..."
            cd "$PROJECT_ROOT/$pkg"
            uv run ruff format src/ tests/ 2>/dev/null || true
            uv run ruff check --fix src/ tests/ 2>/dev/null || true
            cd "$PROJECT_ROOT"
        fi
    done

    echo "Formatting packages/gui..."
    cd "$PROJECT_ROOT/packages/gui"
    pnpm format 2>/dev/null || true
    cd "$PROJECT_ROOT"

    print_success "Code formatting complete"
else
    print_info "Skipping auto-format (--check-only mode)"
fi

# =============================================================================
# Step 2 (or 1 if --check-only): Lint Check (Python + Vue)
# =============================================================================
if [ "$CHECK_ONLY" = false ]; then
    STEP_NUM="2/6"
    NEXT_STEP="3"
    TOTAL_STEPS=6
else
    STEP_NUM="1/5"
    NEXT_STEP="2"
    TOTAL_STEPS=5
fi

print_header "Step $STEP_NUM: Lint Check (ruff + prettier)"

LINT_FAILED=0
for pkg in packages/core packages/cli; do
    if [ -d "$pkg/src" ]; then
        echo "Linting $pkg..."
        cd "$PROJECT_ROOT/$pkg"
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
    print_error "Lint check failed"
    exit 1
fi
print_success "Lint check passed"

# =============================================================================
# Step 3 (or 2 if --check-only): Language Check (Semgrep)
# =============================================================================
STEP_NUM=$((NEXT_STEP))/$(echo "$TOTAL_STEPS")
print_header "Step $STEP_NUM: Language Check (Semgrep)"

echo "Checking for CJK characters in source code via Semgrep..."
if ! command -v semgrep &>/dev/null; then
    print_error "semgrep not found. Install with: pip install semgrep"
    exit 1
fi
if semgrep --config "$PROJECT_ROOT/semgrep-rules.yaml" \
           --no-git-ignore \
           --error \
           --quiet \
           "$PROJECT_ROOT/packages" \
           "$PROJECT_ROOT/.github" \
           "$PROJECT_ROOT/scripts"; then
    print_success "Language check passed"
else
    print_error "Language check failed: CJK characters found in source code"
    print_info "To suppress a single line, add '# nosemgrep' (Python/YAML/Shell) or '// nosemgrep' (JS/TS/Vue) at the end of the line"
    exit 1
fi

# Update step counter for next steps
NEXT_STEP=$((NEXT_STEP + 1))

# =============================================================================
# Step 4 (or 3 if --check-only): Run Tests (pytest)
# =============================================================================
STEP_NUM=$((NEXT_STEP))/$TOTAL_STEPS
print_header "Step $STEP_NUM: Run Python Tests (pytest)"

TEST_FAILED=0
for pkg in packages/core packages/cli; do
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

# Update step counter for next steps
NEXT_STEP=$((NEXT_STEP + 1))

# =============================================================================
# Step 5 (or 4 if --check-only): Run Vue Frontend Tests (vitest)
# =============================================================================
STEP_NUM=$((NEXT_STEP))/$TOTAL_STEPS
print_header "Step $STEP_NUM: Run Vue Tests (vitest)"

cd "$PROJECT_ROOT/packages/gui"
if pnpm vitest run; then
    print_success "Vue tests passed"
else
    print_error "Vue tests failed"
    exit 1
fi
cd "$PROJECT_ROOT"

# Update step counter for next steps
NEXT_STEP=$((NEXT_STEP + 1))

# =============================================================================
# Step 6 (or 5 if --check-only): Vue Type Check & Build
# =============================================================================
if [ "$CHECK_ONLY" = false ]; then
    STEP_NUM="6/6"
    print_header "Step $STEP_NUM: Vue Type Check & Build"

    cd "$PROJECT_ROOT/packages/gui"
    if pnpm run type-check && pnpm build; then
        print_success "Vue type check and build passed"
    else
        print_error "Vue type check or build failed"
        exit 1
    fi
    cd "$PROJECT_ROOT"
else
    STEP_NUM="5/5"
    print_header "Step $STEP_NUM: Vue Type Check & Build"

    cd "$PROJECT_ROOT/packages/gui"
    if pnpm run type-check && pnpm build; then
        print_success "Vue type check and build passed"
    else
        print_error "Vue type check or build failed"
        exit 1
    fi
    cd "$PROJECT_ROOT"
fi

# =============================================================================
# Complete
# =============================================================================
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ✓ All checks passed!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

if [ "$CHECK_ONLY" = false ]; then
    echo "Code is ready to commit."
else
    echo "All CI checks passed."
fi
echo ""
