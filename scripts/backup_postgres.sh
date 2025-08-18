#!/usr/bin/env bash
set -euo pipefail

# Postgres backup script
# - Works against a running docker container (default: gas-db from docker-compose.postgres.yml)
# - Outputs gzipped SQL dump with timestamp in ./backups
#
# Usage:
#   bash scripts/backup_postgres.sh [OUTPUT_DIR]
# Env:
#   PG_CONTAINER=gas-db
#   PGUSER=gas PGDATABASE=gas PGPASSWORD=gas_pass
#   FILENAME_PREFIX=db

OUT_DIR=${1:-backups}
PG_CONTAINER=${PG_CONTAINER:-gas-db}
PGUSER=${PGUSER:-gas}
PGDATABASE=${PGDATABASE:-gas}
PGPASSWORD=${PGPASSWORD:-gas_pass}
FILENAME_PREFIX=${FILENAME_PREFIX:-db}

mkdir -p "$OUT_DIR"
ts=$(date +%Y%m%d-%H%M%S)
outfile="$OUT_DIR/${FILENAME_PREFIX}-${ts}.sql.gz"

echo "Backing up Postgres from container=$PG_CONTAINER database=$PGDATABASE user=$PGUSER -> $outfile"
# Use docker exec; requires container running
export PGPASSWORD
if ! docker ps --format '{{.Names}}' | grep -q "^${PG_CONTAINER}$"; then
  echo "ERROR: container ${PG_CONTAINER} not running" >&2
  exit 1
fi

docker exec -e PGPASSWORD="$PGPASSWORD" -i "$PG_CONTAINER" \
  pg_dump -U "$PGUSER" -d "$PGDATABASE" | gzip -c > "$outfile"

echo "Done: $outfile"

