# Scripts

## Dev stack (PG + Redis + App)

- Start: `scripts/dev.ps1 up`
- Stop: `scripts/dev.ps1 down`
- Custom port: in PowerShell, set `$env:DEV_PORT='8010'` then run `scripts/dev.ps1 up`

## SQLite -> PostgreSQL migration

1. Ensure dev stack is up (`scripts/dev.ps1 up`)
2. Put your SQLite file at `data/grade_analysis.db` or set env `SOURCE_SQLITE=...`
3. Run migration inside app container:

```
docker compose -f docker-compose.dev.yml exec gas python scripts/migrate_sqlite_to_pg.py
```

This performs idempotent copy per table, respects FKs order, and adjusts sequences.

# One-click local run for Grade Analysis System (Windows)

PowerShell script to build and run the app in Docker with sensible volumes and an automatic health check.

## Prerequisites
- Windows 10/11 with PowerShell
- Docker Desktop installed and running (CLI `docker` on PATH)

## Usage
From the repo root:

```powershell
scripts\start.ps1
```

Options:

```powershell
scripts\start.ps1 -ContainerName gas-local -ImageTag gas-local:dev -Port 8001 -AdminPassword 123456 -NoBuild:$false -OpenBrowser:$true
```

- ContainerName: docker container name
- ImageTag: image tag to build/run
- Port: host port to expose the app (container listens on 8000)
- AdminPassword: initial admin password for first-time login
- NoBuild: skip docker build if you already built the image
- OpenBrowser: open app in default browser once healthy

Mounts created automatically:
- uploads/ -> /app/uploads
- exports/ -> /app/exports
- data/grade_analysis.db -> /app/grade_analysis.db (created if missing)
- static/ -> /app/app/static

## Health check
The script polls GET /health (HTTP 200) up to ~30 seconds, and shows last logs if unhealthy.

## Notes
- If you change code, re-run `scripts\start.ps1` (without `-NoBuild`) to rebuild the image.
- If the port is in use, pass a different `-Port`.
- You can stop and remove the container with: `docker rm -f gas-local`.

