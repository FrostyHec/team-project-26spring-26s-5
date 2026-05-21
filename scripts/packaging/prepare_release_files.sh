#!/usr/bin/env bash
# 功能：从 CI 下载的构建产物中筛选最终可分发安装包，避免上传 unpacked 内部文件。 # nosemgrep
# Purpose: Select final distributable installers from downloaded CI artifacts and avoid uploading unpacked internals.
set -euo pipefail

SOURCE_DIR="${1:-release-artifacts}"
DEST_DIR="${2:-release-files}"

if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "Release artifact source directory does not exist: $SOURCE_DIR" >&2
  exit 1
fi

mkdir -p "$DEST_DIR"

SELECTED_LIST="$(mktemp)"
cleanup() {
  rm -f "$SELECTED_LIST"
}
trap cleanup EXIT

while IFS= read -r -d '' file; do
  parent_name="$(basename "$(dirname "$file")")"
  file_name="$(basename "$file")"
  if [[ "$parent_name" != "desktop" ]]; then
    continue
  fi

  case "$file_name" in
    *.AppImage | *.tar.gz | *.exe | *.dmg | *.zip)
      printf '%s\t%s\n' "$file_name" "$file" >> "$SELECTED_LIST"
      ;;
  esac
done < <(find "$SOURCE_DIR" -type f -print0)

if [[ ! -s "$SELECTED_LIST" ]]; then
  echo "No release files found under $SOURCE_DIR." >&2
  echo "Expected top-level desktop artifacts matching: *.AppImage, *.tar.gz, *.exe, *.dmg, *.zip" >&2
  find "$SOURCE_DIR" -maxdepth 6 -type f | sort >&2
  exit 1
fi

DUPLICATE_NAMES="$(cut -f1 "$SELECTED_LIST" | sort | uniq -d)"
if [[ -n "$DUPLICATE_NAMES" ]]; then
  echo "Duplicate release asset file names found. GitHub Release assets use a flat namespace:" >&2
  echo "$DUPLICATE_NAMES" >&2
  exit 1
fi

while IFS=$'\t' read -r file_name file; do
  cp "$file" "$DEST_DIR/$file_name"
done < "$SELECTED_LIST"

echo "Prepared release files:"
find "$DEST_DIR" -maxdepth 1 -type f | sort
