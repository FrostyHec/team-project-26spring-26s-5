#!/bin/bash
# =============================================================================
# CI local simulation script
# Purpose: Run all CI checks locally before creating a PR
# =============================================================================

set -e  # Exit on error

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}========================================${NC}"
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

# =============================================================================
# Step 1: Lint & Format Check
# =============================================================================
print_header "Step 1/4: Lint & Format Check"

echo "Checking code format..."
if ruff format --check src/ tests/; then
    print_success "Code format check passed"
else
    print_error "Code format check failed"
    echo ""
    echo "Run the following to fix formatting:"
    echo "  ruff format src/ tests/"
    exit 1
fi

echo ""
echo "Running linter..."
if ruff check src/ tests/; then
    print_success "Lint check passed"
else
    print_error "Lint check failed"
    echo ""
    echo "Try auto-fixing with:"
    echo "  ruff check --fix src/ tests/"
    exit 1
fi

# =============================================================================
# Step 2: Type Check
# =============================================================================
print_header "Step 2/4: Type Check"

echo "Running MyPy type checks..."
if mypy src/; then
    print_success "Type check passed"
else
    print_error "Type check failed"
    exit 1
fi

# =============================================================================
# Step 3: Run Tests
# =============================================================================
print_header "Step 3/4: Run Tests"

echo "Running tests and generating reports..."
if pytest --junitxml=pytest-report.xml --cov=deep_solutions --cov-report=xml --cov-report=term-missing; then
    print_success "All tests passed"
else
    print_error "Tests failed"
    exit 1
fi

# =============================================================================
# Step 4: Build Check
# =============================================================================
print_header "Step 4/4: Build Check"

echo "Cleaning previous build artifacts..."
rm -rf dist/ build/ *.egg-info

echo "Building package..."
if python -m build; then
    print_success "Package build succeeded"
else
    print_error "Package build failed"
    exit 1
fi

echo ""
echo "Checking distribution files..."
if twine check dist/*; then
    print_success "Distribution check passed"
else
    print_error "Distribution check failed"
    exit 1
fi

# =============================================================================
# Summary
# =============================================================================
print_header "Summary"

echo -e "${GREEN}✓ All CI checks passed!${NC}"
echo ""
echo "Generated files:"
echo "  - pytest-report.xml (test report)"
echo "  - coverage.xml (coverage report)"
echo "  - dist/ (build artifacts)"
echo ""
print_success "Code is ready to create a Pull Request"
