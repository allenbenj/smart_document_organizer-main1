@echo off
REM Batch file wrapper for cleanup.ps1
echo Running cleanup...
powershell -ExecutionPolicy Bypass -File "%~dp0cleanup.ps1"
pause
