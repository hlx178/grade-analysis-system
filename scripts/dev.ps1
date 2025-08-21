param(
  [ValidateSet('up','down')][string]$cmd = 'up'
)

if ($cmd -eq 'up') {
  Write-Host '[INFO] Starting dev stack (PG+Redis+App)' -ForegroundColor Cyan
  docker compose -f docker-compose.dev.yml up -d
  if ($LASTEXITCODE -ne 0) { Write-Host '[ERROR] compose up failed' -ForegroundColor Red; exit 1 }
  Write-Host '[INFO] Waiting for app ready...' -ForegroundColor Cyan
  for ($i=0; $i -lt 60; $i++) {
    try { $code = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://localhost:8001/ready).StatusCode; if ($code -eq 200) { break } } catch { Start-Sleep -Seconds 2 }
  }
  Write-Host '[INFO] Dev stack ready at http://localhost:8001' -ForegroundColor Green
} else {
  Write-Host '[INFO] Stopping dev stack' -ForegroundColor Yellow
  docker compose -f docker-compose.dev.yml down
}

