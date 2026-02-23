@echo off
setlocal

set "PROJECT_ROOT=E:\Project\smart_document_organizer-main"
if not exist "%PROJECT_ROOT%" (
  echo Project root not found: %PROJECT_ROOT%
  exit /b 1
)

cd /d "%PROJECT_ROOT%"
set "GUI_SKIP_WSL_BACKEND_START=1"
set "STARTUP_PROFILE=full"

where py >nul 2>nul
if %errorlevel%==0 (
  py Start.py --gui --profile full
  exit /b %errorlevel%
)

where python >nul 2>nul
if %errorlevel%==0 (
  python Start.py --gui --profile full
  exit /b %errorlevel%
)

for %%P in (
  "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
  "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
  "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
  "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
  "C:\Python313\python.exe"
  "C:\Python312\python.exe"
  "C:\Python311\python.exe"
  "C:\Python310\python.exe"
) do (
  if exist %%~P (
    "%%~P" Start.py --gui --profile full
    exit /b %errorlevel%
  )
)

for /f "delims=" %%P in ('dir /b /s "C:\Users\*\AppData\Local\Programs\Python\Python3*\python.exe" 2^>nul') do (
  if exist "%%~P" (
    "%%~P" Start.py --gui --profile full
    exit /b %errorlevel%
  )
)

echo No Python launcher found on PATH and no known python.exe path detected.
exit /b 1
