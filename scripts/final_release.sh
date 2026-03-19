#!/bin/bash
# =============================================================================
# Final Release Script for deep-solutions
#
# Publishes a production version to PyPI.
# Run test_release.sh FIRST to validate the pipeline on TestPyPI.
#
# Two modes:
#   A) Rename mode — rename an existing tag (e.g. v0.1.1.dev3 → v0.1.1),
#      optionally clean up other .dev tags.
#   B) Direct mode — use an existing tag as-is (e.g. you already tested
#      with v0.1.1 directly, so no rename needed).
#
# Flow:
#   1. Ask rename-or-direct
#   2. (Rename) create new tag, delete old, optionally clean .dev tags
#   3. Trigger publish.yml workflow
#   4. Wait for completion and display results
#
# Prerequisites:
#   - GitHub CLI (gh) installed and authenticated: gh auth login
#   - test_release.sh has passed for the version being published
#
# Usage:
#   bash scripts/final_release.sh
# =============================================================================

set -e

# ── colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info()    { echo -e "${BLUE}ℹ ${NC}$1"; }
print_success() { echo -e "${GREEN}✅ ${NC}$1"; }
print_warning() { echo -e "${YELLOW}⚠️  ${NC}$1"; }
print_error()   { echo -e "${RED}❌ ${NC}$1"; }

# ── helpers ──────────────────────────────────────────────────────────────────
validate_version() {
    local version=$1
    if [[ ! $version =~ ^v[0-9]+\.[0-9]+\.[0-9]+ ]]; then
        print_error "Invalid version format: $version"
        print_info "Must start with vX.Y.Z (e.g., v1.0.0, v0.1.1.dev1)"
        return 1
    fi
    return 0
}

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

tag_exists() {
    git rev-parse "$1" >/dev/null 2>&1
}

