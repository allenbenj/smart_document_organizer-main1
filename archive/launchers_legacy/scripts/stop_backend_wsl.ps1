param(
  [string]$WslDistro = "Ubuntu",
  [string]$LinuxProjectPath = "/mnt/e/Project/smart_document_organizer-main"
)

$ErrorActionPreference = "Continue"
Write-Host "[+] Stopping backend in WSL..." -ForegroundColor Cyan

$stopCmd = @"
set +e
cd '$LinuxProjectPath'
if [ -f .backend-wsl.pid ]; then
  PID=$(cat .backend-wsl.pid)
  kill $PID 2>/dev/null
  rm -f .backend-wsl.pid
fi
pkill -f "tools/run_app.py --backend-only" 2>/dev/null
pkill -f "uvicorn Start:app" 2>/dev/null
echo "DONE"
"@

wsl -d $WslDistro bash -lc $stopCmd | ForEach-Object { Write-Host "    $_" }
Write-Host "[OK] Stop command sent." -ForegroundColor Green
