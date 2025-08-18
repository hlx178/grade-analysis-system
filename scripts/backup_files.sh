#!/usr/bin/env bash
set -euo pipefail

# Backup uploads/ and exports/ directories
# Usage: bash scripts/backup_files.sh [OUTPUT_DIR]

OUT_DIR=${1:-backups}
SRC_DIRS=(uploads exports)

mkdir -p "$OUT_DIR"
ts=$(date +%Y%m%d-%H%M%S)
outfile="$OUT_DIR/files-$ts.tar.gz"

echo "Backing up ${SRC_DIRS[*]} -> $outfile"

tar -czf "$outfile" "${SRC_DIRS[@]}" 2>/dev/null || {
  echo "WARN: some sources may be missing; created archive if any existed"
}

echo "Done: $outfile"

