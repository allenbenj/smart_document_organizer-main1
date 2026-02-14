@echo off
setlocal
REM Simple one-click launcher for backend API + desktop GUI

REM Hard reset stale Python launcher/runtime processes to avoid old-code drift
echo Stopping stale Python processes (if any)...
taskkill /F /IM python.exe /T >nul 2>nul
taskkill /F /IM py.exe /T >nul 2>nul

set "PY_CMD="
where python >nul 2>nul
if not errorlevel 1 set "PY_CMD=python"
if "%PY_CMD%"=="" (
  where py >nul 2>nul
  if not errorlevel 1 set "PY_CMD=py -3"
)
if "%PY_CMD%"=="" (
  echo Python not found in PATH. Please install Python 3.10+ and try again.
  exit /b 1
)

echo Starting API and GUI...
call %PY_CMD% tools\run_app.py
set rc=%ERRORLEVEL%
if %rc% neq 0 (
  echo.
  echo If this is a first run, install dependencies with:
  echo   %PY_CMD% tools\run_app.py --install
)
echo Script finished with code %rc%.
exit /b %rc%
