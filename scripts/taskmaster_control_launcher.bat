@echo off
setlocal
cd /d "%~dp0\.."
python scripts\taskmaster_control_launcher.py %*
endlocal
