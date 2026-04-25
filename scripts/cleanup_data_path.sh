#!/usr/bin/env bash
set -euo pipefail

# Usage:
#  ./scripts/cleanup_data_path.sh [env-file]
# Defaults to reading DATA_PATH from .env in the repo root.

ENV_FILE="${1:-.env}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

resolve_abs() {
  if command -v realpath >/dev/null 2>&1; then
    realpath "$1"
  else
    readlink -f "$1"
  fi
}

if [ ! -f "$ENV_FILE" ]; then
  echo "Env file '$ENV_FILE' not found." >&2
  exit 1
fi

DATA_PATH_LINE=$(grep -E '^[[:space:]]*DATA_PATH=' "$ENV_FILE" || true)
if [ -z "$DATA_PATH_LINE" ]; then
  echo "DATA_PATH not set in $ENV_FILE" >&2
  exit 1
fi

DATA_PATH=${DATA_PATH_LINE#*=}
# strip surrounding double and single quotes, then trim
DATA_PATH=${DATA_PATH#\"}
DATA_PATH=${DATA_PATH%\"}
DATA_PATH=${DATA_PATH#\'}
DATA_PATH=${DATA_PATH%\'}
DATA_PATH=$(printf '%s' "$DATA_PATH" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')

if [ -z "$DATA_PATH" ]; then
  echo "DATA_PATH empty after parsing $ENV_FILE" >&2
  exit 1
fi

CANDIDATES=()
if [[ "$DATA_PATH" = /* ]]; then
  CANDIDATES+=("$DATA_PATH")
else
  CANDIDATES+=("$REPO_ROOT/$DATA_PATH" "$REPO_ROOT/packages/cli/$DATA_PATH" "$REPO_ROOT/packages/core/$DATA_PATH")
fi

EXISTING=()
for p in "${CANDIDATES[@]}"; do
  if [ -e "$p" ]; then
    EXISTING+=("$p")
  fi
done

if [ ${#EXISTING[@]} -eq 0 ]; then
  echo "No matching paths found to delete for DATA_PATH='$DATA_PATH'."
  exit 0
fi

echo "The following root paths will be deleted (showing roots only):"
for d in "${EXISTING[@]}"; do
  if [ -d "$d" ]; then
    COUNT=$(find "$d" -mindepth 1 -printf '.' | wc -c || true)
  else
    COUNT=1
  fi

  echo
  echo "--- Path: $d ---"
  echo "file://$(resolve_abs "$d")"
  echo "Items to be removed: $COUNT"
done

read -r -p "Type 'yes' to confirm deletion of the above paths and all their contents: " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
  echo "Aborted by user. No changes made."
  exit 1
fi

for d in "${EXISTING[@]}"; do
  rm -rf -- "$d"
  echo "Deleted: $d"
done

echo "Cleanup complete."
