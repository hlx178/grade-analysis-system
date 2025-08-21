param(
  [switch]$DevCompose,
  [switch]$Up,
  [switch]$Down
)

if ($DevCompose) {
  if ($Up) {
    Write-Host "[INFO] Starting dev stack (PG + Redis + App) via docker-compose.dev.yml" -ForegroundColor Cyan
    docker compose -f docker-compose.dev.yml up -d
    if ($LASTEXITCODE -ne 0) { Write-Host "[ERROR] compose up failed" -ForegroundColor Red; exit 1 }
    Write-Host "[INFO] Waiting for app ready..." -ForegroundColor Cyan
    for ($i=0; $i -lt 60; $i++) {
      try { $code = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://localhost:8001/ready).StatusCode; if ($code -eq 200) { break } } catch { Start-Sleep -Seconds 2 }
    }
    Write-Host "[INFO] Dev stack ready at http://localhost:8001" -ForegroundColor Green
    exit 0
  }
  if ($Down) {
    Write-Host "[INFO] Stopping dev stack" -ForegroundColor Yellow
    docker compose -f docker-compose.dev.yml down
    exit 0
  }
}

param(
  [string]$GitSshUrl = '',                # e.g. git@github.com:org/repo.git
  [string]$Branch = 'main',
  [switch]$InitRepo = $false,             # init repo if .git missing
  [switch]$Push = $true,                  # push code to origin

  [string]$ContainerName = 'gas-local',
  [int]$Port = 8001,
  [string]$AdminPassword = '123456',

  [switch]$BuildLocalImage = $true,
  [string]$LocalImageTag = 'gas-local:dev',

  [switch]$PushGHCR = $false,
  [string]$GhcrImage = '',                # e.g. ghcr.io/org/repo
  [string]$GhcrUser = '',
  [string]$GhcrToken = '',                # PAT with packages:write

  [switch]$PushDockerHub = $false,
  [string]$DockerHubImage = '',           # e.g. username/repo
  [string]$DockerHubUser = '',
  [string]$DockerHubPassword = '',

  [switch]$OpenBrowser = $true
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Info($m){ Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Warn($m){ Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Err($m){ Write-Host "[ERROR] $m" -ForegroundColor Red }

# Resolve repo root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir '..')
Set-Location $RepoRoot
Info "Repo root: $RepoRoot"

# tools check
try { git --version | Out-Null } catch { Err 'git not found on PATH'; exit 1 }
try { docker --version | Out-Null } catch { Err 'docker not found on PATH'; exit 1 }

# init repo if needed
$gitDir = Join-Path $RepoRoot '.git'
if ($InitRepo -or -not (Test-Path $gitDir)) {
  if (-not $GitSshUrl) { Err 'GitSshUrl is required for repo initialization'; exit 1 }
  Info 'Initializing git repository...'
  git init
  git add .
  git commit -m "chore: init"
  try { git branch -M $Branch } catch { }
  $hasOrigin = git remote | Select-String -Pattern '^origin$' -Quiet
  if (-not $hasOrigin) { git remote add origin $GitSshUrl }
  Info 'Pushing initial commit...'
  git push -u origin $Branch
}

# ensure remote exists
if ($GitSshUrl) {
  $cfg = git remote get-url origin 2>$null
  if (-not $cfg) { git remote add origin $GitSshUrl }
}

# stage/commit (if there are changes)
$changes = git status --porcelain
if ($changes) {
  Info 'Staging and committing changes...'
  git add -A
  $msg = "chore: workflow auto-commit $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
  git commit -m $msg
}

# current sha
$sha = (git rev-parse --short HEAD).Trim()
$tsTag = (Get-Date -Format 'yyyyMMdd-HHmmss')

# push code
if ($Push) {
  Info "Pushing to origin/$Branch ..."
  git push origin $Branch
}

# build local image
if ($BuildLocalImage) {
  Info "Building local image: $LocalImageTag"
  docker build -t $LocalImageTag .
}

# derive repo name from SSH url if needed
function Parse-OrgRepoFromSsh($url){
  # git@github.com:org/repo.git -> org/repo
  if (-not $url) { return $null }
  $m = [regex]::Match($url, ':[^/]+/(.+?)(?:\.git)?$')
  if ($m.Success) { return $m.Groups[1].Value }
  return $null
}
$orgRepo = Parse-OrgRepoFromSsh $GitSshUrl

# push to GHCR
if ($PushGHCR) {
  if (-not $GhcrImage) {
    if (-not $orgRepo) { Err 'GhcrImage not set and cannot infer from GitSshUrl'; exit 1 }
    $GhcrImage = "ghcr.io/$orgRepo"
  }
  if (-not $GhcrUser -or -not $GhcrToken) { Err 'GhcrUser/GhcrToken required for GHCR'; exit 1 }
  Info "Login GHCR as $GhcrUser"
  docker login ghcr.io -u $GhcrUser -p $GhcrToken | Out-Null
  $ver = "$(($GhcrImage)):$sha"
  $latest = "$(($GhcrImage)):latest"
  Info "Tagging $LocalImageTag -> $ver, $latest"
  docker tag $LocalImageTag $ver
  docker tag $LocalImageTag $latest
  Info "Pushing $ver ..."; docker push $ver
  Info "Pushing $latest ..."; docker push $latest
}

# push to Docker Hub
if ($PushDockerHub) {
  if (-not $DockerHubImage) {
    if (-not $orgRepo) { Err 'DockerHubImage not set and cannot infer from GitSshUrl'; exit 1 }
    # default to <user>/<repo> if possible, else require explicit
    $repoOnly = $orgRepo.Split('/')[-1]
    if (-not $DockerHubUser) { Err 'DockerHubUser required to infer docker hub repo'; exit 1 }
    $DockerHubImage = "$DockerHubUser/$repoOnly"
  }
  if (-not $DockerHubUser -or -not $DockerHubPassword) { Err 'DockerHubUser/Password required for Docker Hub'; exit 1 }
  Info "Login Docker Hub as $DockerHubUser"
  docker login -u $DockerHubUser -p $DockerHubPassword | Out-Null
  $ver = "$(($DockerHubImage)):$sha"
  $latest = "$(($DockerHubImage)):latest"
  Info "Tagging $LocalImageTag -> $ver, $latest"
  docker tag $LocalImageTag $ver
  docker tag $LocalImageTag $latest
  Info "Pushing $ver ..."; docker push $ver
  Info "Pushing $latest ..."; docker push $latest
}

# restart local container with the new local image
Info 'Restarting local container...'
& "$ScriptDir/start.ps1" -ContainerName $ContainerName -ImageTag $LocalImageTag -Port $Port -AdminPassword $AdminPassword -NoBuild:$true -OpenBrowser:$OpenBrowser
if ($LASTEXITCODE -ne 0) { Err 'Failed to restart local container'; exit 1 }

Info 'Workflow completed successfully.'

