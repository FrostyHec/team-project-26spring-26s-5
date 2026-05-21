#!/usr/bin/env bash
# 功能：使用 backend staging 临时启动打包后的后端并检查健康接口、SPA 页面和默认 PDF 访问。 # nosemgrep
# Purpose: Start the packaged backend from staging temporarily and smoke-test health, SPA, and default PDF access.
set -euo pipefail

STAGING_DIR=""
PORT=""
KEEP_RUNNING=0
IN_PLACE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --staging-dir)
      STAGING_DIR="$2"
      shift 2
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    --keep-running)
      KEEP_RUNNING=1
      shift
      ;;
    --in-place)
      IN_PLACE=1
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$STAGING_DIR" ]]; then
  echo "Usage: scripts/packaging/debug_packaged_app.sh --staging-dir <path> [--port <port>] [--keep-running] [--in-place]" >&2
  exit 2
fi

SOURCE_STAGING_DIR="$(cd "$STAGING_DIR" && pwd)"
if [[ "$IN_PLACE" -eq 0 ]]; then
  WORK_ROOT="$(mktemp -d)"
  cp -R "$SOURCE_STAGING_DIR" "$WORK_ROOT/backend-staging"
  STAGING_DIR="$WORK_ROOT/backend-staging"
else
  WORK_ROOT=""
  STAGING_DIR="$SOURCE_STAGING_DIR"
fi
ENV_FILE="$STAGING_DIR/config/.env"
GUI_DIR="$STAGING_DIR/gui"
BACKEND_BIN="$STAGING_DIR/bin/react-agent-backend"
if [[ "$(uname -s)" =~ MINGW|MSYS|CYGWIN ]] && [[ ! -f "$BACKEND_BIN" ]]; then
  BACKEND_BIN="$STAGING_DIR/bin/react-agent-backend.exe"
fi

[[ -x "$BACKEND_BIN" ]] || { echo "Backend binary is missing or not executable: $BACKEND_BIN" >&2; exit 1; }
[[ -f "$ENV_FILE" ]] || { echo "Editable env file is missing: $ENV_FILE" >&2; exit 1; }
[[ -w "$ENV_FILE" ]] || { echo "Env file is not writable: $ENV_FILE" >&2; exit 1; }
[[ -f "$GUI_DIR/index.html" ]] || { echo "GUI index.html is missing: $GUI_DIR/index.html" >&2; exit 1; }
[[ -d "$STAGING_DIR/output/pdfs" ]] || { echo "Default PDF directory is missing: $STAGING_DIR/output/pdfs" >&2; exit 1; }

if [[ -z "$PORT" ]]; then
  PORT="$(python3 - <<'PY'
import socket
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
)"
fi

cleanup() {
  if [[ "${BACKEND_PID:-}" ]]; then
    if [[ "$KEEP_RUNNING" -eq 0 ]]; then
      kill "$BACKEND_PID" >/dev/null 2>&1 || true
      wait "$BACKEND_PID" >/dev/null 2>&1 || true
    else
      echo "Backend left running with PID $BACKEND_PID"
    fi
  fi
  if [[ "$KEEP_RUNNING" -eq 0 && -n "${WORK_ROOT:-}" ]]; then
    rm -rf "$WORK_ROOT"
  fi
}
trap cleanup EXIT

"$BACKEND_BIN" serve \
  --env-file "$ENV_FILE" \
  --host 127.0.0.1 \
  --port "$PORT" \
  --static-dir "$GUI_DIR" &
BACKEND_PID=$!

BASE_URL="http://127.0.0.1:$PORT"
for _ in $(seq 1 60); do
  if curl -fsS "$BASE_URL/api/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

curl -fsS "$BASE_URL/api/health" >/dev/null
curl -fsS "$BASE_URL/" >/dev/null
curl -fsS "$BASE_URL/settings" >/dev/null

FIRST_PDF="$(find "$STAGING_DIR/output/pdfs" -maxdepth 1 -type f -name '*.pdf' | head -n 1 || true)"
if [[ -n "$FIRST_PDF" ]]; then
  PDF_NAME="$(basename "$FIRST_PDF")"
  PDF_URL_NAME="$(PDF_NAME="$PDF_NAME" python3 - <<'PY'
import os
from urllib.parse import quote

print(quote(os.environ["PDF_NAME"]))
PY
)"
  curl -fsS "$BASE_URL/files/pdfs/$PDF_URL_NAME" >/dev/null
else
  echo "warning: no bundled PDF found under output/pdfs; skipping PDF route check" >&2
fi

echo "Packaged backend smoke check passed: $BASE_URL"
