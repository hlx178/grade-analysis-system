param(
  [string]$Tag = "latest",
  [string]$Registry = "ghcr.io",
  [string]$Namespace = "hlx178",
  [string]$ImageName = "grade-analysis"
)

$ErrorActionPreference = "Stop"

# Compute full image (use ${} to avoid ':' parsing issues)
$FullImage = "${Registry}/${Namespace}/${ImageName}:${Tag}"

Write-Host "[build] Image => $FullImage"

# Build with Dockerfile in repo root
 docker build -t $FullImage .

Write-Host "[push] $FullImage"
 docker push $FullImage

Write-Host "Done."
