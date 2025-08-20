# Local Dev Workflow (Git + Docker + Registries)

PowerShell one-command workflow to:
- Initialize or update local git repo (SSH remote)
- Push code to origin
- Build local Docker image
- (Optional) Push image to GHCR and/or Docker Hub
- Restart local container with the new image

## Script
- `scripts/workflow.ps1` (Windows PowerShell)
- Requires: git, docker on PATH

## Typical Usage

First-time init (create repo and push initial commit):
```powershell
scripts\workflow.ps1 -GitSshUrl git@github.com:org/repo.git -InitRepo -Branch main -BuildLocalImage -Push
```

Daily flow (commit/push/build/restart):
```powershell
scripts\workflow.ps1 -Push -BuildLocalImage -LocalImageTag gas-local:dev
```

Push image to GHCR:
```powershell
scripts\workflow.ps1 -Push -BuildLocalImage -PushGHCR -GhcrUser <gh_user> -GhcrToken <gh_pat> -GhcrImage ghcr.io/org/repo
```

Push image to Docker Hub:
```powershell
scripts\workflow.ps1 -Push -BuildLocalImage -PushDockerHub -DockerHubUser <dh_user> -DockerHubPassword <dh_pwd> -DockerHubImage <dh_user>/<repo>
```

Restart local container only (reuse existing local image):
```powershell
scripts\workflow.ps1 -BuildLocalImage:$false -Push:$false
```

## What it does
1) Git
- If `-InitRepo` or no .git exists: `git init`, add remote (SSH), first commit, push
- If working tree has changes: auto-commit with timestamp and push (if `-Push`)

2) Build
- `docker build -t <LocalImageTag> .`

3) Registries
- GHCR: `docker login ghcr.io`, tag as `:latest` and `:<short-sha>`, push both
- Docker Hub: `docker login`, tag/push `:latest` and `:<short-sha>`

4) Run
- Calls `scripts/start.ps1 -NoBuild` to restart local container with mounted volumes and health check

## Conventions
- App listens on container port 8000 (mapped to `-Port` on host)
- Health endpoint: `/health`
- Volumes: `uploads/`, `exports/`, `data/grade_analysis.db`, `static/`

## Notes
- For non-Windows, adapt these scripts into bash (optional next step)
- Ensure your SSH keys are loaded to push to the remote
- PAT scopes: GHCR needs packages:write, Docker Hub needs account login

