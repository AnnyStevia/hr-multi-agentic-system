# Free HR platform dev ports (frontend 3000, backend 8000) and related orphans.
# Usage (from repo root):
#   .\scripts\dev-stop.ps1
#   .\scripts\dev-stop.ps1 -ClearNextCache

param(
  [switch]$ClearNextCache
)

$ErrorActionPreference = "SilentlyContinue"
$Root = Split-Path -Parent $PSScriptRoot
$Ports = @(3000, 8000)
$ProjectMarker = "HR-Multi-Agentic-System-Last-Year-Project"

function Stop-ByPort([int]$Port) {
  $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  if (-not $conns) {
    Write-Host "Port ${Port}: already free"
    return
  }
  foreach ($conn in $conns) {
    $procId = $conn.OwningProcess
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$procId"
    Write-Host "Stopping PID $procId on port ${Port}"
    if ($proc.CommandLine) {
      Write-Host "  $($proc.CommandLine.Substring(0, [Math]::Min(140, $proc.CommandLine.Length)))"
    }
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
  }
}

function Stop-ProjectOrphans {
  Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and $_.CommandLine -match [regex]::Escape($ProjectMarker) -and (
      $_.CommandLine -match 'next(\.js|\s|\\)|"next"|uvicorn|npm run dev'
    )
  } | ForEach-Object {
    Write-Host "Stopping orphan PID $($_.ProcessId)"
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  }
}

Write-Host "Stopping HR platform dev servers..."
foreach ($port in $Ports) { Stop-ByPort $port }
Stop-ProjectOrphans
Start-Sleep -Seconds 1

# Kill child watchers that sometimes keep the port after parent dies
foreach ($port in $Ports) { Stop-ByPort $port }

if ($ClearNextCache) {
  $nextDir = Join-Path $Root "frontend\.next"
  if (Test-Path $nextDir) {
    Remove-Item -Recurse -Force $nextDir
    Write-Host "Cleared frontend\.next"
  } else {
    Write-Host "No frontend\.next to clear"
  }
}

Write-Host "Done. Ports 3000 and 8000 should be free."
