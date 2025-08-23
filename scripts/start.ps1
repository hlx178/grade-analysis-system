param(
  [string]$ContainerName = 'gas-local',
  [string]$ImageTag = 'gas-local:dev',
  [int]$Port = 8001,
  [string]$AdminPassword = '123456',
  [switch]$NoBuild = $false,
  [switch]$OpenBrowser = $true
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Info($msg){ Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Warn($msg){ Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg){ Write-Host "[ERROR] $msg" -ForegroundColor Red }

# Resolve project root (directory of this script -> repo root)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir '..')
Set-Location $RepoRoot
Write-Info "Repo root: $RepoRoot"

# Check Docker
try {
  docker --version | Out-Null
} catch {
  Write-Err "Docker CLI not found. Please install Docker Desktop and ensure 'docker' is in PATH."; exit 1
}

# Ensure data directories exist
$uploads = Join-Path $RepoRoot 'uploads'
$exports = Join-Path $RepoRoot 'exports'
$dataDir = Join-Path $RepoRoot 'data'
$staticDir = Join-Path $RepoRoot 'static'
$null = New-Item -ItemType Directory -Force -Path $uploads,$exports,$dataDir,$staticDir | Out-Null

# Ensure DB file exists (file mount on Windows works best when file pre-exists)
$dbFile = Join-Path $dataDir 'grade_analysis.db'
if (-not (Test-Path $dbFile)) { New-Item -ItemType File -Path $dbFile | Out-Null }

# Build image
if (-not $NoBuild) {
  Write-Info "Building Docker image: $ImageTag"
  docker build -t $ImageTag .
}

# Stop existing container
$existing = (docker ps -a --format '{{.Names}}' | Where-Object { $_ -eq $ContainerName })
if ($existing) {
  Write-Warn "Container '$ContainerName' exists; removing..."
  docker rm -f $ContainerName | Out-Null
}

# Run container
Write-Info "Starting container '$ContainerName' on http://localhost:$Port ..."
if (-not $Port -or $Port -le 0) { Write-Err "Invalid Port '$Port'"; exit 1 }
$portMap = ("{0}:{1}" -f $Port, 8000)
$runArgs = @(
  'run','--name', $ContainerName,
  '-p', $portMap,
  '-e','FLASK_CONFIG=production',
  '-e',("ADMIN_INITIAL_PASSWORD={0}" -f $AdminPassword),
  '-v',("{0}:/app/uploads" -f $uploads),
  '-v',("{0}:/app/exports" -f $exports),
  '-v',("{0}:/app/grade_analysis.db" -f $dbFile),
  '-v',("{0}:/app/app/static" -f $staticDir),
  '-d', $ImageTag
)
Write-Info ("docker " + ($runArgs -join ' '))
$containerId = & docker @runArgs
if ($LASTEXITCODE -ne 0) { Write-Err "Failed to start container"; exit 1 }

# Health check
$healthUrl = "http://localhost:$Port/health"
Write-Info "Waiting for service healthy: $healthUrl"
$ok = $false
for ($i=1; $i -le 30; $i++) {
  try {
    $status = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 $healthUrl).StatusCode
    if ($status -eq 200) { $ok = $true; break }
  } catch { Start-Sleep -Seconds 1 }
}
if (-not $ok) {
  Write-Err "Service did not become healthy in time. Showing last logs:"
  docker logs --tail 100 $ContainerName
  exit 1
}

Write-Host ""; Write-Host "=== Ready ===" -ForegroundColor Green
Write-Host ("URL:        http://localhost:{0}" -f $Port)
Write-Host ("Container:  {0}" -f $ContainerName)
Write-Host ("Image:      {0}" -f $ImageTag)
Write-Host ("Admin Pwd:  {0} (first-time login)" -f $AdminPassword)
Write-Host "Mounts:     uploads/, exports/, data/grade_analysis.db, static/"

if ($OpenBrowser) {
  try { Start-Process ("http://localhost:{0}" -f $Port) } catch {}
}

