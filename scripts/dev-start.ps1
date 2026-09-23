# Stop any stale servers, then start backend + frontend for local dev.
# Usage (from repo root):
#   .\scripts\dev-start.ps1
#   .\scripts\dev-start.ps1 -ClearNextCache

param(
  [switch]$ClearNextCache
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$StopScript = Join-Path $PSScriptRoot "dev-stop.ps1"

if ($ClearNextCache) {
  & $StopScript -ClearNextCache
} else {
  & $StopScript
}

$backend = Join-Path $Root "backend"
$frontend = Join-Path $Root "frontend"
$uvicorn = Join-Path $backend ".venv\Scripts\uvicorn.exe"

if (-not (Test-Path $uvicorn)) {
  throw "Backend venv missing: $uvicorn"
}

Write-Host "Starting backend on http://127.0.0.1:8000 ..."
Start-Process -FilePath $uvicorn -ArgumentList @(
  "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000"
) -WorkingDirectory $backend -WindowStyle Minimized

Write-Host "Starting frontend on http://localhost:3000 ..."
Start-Process -FilePath "npm" -ArgumentList @("run", "dev") -WorkingDirectory $frontend -WindowStyle Minimized

Write-Host ""
Write-Host "Started in separate windows (minimized)."
Write-Host "  Backend:  http://127.0.0.1:8000"
Write-Host "  Frontend: http://localhost:3000"
Write-Host "To stop later: .\scripts\dev-stop.ps1"
