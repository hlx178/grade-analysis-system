#!/usr/bin/env bash
# Full local dev workflow (Linux/macOS)
# - git init/commit/push (SSH)
# - docker build
# - optional push to GHCR/DockerHub
# - restart local container with new image

set -euo pipefail

GIT_SSH_URL=""         # git@github.com:org/repo.git
BRANCH="main"
INIT_REPO=0
PUSH_CODE=1

CONTAINER_NAME="gas-local"
PORT=8001
ADMIN_PASSWORD="123456"

BUILD_LOCAL=1
LOCAL_IMAGE_TAG="gas-local:dev"

PUSH_GHCR=0
GHCR_IMAGE=""          # ghcr.io/org/repo
GHCR_USER=""
GHCR_TOKEN=""

PUSH_DH=0
DH_IMAGE=""            # user/repo
DH_USER=""
DH_PASSWORD=""

OPEN_BROWSER=1

log(){ printf "[INFO] %s\n" "$*"; }
warn(){ printf "[WARN] %s\n" "$*"; }
err(){ printf "[ERROR] %s\n" "$*" 1>&2; }

die(){ err "$*"; exit 1; }

# parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --git-ssh-url) GIT_SSH_URL="$2"; shift 2;;
    --branch) BRANCH="$2"; shift 2;;
    --init-repo) INIT_REPO=1; shift;;
    --no-push) PUSH_CODE=0; shift;;
    --container-name) CONTAINER_NAME="$2"; shift 2;;
    --port) PORT="$2"; shift 2;;
    --admin-password) ADMIN_PASSWORD="$2"; shift 2;;
    --no-build) BUILD_LOCAL=0; shift;;
    --image-tag) LOCAL_IMAGE_TAG="$2"; shift 2;;
    --push-ghcr) PUSH_GHCR=1; shift;;
    --ghcr-image) GHCR_IMAGE="$2"; shift 2;;
    --ghcr-user) GHCR_USER="$2"; shift 2;;
    --ghcr-token) GHCR_TOKEN="$2"; shift 2;;
    --push-dh) PUSH_DH=1; shift;;
    --dh-image) DH_IMAGE="$2"; shift 2;;
    --dh-user) DH_USER="$2"; shift 2;;
    --dh-password) DH_PASSWORD="$2"; shift 2;;
    --no-open-browser) OPEN_BROWSER=0; shift;;
    -h|--help)
      cat <<EOF
Usage: scripts/workflow.sh [options]
  --git-ssh-url URL          SSH remote url (git@github.com:org/repo.git)
  --branch BRANCH            Branch (default: main)
  --init-repo                Initialize repo if .git missing
  --no-push                  Do not push code

  --container-name NAME      Local container name (default: gas-local)
  --port PORT                Host port (default: 8001)
  --admin-password PASS      Initial admin password

  --no-build                 Skip docker build
  --image-tag TAG            Local image tag (default: gas-local:dev)

  --push-ghcr                Push to GHCR
  --ghcr-image IMAGE         ex: ghcr.io/org/repo
  --ghcr-user USER           GHCR username
  --ghcr-token TOKEN         GHCR PAT (packages:write)

  --push-dh                  Push to Docker Hub
  --dh-image IMAGE           ex: user/repo
  --dh-user USER             Docker Hub user
  --dh-password PASS         Docker Hub password

  --no-open-browser          Do not open browser
EOF
      exit 0;;
    *) die "Unknown arg: $1";;
  esac
done

# resolve repo
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$REPO_ROOT"
log "Repo root: $REPO_ROOT"

command -v git >/dev/null || die "git not found"
command -v docker >/dev/null || die "docker not found"

# git init
if [[ $INIT_REPO -eq 1 || ! -d .git ]]; then
  [[ -n "$GIT_SSH_URL" ]] || die "--git-ssh-url required for init"
  log "Initializing git repo..."
  git init
  git add .
  git commit -m "chore: init"
  git branch -M "$BRANCH" || true
  if ! git remote | grep -q '^origin$'; then git remote add origin "$GIT_SSH_URL"; fi
  git push -u origin "$BRANCH"
fi

# ensure origin
if [[ -n "$GIT_SSH_URL" ]] && ! git remote get-url origin >/dev/null 2>&1; then
  git remote add origin "$GIT_SSH_URL"
fi

# commit changes if any
if [[ -n "$(git status --porcelain)" ]]; then
  log "Committing local changes..."
  git add -A
  git commit -m "chore: workflow auto-commit $(date '+%Y-%m-%d %H:%M:%S')"
fi

SHA=$(git rev-parse --short HEAD)

# push code
if [[ $PUSH_CODE -eq 1 ]]; then
  log "Pushing to origin/$BRANCH ..."
  git push origin "$BRANCH"
fi

# build local image
if [[ $BUILD_LOCAL -eq 1 ]]; then
  log "Building local image: $LOCAL_IMAGE_TAG"
  docker build -t "$LOCAL_IMAGE_TAG" .
fi

# GHCR push
if [[ $PUSH_GHCR -eq 1 ]]; then
  [[ -n "$GHCR_IMAGE" ]] || {
    # infer from ssh url if possible
    ORG_REPO=$(echo "$GIT_SSH_URL" | sed -E 's#.*:([^/]+/[^.]+)(\.git)?$#\1#')
    [[ -n "$ORG_REPO" ]] || die "--ghcr-image required if cannot infer org/repo"
    GHCR_IMAGE="ghcr.io/$ORG_REPO"
  }
  [[ -n "$GHCR_USER" && -n "$GHCR_TOKEN" ]] || die "--ghcr-user/--ghcr-token required"
  log "Login GHCR as $GHCR_USER"
  echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USER" --password-stdin >/dev/null
  docker tag "$LOCAL_IMAGE_TAG" "$GHCR_IMAGE:$SHA"
  docker tag "$LOCAL_IMAGE_TAG" "$GHCR_IMAGE:latest"
  log "Pushing $GHCR_IMAGE:$SHA and :latest"
  docker push "$GHCR_IMAGE:$SHA"
  docker push "$GHCR_IMAGE:latest"
fi

# Docker Hub push
if [[ $PUSH_DH -eq 1 ]]; then
  [[ -n "$DH_IMAGE" ]] || {
    REPO_ONLY=$(echo "$GIT_SSH_URL" | sed -E 's#.*:([^/]+)/(.*)\.git#\2#')
    [[ -n "$DH_USER" && -n "$REPO_ONLY" ]] || die "--dh-image required if cannot infer user/repo"
    DH_IMAGE="$DH_USER/$REPO_ONLY"
  }
  [[ -n "$DH_USER" && -n "$DH_PASSWORD" ]] || die "--dh-user/--dh-password required"
  log "Login Docker Hub as $DH_USER"
  echo "$DH_PASSWORD" | docker login -u "$DH_USER" --password-stdin >/dev/null
  docker tag "$LOCAL_IMAGE_TAG" "$DH_IMAGE:$SHA"
  docker tag "$LOCAL_IMAGE_TAG" "$DH_IMAGE:latest"
  log "Pushing $DH_IMAGE:$SHA and :latest"
  docker push "$DH_IMAGE:$SHA"
  docker push "$DH_IMAGE:latest"
fi

# restart container (reuse start.sh)
"$SCRIPT_DIR/start.sh" --container-name "$CONTAINER_NAME" --image-tag "$LOCAL_IMAGE_TAG" --port "$PORT" --admin-password "$ADMIN_PASSWORD" --no-build $([[ $OPEN_BROWSER -eq 1 ]] || echo "--no-open-browser")

log "Workflow completed."

