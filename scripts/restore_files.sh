#!/usr/bin/env bash
set -euo pipefail

# Restore uploads/ and exports/ from an archive created by backup_files.sh
# Usage: bash scripts/restore_files.sh <files-YYYYmmdd-HHMMSS.tar.gz>

if [ $# -lt 1 ]; then
  echo "Usage: $0 <archive.tar.gz>" >&2
  exit 1
fi

ARCHIVE=$1
if [ ! -f "$ARCHIVE" ]; then
  echo "ERROR: file not found: $ARCHIVE" >&2
  exit 1
fi

echo "Restoring from $ARCHIVE"

tar -xzf "$ARCHIVE"

echo "Done"

