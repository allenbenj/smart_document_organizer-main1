# Scripts Directory

All startup, cleanup, and utility scripts have been moved here for better organization.

## Startup Scripts

### Windows (PowerShell)
- **`run_clean.ps1`** - *RECOMMENDED* - Full cleanup, start backend, wait for health, launch GUI
- **`run_app.ps1`** - Start application (assumes backend already running)
- **`run_hybrid.ps1`** - Hybrid startup mode
- **`cleanup.ps1`** - Kill processes, free ports, clean caches

### Windows (Batch)
- **`run_app.bat`** - Start application (batch version)
- **`run_deps.bat`** - Install dependencies
- **`run_start.bat`** - Quick start (batch version)
- **`cleanup.bat`** - Cleanup wrapper (calls cleanup.ps1)

### WSL/Linux
- **`stop_backend_wsl.ps1`** - Stop backend running in WSL

## Usage

**Recommended First-Time Setup:**
```powershell
# From project root
.\scripts\run_deps.bat          # Install dependencies (one-time)
.\scripts\run_clean.ps1         # Start with full cleanup
```

**Daily Usage:**
```powershell
.\scripts\run_clean.ps1         # Safest - always cleanup first
# OR
.\scripts\cleanup.ps1           # Manual cleanup
.\scripts\run_app.ps1           # Then start
```

**Troubleshooting:**
```powershell
.\scripts\cleanup.ps1           # Kill stuck processes
.\scripts\stop_backend_wsl.ps1  # If backend in WSL won't stop
```

## File Organization

All command-line scripts (.bat, .ps1) were moved from the project root to this directory on Feb 16, 2026 to reduce root folder clutter.

Main application entry points remain in root:
- `Start.py` - Backend server
- `gui/gui_dashboard.py` - GUI application
