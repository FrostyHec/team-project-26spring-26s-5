#!/usr/bin/env bash
# 功能：清理本地打包产物和打包缓存，可选清理桌面依赖与用户运行时配置。 # nosemgrep
# Purpose: Clear local packaging outputs and caches, with optional desktop deps and runtime config cleanup.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REMOVE_DESKTOP_DEPS=0
REMOVE_RUNTIME_CONFIG=0

usage() {
  cat <<'EOF'
Usage: scripts/packaging/clear_package_build.sh [--desktop-deps] [--runtime-config]

Clears package build outputs and packaging caches.

Default removals:
  - build/package
  - legacy .nonpublic/build/package
  - packages/desktop/dist

Options:
  --desktop-deps     Also remove packages/desktop/node_modules.
  --runtime-config  Also remove ~/.config/react-agent-desktop.
  -h, --help        Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --desktop-deps)
      REMOVE_DESKTOP_DEPS=1
      shift
      ;;
    --runtime-config)
      REMOVE_RUNTIME_CONFIG=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

remove_path() {
  local target="$1"
  if [[ -e "$target" || -L "$target" ]]; then
    rm -rf "$target"
    echo "Removed: $target"
  else
    echo "Already clean: $target"
  fi
}

remove_path "$ROOT/build/package"
remove_path "$ROOT/.nonpublic/build/package"
remove_path "$ROOT/packages/desktop/dist"

if [[ "$REMOVE_DESKTOP_DEPS" -eq 1 ]]; then
  remove_path "$ROOT/packages/desktop/node_modules"
fi

if [[ "$REMOVE_RUNTIME_CONFIG" -eq 1 ]]; then
  remove_path "$HOME/.config/react-agent-desktop"
fi

echo "Package build cleanup complete."
