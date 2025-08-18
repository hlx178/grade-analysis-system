#!/usr/bin/env bash
set -euo pipefail

# Postgres restore script
# - Restores a gzipped SQL dump into a running docker container (default: gas-db)
#
# Usage:
#   bash scripts/restore_postgres.sh <DUMP_FILE.sql.gz>
# Env:
#   PG_CONTAINER=gas-db
#   PGUSER=gas PGDATABASE=gas PGPASSWORD=gas_pass

if [ $# -lt 1 ]; then
  echo "Usage: $0 <dump.sql.gz>" >&2
  exit 1
fi

DUMP_FILE=$1
PG_CONTAINER=${PG_CONTAINER:-gas-db}
PGUSER=${PGUSER:-gas}
PGDATABASE=${PGDATABASE:-gas}
PGPASSWORD=${PGPASSWORD:-gas_pass}

if [ ! -f "$DUMP_FILE" ]; then
  echo "ERROR: file not found: $DUMP_FILE" >&2
  exit 1
fi

if ! docker ps --format '{{.Names}}' | grep -q "^${PG_CONTAINER}$"; then
  echo "ERROR: container ${PG_CONTAINER} not running" >&2
  exit 1
fi

echo "Restoring $DUMP_FILE into container=$PG_CONTAINER database=$PGDATABASE user=$PGUSER"
export PGPASSWORD
zcat "$DUMP_FILE" | docker exec -e PGPASSWORD="$PGPASSWORD" -i "$PG_CONTAINER" psql -U "$PGUSER" -d "$PGDATABASE"

echo "Done"

