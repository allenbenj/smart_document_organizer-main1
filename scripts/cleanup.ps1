#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Comprehensive cleanup script for Smart Document Organizer
    
.DESCRIPTION
    Kills all related processes, cleans stale locks, temporary files,
    and ensures a clean state for restart.
    
.EXAMPLE
    .\cleanup.ps1
    .\cleanup.ps1 -Verbose
#>

param(
    [switch]$Verbose
)

$ErrorActionPreference = "Continue"
$ProjectRoot = $PSScriptRoot

Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Smart Document Organizer - FULL CLEANUP" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# 1. Kill all Python processes related to this project
Write-Host "[1/6] Terminating Python processes..." -ForegroundColor Yellow
$killed = 0
Get-Process -Name python, pythonw -ErrorAction SilentlyContinue | ForEach-Object {
    try {
        $proc = $_
        $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($proc.Id)" -ErrorAction SilentlyContinue).CommandLine
        
        # Check if process is related to our project
        if ($cmdLine -and ($cmdLine -like "*Start.py*" -or 
                           $cmdLine -like "*gui_dashboard*" -or 
                           $cmdLine -like "*smart_document_organizer*" -or
                           $cmdLine -like "*uvicorn*" -or
                           $cmdLine -like "*fastapi*")) {
            Write-Host "  → Killing PID $($proc.Id): $($cmdLine.Substring(0, [Math]::Min(80, $cmdLine.Length)))" -ForegroundColor Gray
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            $killed++
        }
    } catch {
        # Silently continue
    }
}
Write-Host "  ✓ Killed $killed Python process(es)" -ForegroundColor Green
Start-Sleep -Milliseconds 500

# 2. Clean up port 8000 (in case something else is using it)
Write-Host "`n[2/6] Checking port 8000..." -ForegroundColor Yellow
$port8000 = netstat -ano | Select-String ":8000.*LISTENING"
if ($port8000) {
    $port8000 | ForEach-Object {
        $line = $_.Line
        if ($line -match "\s+(\d+)$") {
            $pid = $matches[1]
            Write-Host "  → Port 8000 in use by PID $pid, terminating..." -ForegroundColor Gray
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Host "  ✓ Port 8000 freed" -ForegroundColor Green
} else {
    Write-Host "  ✓ Port 8000 is free" -ForegroundColor Green
}

# 3. Clean temporary files and locks
Write-Host "`n[3/6] Cleaning temporary files and locks..." -ForegroundColor Yellow
$cleaned = 0

# Lock files
$lockPatterns = @("*.lock", "*.pid", ".uvicorn.pid")
foreach ($pattern in $lockPatterns) {
    Get-ChildItem -Path $ProjectRoot -Filter $pattern -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Host "  → Removing: $($_.FullName)" -ForegroundColor Gray
        Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
        $cleaned++
    }
}

# Python cache
Get-ChildItem -Path $ProjectRoot -Filter "__pycache__" -Recurse -Directory -ErrorAction SilentlyContinue | ForEach-Object {
    if ($Verbose) {
        Write-Host "  → Cleaning: $($_.FullName)" -ForegroundColor Gray
    }
    Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
    $cleaned++
}

# .pyc files
Get-ChildItem -Path $ProjectRoot -Filter "*.pyc" -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
    $cleaned++
}

Write-Host "  ✓ Cleaned $cleaned temporary file(s)" -ForegroundColor Green

# 4. Clean GUI-specific temp files
Write-Host "`n[4/6] Cleaning GUI state..." -ForegroundColor Yellow
$guiTempFiles = @(
    "$ProjectRoot\gui\*.tmp",
    "$ProjectRoot\gui\.state",
    "$ProjectRoot\.gui_state"
)
$guiCleaned = 0
foreach ($pattern in $guiTempFiles) {
    if (Test-Path $pattern) {
        Remove-Item $pattern -Force -ErrorAction SilentlyContinue
        $guiCleaned++
    }
}
Write-Host "  ✓ Cleaned $guiCleaned GUI temp file(s)" -ForegroundColor Green

# 5. Check database locks
Write-Host "`n[5/6] Checking database locks..." -ForegroundColor Yellow
$dbPath = "$ProjectRoot\mem_db\data\documents.db"
$dbLock = "$dbPath-shm"
$dbWal = "$dbPath-wal"

if (Test-Path $dbLock) {
    Write-Host "  → Removing SQLite shared memory: $dbLock" -ForegroundColor Gray
    Remove-Item $dbLock -Force -ErrorAction SilentlyContinue
}
if (Test-Path $dbWal) {
    Write-Host "  → Removing SQLite WAL: $dbWal" -ForegroundColor Gray
    Remove-Item $dbWal -Force -ErrorAction SilentlyContinue
}
Write-Host "  ✓ Database locks cleared" -ForegroundColor Green

# 6. Verify cleanup
Write-Host "`n[6/6] Verifying cleanup..." -ForegroundColor Yellow
Start-Sleep -Milliseconds 300

$remainingProcs = Get-Process -Name python, pythonw -ErrorAction SilentlyContinue | Where-Object {
    $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)" -ErrorAction SilentlyContinue).CommandLine
    $cmdLine -and ($cmdLine -like "*smart_document_organizer*" -or $cmdLine -like "*Start.py*")
}

if ($remainingProcs) {
    Write-Host "  ⚠ Warning: $($remainingProcs.Count) related process(es) still running" -ForegroundColor Yellow
    $remainingProcs | ForEach-Object {
        Write-Host "    PID: $($_.Id)" -ForegroundColor Gray
    }
} else {
    Write-Host "  ✓ All processes terminated" -ForegroundColor Green
}

$port8000Check = netstat -ano | Select-String ":8000.*LISTENING"
if ($port8000Check) {
    Write-Host "  ⚠ Warning: Port 8000 still in use" -ForegroundColor Yellow
} else {
    Write-Host "  ✓ Port 8000 is free" -ForegroundColor Green
}

Write-Host "`n═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  CLEANUP COMPLETE" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "`nYou can now safely start the application with:" -ForegroundColor White
Write-Host "  • Backend:  python Start.py" -ForegroundColor Cyan
Write-Host "  • GUI:      python gui\gui_dashboard.py" -ForegroundColor Cyan
Write-Host ""
