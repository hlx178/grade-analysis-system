param(
  [ValidateSet('up','down')][string]$cmd = 'up',
  [int]$Port
)

if ($cmd -eq 'up') {
  if ($Port) { $env:DEV_PORT = "$Port" }
  $p = if ($env:DEV_PORT) { $env:DEV_PORT } else { '8001' }
  Write-Host ("[INFO] Starting dev stack (PG+Redis+App) on http://localhost:{0}" -f $p) -ForegroundColor Cyan
  # Always rebuild local app image to pick up code changes baked into gas-local:dev
  docker compose -f docker-compose.dev.yml build app
  if ($LASTEXITCODE -ne 0) { Write-Host '[ERROR] compose build failed' -ForegroundColor Red; exit 1 }
  docker compose -f docker-compose.dev.yml up -d
  if ($LASTEXITCODE -ne 0) { Write-Host '[ERROR] compose up failed' -ForegroundColor Red; exit 1 }
  Write-Host '[INFO] Waiting for app ready...' -ForegroundColor Cyan
  for ($i=0; $i -lt 60; $i++) {
    try { $code = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 ("http://localhost:{0}/ready" -f $p)).StatusCode; if ($code -eq 200) { break } } catch { Start-Sleep -Seconds 2 }
  }
  Write-Host ("[INFO] Dev stack ready at http://localhost:{0}" -f $p) -ForegroundColor Green
} else {
  Write-Host '[INFO] Stopping dev stack' -ForegroundColor Yellow
  docker compose -f docker-compose.dev.yml down
}

