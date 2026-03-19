#!/bin/bash
# =============================================================================
# deep-solutions Developer Check Script
# Run complete code check pipeline before commit/publish
# =============================================================================

set -e  # Exit on error

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored messages
print_header() {
    echo ""
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}============================================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Get project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  deep-solutions Code Check Script${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Project directory: $PROJECT_ROOT"
echo ""

# =============================================================================
# Step 1: Code Formatting
# =============================================================================
print_header "Step 1/5: Code Formatting (ruff format)"

echo "Formatting src/ and tests/ ..."
ruff format src/ tests/
print_success "Code formatting complete"

# =============================================================================
# Step 2: Lint Check
# =============================================================================
print_header "Step 2/5: Lint Check (ruff check)"

echo "Checking code issues..."
if ruff check src/ tests/; then
    print_success "Lint check passed"
else
    print_error "Lint check failed"
    echo ""
    echo "Tip: Run 'ruff check --fix src/ tests/' to auto-fix some issues"
    exit 1
fi

# =============================================================================
# Step 3: Type Check
# =============================================================================
print_header "Step 3/5: Type Check (mypy)"

echo "Running type check..."
if mypy src/; then
    print_success "Type check passed"
else
    print_error "Type check failed"
    exit 1
fi

# =============================================================================
# Step 4: Language Check
# =============================================================================
print_header "Step 4/5: Language Check"

echo "Checking for Chinese characters in source code..."
if python scripts/check_language.py; then
    print_success "Language check passed"
else
    print_error "Language check failed"
    exit 1
fi

# =============================================================================
# Step 5: Run Tests
# =============================================================================
print_header "Step 5/5: Run Tests (pytest)"

echo "Running tests..."
if pytest; then
    print_success "All tests passed"
else
    print_error "Tests failed"
    exit 1
fi

# =============================================================================
# Complete
# =============================================================================
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ✓ All checks passed!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Code is ready to commit or publish."
echo ""
