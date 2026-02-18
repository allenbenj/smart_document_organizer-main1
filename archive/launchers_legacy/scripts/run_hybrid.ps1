param(
  [string]$WslDistro = "Ubuntu",
  [string]$LinuxProjectPath = "/mnt/e/Project/smart_document_organizer-main",
  [string]$BackendHealthUrl = "http://127.0.0.1:8000/api/health",
  [int]$HealthTimeoutSeconds = 120,
  [switch]$NoGui
)

$ErrorActionPreference = "Stop"

function Step($msg) {
  Write-Host "[+] $msg" -ForegroundColor Cyan
}

function Warn($msg) {
  Write-Host "[!] $msg" -ForegroundColor Yellow
}

function Ok($msg) {
  Write-Host "[OK] $msg" -ForegroundColor Green
}

Step "Hybrid launcher starting"
Write-Host "    Windows CWD: $(Get-Location)"
Write-Host "    WSL distro : $WslDistro"
Write-Host "    Linux path : $LinuxProjectPath"
Write-Host "    Health URL : $BackendHealthUrl"

# 1) Start backend in WSL/Linux
Step "Starting backend in WSL (backend-only mode)"
$startCmd = @"
set -e
cd '$LinuxProjectPath'
mkdir -p logs
# If already running, keep it
if pgrep -f "tools/run_app.py --backend-only" >/dev/null 2>&1; then
  echo "ALREADY_RUNNING"
else
  nohup .venv/bin/python tools/run_app.py --backend-only > logs/backend-wsl.log 2>&1 &
  echo $! > .backend-wsl.pid
  echo "STARTED_PID:$(cat .backend-wsl.pid)"
fi
"@

$startOut = wsl -d $WslDistro bash -lc $startCmd
$startOut | ForEach-Object { Write-Host "    $_" }

# 2) Poll backend health
Step "Waiting for backend health"
$deadline = (Get-Date).AddSeconds($HealthTimeoutSeconds)
$healthy = $false
while ((Get-Date) -lt $deadline) {
  try {
    $resp = Invoke-RestMethod -Uri $BackendHealthUrl -Method Get -TimeoutSec 3
    if ($null -ne $resp) {
      $healthy = $true
      Ok "Backend healthy: $($resp | ConvertTo-Json -Compress)"
      break
    }
  } catch {
    Write-Host "    ...not ready yet"
    Start-Sleep -Milliseconds 1200
  }
}

if (-not $healthy) {
  Warn "Backend did not become healthy in time ($HealthTimeoutSeconds s)."
  Warn "Check Linux logs:"
  Write-Host "    wsl -d $WslDistro bash -lc \"tail -n 120 '$LinuxProjectPath/logs/backend-wsl.log'\""
  exit 1
}

if ($NoGui) {
  Ok "NoGui switch set. Backend is up; exiting launcher."
  Write-Host "    Docs: http://127.0.0.1:8000/docs"
  exit 0
}

# 3) Launch Windows GUI
Step "Launching Windows GUI"
$winPython = Join-Path $PWD ".venv-win\Scripts\python.exe"
if (-not (Test-Path $winPython)) {
  Warn "Windows venv not found at .venv-win"
  Step "Creating .venv-win"
  py -3 -m venv .venv-win
  & .\.venv-win\Scripts\python.exe -m pip install --upgrade pip
  & .\.venv-win\Scripts\python.exe -m pip install -r .\requirements-core.txt
}

# Ensure GUI runtime deps exist for Windows launcher
Step "Ensuring GUI deps in .venv-win"
& .\.venv-win\Scripts\python.exe -m pip install PySide6 requests | Out-Null

Ok "Starting GUI process now"
& .\.venv-win\Scripts\python.exe .\gui\gui_dashboard.py
$guiExit = $LASTEXITCODE

if ($guiExit -ne 0) {
  Warn "GUI exited with code $guiExit"
  Warn "Backend is still running in WSL."
  Write-Host "    Stop backend: .\stop_backend_wsl.ps1"
  exit $guiExit
}

Ok "GUI exited cleanly"
Write-Host "    Backend still running in WSL. Stop when done: .\stop_backend_wsl.ps1"
exit 0
