#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Clean start script - runs cleanup then starts backend and GUI
    
.DESCRIPTION
    Performs full cleanup, starts backend, waits for it to be ready,
    then launches the GUI.
#>

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

# Run cleanup first
Write-Host "Running cleanup..." -ForegroundColor Cyan
& "$ProjectRoot\cleanup.ps1"

Write-Host "`nStarting backend..." -ForegroundColor Cyan
$backendProcess = Start-Process -FilePath "python" -ArgumentList "Start.py" -WorkingDirectory $ProjectRoot -PassThru -WindowStyle Normal

Write-Host "Waiting for backend to be ready (this may take 30-60 seconds)..." -ForegroundColor Yellow
$maxWait = 120
$waited = 0
$ready = $false

while ($waited -lt $maxWait -and !$ready) {
    Start-Sleep -Seconds 2
    $waited += 2
    
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            $ready = $true
            Write-Host "✓ Backend is ready!" -ForegroundColor Green
        }
    } catch {
        Write-Host "." -NoNewline -ForegroundColor Gray
    }
}

if (!$ready) {
    Write-Host "`n⚠ Backend did not become ready within $maxWait seconds" -ForegroundColor Yellow
    Write-Host "Check the backend terminal for errors" -ForegroundColor Yellow
    Write-Host "`nPress Enter to continue anyway, or Ctrl+C to abort..."
    Read-Host
}

Write-Host "`nStarting GUI..." -ForegroundColor Cyan
Start-Process -FilePath "python" -ArgumentList "gui\gui_dashboard.py" -WorkingDirectory $ProjectRoot -WindowStyle Normal

Write-Host "`n═══════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  Application started!" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "`nBackend PID: $($backendProcess.Id)" -ForegroundColor Gray
Write-Host "Backend URL: http://127.0.0.1:8000" -ForegroundColor Gray
Write-Host "`nTo stop everything, run: .\cleanup.ps1" -ForegroundColor Gray
Write-Host ""
