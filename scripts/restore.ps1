param([Parameter(Mandatory = $true)][string]$Stamp)
$src = Join-Path "backups" $Stamp
if (-not (Test-Path $src)) { throw "backup not found: $src" }
if (Test-Path (Join-Path $src "data")) {
    Copy-Item -Recurse -Force (Join-Path $src "data") "data"
}
Write-Output "restored $Stamp"
