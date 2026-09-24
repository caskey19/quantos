$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dest = Join-Path "backups" $stamp
New-Item -ItemType Directory -Force -Path $dest | Out-Null
if (Test-Path "data") { Copy-Item -Recurse "data" (Join-Path $dest "data") }
Write-Output "backup written to $dest"
