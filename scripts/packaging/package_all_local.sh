#!/usr/bin/env bash
# 功能：在当前本机平台执行完整打包流程，包括检查、前端构建、后端 staging、smoke test 和桌面端打包。 # nosemgrep
# Purpose: Run the full current-platform packaging flow: checks, GUI build, backend staging, smoke test, and desktop package.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

bash scripts/check.sh
pnpm --dir packages/gui build
python scripts/packaging/package_backend.py --skip-gui-build --version "${PACKAGE_VERSION:-internal}"
bash scripts/packaging/debug_packaged_app.sh --staging-dir build/package/backend-staging
bash scripts/packaging/package_desktop.sh

echo "Backend staging: $ROOT/build/package/backend-staging"
echo "Desktop artifacts: $ROOT/build/package/artifacts/desktop"