# ── main ─────────────────────────────────────────────────────────────────────
main() {
    echo "========================================"
    print_info "Deep Solutions — Final Release"
    echo "========================================"
    echo

    # Pre-flight
    check_gh_auth
    print_success "GitHub CLI is authenticated"
    echo

    # Ensure main is up-to-date
    print_info "Ensuring main branch is up-to-date..."
    CURRENT_BRANCH=$(git branch --show-current)
    if [ "$CURRENT_BRANCH" != "main" ]; then
        print_info "Switching from $CURRENT_BRANCH to main..."
        git checkout main
    fi
    git pull origin main
    print_success "On main branch with latest code"
    echo

    # ── Step 1: Choose mode ──────────────────────────────────────────────────
    print_info "Step 1: Choose release mode"
    print_info "  A) Rename mode — rename a test tag (e.g. v0.1.1.dev3 → v0.1.1)"
    print_info "  B) Direct mode — use an existing tag as-is"
    echo
    read -p "$(echo -e ${YELLOW}'Rename an existing tag? (y/n): '${NC})" -n 1 -r
    echo
    RENAME_MODE=false
    [[ $REPLY =~ ^[Yy]$ ]] && RENAME_MODE=true
    echo

    if $RENAME_MODE; then
        # ── Rename mode ─────────────────────────────────────────────────────
        read -p "$(echo -e ${BLUE}'Origin tag (the one that passed test): '${NC})" ORIGIN_TAG
        if ! validate_version "$ORIGIN_TAG"; then exit 1; fi
        if ! tag_exists "$ORIGIN_TAG"; then
            print_error "Tag $ORIGIN_TAG does not exist!"
            print_info "Run test_release.sh first to create and validate a tag."
            exit 1
        fi
        echo
        read -p "$(echo -e ${BLUE}'Publish tag (final version, e.g. v0.1.1): '${NC})" PUBLISH_TAG
        if ! validate_version "$PUBLISH_TAG"; then exit 1; fi
        if tag_exists "$PUBLISH_TAG"; then
            print_error "Tag $PUBLISH_TAG already exists!"
            exit 1
        fi

        echo
        print_info "Renaming tag: $ORIGIN_TAG → $PUBLISH_TAG"

        # Create new tag pointing at same commit as origin tag
        git tag -a "$PUBLISH_TAG" "$ORIGIN_TAG"^{} -m "Release $PUBLISH_TAG"
        print_success "Local tag created: $PUBLISH_TAG"

        # Push new tag
        git push origin "$PUBLISH_TAG"
        print_success "Pushed $PUBLISH_TAG to origin"

        # Delete old local + remote tag
        git tag -d "$ORIGIN_TAG"
        git push origin ":refs/tags/$ORIGIN_TAG"
        print_success "Deleted origin tag: $ORIGIN_TAG"
        echo

        # ── Optional: clean up other .dev tags ──────────────────────────────
        # Extract base version (e.g. v0.1.1 from v0.1.1.dev3)
        BASE_VERSION=$(echo "$PUBLISH_TAG" | grep -oP '^v[0-9]+\.[0-9]+\.[0-9]+')
        DEV_TAGS=$(git tag -l "${BASE_VERSION}.dev*" 2>/dev/null || true)

        if [ -n "$DEV_TAGS" ]; then
            print_warning "Found remaining .dev tags for $BASE_VERSION:"
            echo "$DEV_TAGS" | sed 's/^/    /'
            echo
            read -p "$(echo -e ${YELLOW}'Delete all these .dev tags? (y/n): '${NC})" -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                for tag in $DEV_TAGS; do
                    git tag -d "$tag" 2>/dev/null || true
                    git push origin ":refs/tags/$tag" 2>/dev/null || true
                    print_info "Deleted: $tag"
                done
                print_success "All .dev tags cleaned up"
            else
                print_info "Skipping .dev tag cleanup"
            fi
            echo
        fi

    else
        # ── Direct mode ──────────────────────────────────────────────────────
        read -p "$(echo -e ${BLUE}'Publish tag: '${NC})" PUBLISH_TAG
        if ! validate_version "$PUBLISH_TAG"; then exit 1; fi
        if ! tag_exists "$PUBLISH_TAG"; then
            print_error "Tag $PUBLISH_TAG does not exist!"
            print_warning "You should run test_release.sh first to create and validate the tag."
            exit 1
        fi
        print_success "Using existing tag: $PUBLISH_TAG"
        echo
    fi

    # ── Step 2: Trigger publish.yml ──────────────────────────────────────────
    print_info "Step 2: Triggering production publish workflow..."

    gh workflow run publish.yml -f version_tag="$PUBLISH_TAG" --ref "$PUBLISH_TAG" 2>&1
    if [ $? -ne 0 ]; then
        print_error "Failed to trigger publish workflow"
        exit 1
    fi

    print_success "Workflow triggered successfully"
    print_info "Waiting for workflow to start..."
    sleep 5

    # Get the run ID
    RUN_ID=$(gh run list --workflow=publish.yml --limit 1 --json databaseId --jq '.[0].databaseId')
    if [ -z "$RUN_ID" ]; then
        print_error "Could not find workflow run"
        print_info "Check manually: gh run list --workflow=publish.yml"
        exit 1
    fi

    print_info "Monitoring workflow run: $RUN_ID"
    print_info "View at: https://github.com/FrostyHec/deep-solutions/actions/runs/$RUN_ID"
    echo

    # ── Step 3: Wait and report ──────────────────────────────────────────────
    print_info "Waiting for workflow to complete (this may take several minutes)..."
    gh run watch "$RUN_ID"

    WORKFLOW_STATUS=$(gh run view "$RUN_ID" --json conclusion --jq '.conclusion')

    echo
    echo "========================================"

    if [ "$WORKFLOW_STATUS" == "success" ]; then
        print_success "Production publish completed successfully!"
        echo "========================================"
        echo
        print_success "✅ PyPI publish PASSED"
        print_info "Package published: deep-solutions (tag $PUBLISH_TAG)"
        echo
        print_info "Verify installation:"
        VERSION_NUM="${PUBLISH_TAG#v}"
        echo -e "   ${GREEN}pip install deep-solutions==${VERSION_NUM}${NC}"
        echo
        print_success "🎉 Release $PUBLISH_TAG is live!"
    else
        print_error "Workflow failed with status: $WORKFLOW_STATUS"
        echo "========================================"
        echo
        print_error "❌ Production publish FAILED"
        print_warning "Action Required:"
        print_info "1. Check logs: gh run view $RUN_ID --log"
        print_info "2. View: https://github.com/FrostyHec/deep-solutions/actions/runs/$RUN_ID"
        exit 1
    fi
}

main "$@"
