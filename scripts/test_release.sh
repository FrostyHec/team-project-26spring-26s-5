#!/bin/bash
# =============================================================================
# Test Release Script for deep-solutions
# 
# Publishes a test version to TestPyPI to validate the release pipeline.
# Use this BEFORE final_release.sh to verify everything works.
#
# Flow:
#   0. Reminds user to update CHANGELOG.md
#   1. Switches to main branch and pulls latest code
#   2. Prompts for version tag input (e.g., v0.1.1.dev1)
#   3. Creates and pushes git tag
#   4. Triggers publish-test workflow via gh CLI
#   5. Waits for completion and displays results
#
# Prerequisites:
#   - GitHub CLI (gh) installed and authenticated
#   - Run: gh auth login
#
# Usage:
#   bash scripts/test_release.sh
# =============================================================================

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored messages
print_info() {
    echo -e "${BLUE}ℹ ${NC}$1"
}

print_success() {
    echo -e "${GREEN}✅ ${NC}$1"
}

print_warning() {
    echo -e "${YELLOW}⚠️  ${NC}$1"
}

print_error() {
    echo -e "${RED}❌ ${NC}$1"
}

# Function to validate version format
validate_version() {
    local version=$1
    # Version must start with 'v' followed by numbers/dots/rc/dev/alpha/beta
    if [[ ! $version =~ ^v[0-9]+\.[0-9]+\.[0-9]+ ]]; then
        print_error "Invalid version format: $version"
        print_info "Version must start with vX.Y.Z (e.g., v1.0.0, v0.1.1rc1, v2.0.0.dev1)"
        return 1
    fi
    return 0
}

# Function to check if gh CLI is authenticated
check_gh_auth() {
    if ! command -v gh &> /dev/null; then
        print_error "GitHub CLI (gh) is not installed"
        print_info "Install via conda: conda install -c conda-forge gh"
        exit 1
    fi
    
    if ! gh auth status &> /dev/null; then
        print_error "GitHub CLI is not authenticated"
        print_info "Please run: gh auth login"
        exit 1
    fi
}

# Function to check if tag already exists
check_tag_exists() {
    local version=$1
    if git rev-parse "$version" >/dev/null 2>&1; then
        return 0  # Tag exists
    fi
    return 1  # Tag doesn't exist
}

# Main script
main() {
    echo "========================================"
    print_info "Deep Solutions Release Script"
    echo "========================================"
    echo
    
    # Step 0: Remind about CHANGELOG
    print_warning "Step 0: CHANGELOG.md Reminder"
    print_info "Please ensure CHANGELOG.md has been updated with:"
    print_info "  - All changes for this release"
    print_info "  - Proper version header"
    print_info "  - Current date"
    echo
    read -p "$(echo -e ${YELLOW}'Has CHANGELOG.md been updated? (y/n): '${NC})" -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warning "Please update CHANGELOG.md first, then run this script again"
        exit 0
    fi
    echo
    
    # Step 1: Switch to main and pull
    print_info "Step 1: Switching to main branch and pulling latest code..."
    
    # Check if on main branch
    CURRENT_BRANCH=$(git branch --show-current)
    if [ "$CURRENT_BRANCH" != "main" ]; then
        print_info "Current branch: $CURRENT_BRANCH"
        print_info "Switching to main branch..."
        git checkout main
    fi
    
    # Pull latest code
    print_info "Pulling latest code from origin/main..."
    git pull origin main
    print_success "On main branch with latest code"
    echo
    
    # Step 2: Input version tag
    print_info "Step 2: Enter version tag"
    print_info "Examples: v0.1.1rc1, v1.0.0, v2.0.0.dev1"
    echo
    read -p "$(echo -e ${BLUE}'Enter version tag: '${NC})" VERSION
    
    # Validate version format
    if ! validate_version "$VERSION"; then
        exit 1
    fi
    
    # Check if tag already exists
    if check_tag_exists "$VERSION"; then
        print_error "Tag $VERSION already exists!"
        print_info "Please use a different version tag"
        exit 1
    fi
    
    print_success "Version tag: $VERSION"
    echo
    
    # Check gh authentication
    print_info "Checking GitHub CLI authentication..."
    check_gh_auth
    print_success "GitHub CLI is authenticated"
    echo
    
    # Step 3: Create and push tag
    print_info "Step 3: Creating and pushing git tag..."
    
    git tag -a "$VERSION" -m "Release $VERSION"
    print_success "Git tag created: $VERSION"
    
    git push origin "$VERSION"
    print_success "Tag pushed to origin"
    echo
    
    # Step 4: Trigger publish-test workflow
    print_info "Step 4: Triggering publish-test workflow..."
    
    # Trigger the workflow
    WORKFLOW_RUN=$(gh workflow run publish-test.yml -f version_tag="$VERSION" --ref "$VERSION" 2>&1)
    
    if [ $? -ne 0 ]; then
        print_error "Failed to trigger workflow"
        print_error "$WORKFLOW_RUN"
        exit 1
    fi
    
    print_success "Workflow triggered successfully"
    print_info "Waiting for workflow to start..."
    sleep 5
    
    # Get the latest workflow run
    RUN_ID=$(gh run list --workflow=publish-test.yml --limit 1 --json databaseId --jq '.[0].databaseId')
    
    if [ -z "$RUN_ID" ]; then
        print_error "Could not find workflow run"
        print_info "Check manually: gh run list --workflow=publish-test.yml"
        exit 1
    fi
    
    print_info "Monitoring workflow run: $RUN_ID"
    print_info "You can view it at: https://github.com/FrostyHec/deep-solutions/actions/runs/$RUN_ID"
    echo
    
    # Wait for workflow to complete
    print_info "Waiting for workflow to complete (this may take a few minutes)..."
    gh run watch "$RUN_ID"
    
    # Get workflow status
    WORKFLOW_STATUS=$(gh run view "$RUN_ID" --json conclusion --jq '.conclusion')
    
    echo
    echo "========================================"
    
    # Step 5: Display results and guide next steps
    if [ "$WORKFLOW_STATUS" == "success" ]; then
        print_success "Workflow completed successfully!"
        echo "========================================"
        echo
        print_success "✅ TestPyPI publish test PASSED"
        print_info "Package has been validated on TestPyPI"
        echo
        print_warning "Next Steps - Publish to Production PyPI:"
        print_info "1. Go to GitHub Actions: https://github.com/FrostyHec/deep-solutions/actions"
        print_info "2. Select 'Publish to PyPI' workflow"
        print_info "3. Click 'Run workflow'"
        print_info "4. Enter version tag: ${YELLOW}$VERSION${NC}"
        print_info "5. Click 'Run workflow' button"
        echo
        print_info "Or use gh CLI:"
        echo -e "   ${GREEN}gh workflow run publish.yml -f version_tag=\"$VERSION\" --ref \"$VERSION\"${NC}"
        echo
    else
        print_error "Workflow failed with status: $WORKFLOW_STATUS"
        echo "========================================"
        echo
        print_error "❌ TestPyPI publish test FAILED"
        print_warning "Action Required:"
        print_info "1. Check workflow logs: gh run view $RUN_ID --log"
        print_info "2. Fix the issues identified"
        print_info "3. Delete the failed tag: git tag -d $VERSION && git push origin :$VERSION"
        print_info "4. Run this script again"
        echo
        print_info "View full logs: https://github.com/FrostyHec/deep-solutions/actions/runs/$RUN_ID"
        exit 1
    fi
}

# Run main function
main "$@"
