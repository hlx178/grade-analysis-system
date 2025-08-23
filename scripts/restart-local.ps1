param(
  [string]$ComposeFiles = "docker-compose.yml",
  [switch]$PruneOrphans
)

$ErrorActionPreference = "Stop"

# Build -f args array
$files = $ComposeFiles.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' }
$composeArgs = @()
foreach ($f in $files) { $composeArgs += @('-f', $f) }

Write-Host "[compose] pull ($ComposeFiles)"
docker compose @composeArgs pull

Write-Host "[compose] up -d ($ComposeFiles)"
$upArgs = @('up','-d')
if ($PruneOrphans) { $upArgs += '--remove-orphans' }

docker compose @composeArgs @upArgs

Write-Host "Done."
