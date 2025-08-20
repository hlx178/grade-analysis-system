#!/usr/bin/env bash
# One-click local run for Grade Analysis System (Linux/macOS)
# Usage examples:
#   scripts/start.sh
#   scripts/start.sh --container-name gas-local --image-tag gas-local:dev --port 8001 --admin-password 123456
#   scripts/start.sh --no-build --no-open-browser

set -euo pipefail

CONTAINER_NAME="gas-local"
IMAGE_TAG="gas-local:dev"
PORT=8001
ADMIN_PASSWORD="123456"
NO_BUILD=0
OPEN_BROWSER=1

log() { printf "[INFO] %s\n" "$*"; }
warn() { printf "[WARN] %s\n" "$*"; }
err() { printf "[ERROR] %s\n" "$*" 1>&2; }

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    -c|--container-name) CONTAINER_NAME="$2"; shift 2;;
    -i|--image-tag) IMAGE_TAG="$2"; shift 2;;
    -p|--port) PORT="$2"; shift 2;;
    --admin-password) ADMIN_PASSWORD="$2"; shift 2;;
    --no-build) NO_BUILD=1; shift;;
    --no-open-browser) OPEN_BROWSER=0; shift;;
    -h|--help)
      cat <<EOF
Usage: scripts/start.sh [options]
  -c|--container-name NAME     Container name (default: gas-local)
  -i|--image-tag TAG           Image tag (default: gas-local:dev)
  -p|--port PORT               Host port to map to container 8000 (default: 8001)
  --admin-password PASS        Initial admin password (default: 123456)
  --no-build                   Skip docker build
  --no-open-browser            Do not open browser after start
EOF
      exit 0;;
    *) err "Unknown arg: $1"; exit 1;;
  esac
done

# Resolve repo root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$REPO_ROOT"
log "Repo root: $REPO_ROOT"

# Checks
command -v docker >/dev/null 2>&1 || { err "docker not found"; exit 1; }
command -v curl >/dev/null 2>&1 || { warn "curl not found; attempting with wget"; }

# Ensure mounts
mkdir -p "$REPO_ROOT/uploads" "$REPO_ROOT/exports" "$REPO_ROOT/data" "$REPO_ROOT/static"
DB_FILE="$REPO_ROOT/data/grade_analysis.db"
[[ -f "$DB_FILE" ]] || : > "$DB_FILE"

# Build image
if [[ "$NO_BUILD" -eq 0 ]]; then
  log "Building docker image: $IMAGE_TAG"
  docker build -t "$IMAGE_TAG" .
fi

# Stop existing container
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  warn "Removing existing container: $CONTAINER_NAME"
  docker rm -f "$CONTAINER_NAME" >/dev/null
fi

# Run
log "Starting container '$CONTAINER_NAME' on http://localhost:$PORT ..."
docker run --name "$CONTAINER_NAME" \
  -p "$PORT:8000" \
  -e FLASK_CONFIG=production \
  -e ADMIN_INITIAL_PASSWORD="$ADMIN_PASSWORD" \
  -v "$REPO_ROOT/uploads:/app/uploads" \
  -v "$REPO_ROOT/exports:/app/exports" \
  -v "$DB_FILE:/app/grade_analysis.db" \
  -v "$REPO_ROOT/static:/app/app/static" \
  -d "$IMAGE_TAG" >/dev/null

# Health check
HEALTH_URL="http://localhost:$PORT/health"
log "Waiting for healthy: $HEALTH_URL"
OK=0
for i in {1..30}; do
  code=""
  if command -v curl >/dev/null 2>&1; then
    code=$(curl -fsS -o /dev/null -w "%{http_code}" "$HEALTH_URL" || true)
  else
    code=$(wget -qO- --server-response "$HEALTH_URL" 2>&1 | awk '/^  HTTP/{print $2; exit}')
  fi
  if [[ "$code" == "200" ]]; then OK=1; break; fi
  sleep 1
done
if [[ "$OK" -ne 1 ]]; then
  err "Service not healthy in time. Showing logs:"; docker logs --tail 100 "$CONTAINER_NAME" || true; exit 1
fi

printf "\n=== Ready ===\nURL:        http://localhost:%s\nContainer:  %s\nImage:      %s\n" "$PORT" "$CONTAINER_NAME" "$IMAGE_TAG"
[[ "$OPEN_BROWSER" -eq 1 ]] && {
  if [[ "$(uname)" == "Darwin" ]]; then open "http://localhost:$PORT" || true; else xdg-open "http://localhost:$PORT" >/dev/null 2>&1 || true; fi
}

