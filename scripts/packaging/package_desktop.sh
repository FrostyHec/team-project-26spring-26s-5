#!/usr/bin/env bash
# 功能：基于已生成的 backend staging 调用 Electron Builder 构建当前平台桌面发行包。 # nosemgrep
# Purpose: Build the current-platform desktop distribution with Electron Builder from an existing backend staging directory.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT/packages/desktop"

export PACKAGE_VERSION="${PACKAGE_VERSION:-internal}"
DESKTOP_APP_VERSION="${DESKTOP_APP_VERSION:-0.0.0-internal}"
ORIGINAL_PACKAGE_JSON="$(mktemp)"
cp package.json "$ORIGINAL_PACKAGE_JSON"
cleanup() {
  cp "$ORIGINAL_PACKAGE_JSON" package.json
  rm -f "$ORIGINAL_PACKAGE_JSON"
}
trap cleanup EXIT

pnpm install --no-frozen-lockfile

pnpm run build:main

DESKTOP_APP_VERSION="$DESKTOP_APP_VERSION" node - <<'NODE'
const fs = require('node:fs')
const version = process.env.DESKTOP_APP_VERSION
if (!version) {
  throw new Error('DESKTOP_APP_VERSION is required')
}
if (!/^\d+\.\d+\.\d+([-.][0-9A-Za-z.-]+)?$/.test(version)) {
  throw new Error(`Invalid DESKTOP_APP_VERSION: ${version}`)
}
const packagePath = 'package.json'
const pkg = JSON.parse(fs.readFileSync(packagePath, 'utf8'))
pkg.version = version
pkg.packageManager = process.env.DESKTOP_PACKAGE_MANAGER || 'traversal'
fs.writeFileSync(packagePath, `${JSON.stringify(pkg, null, 2)}\n`)
NODE

./node_modules/.bin/electron-builder --publish never

echo "Desktop artifacts: $ROOT/build/package/artifacts/desktop"
