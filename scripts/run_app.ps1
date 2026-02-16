param(
  [switch]$Install = $false,
  [switch]$Optional = $false
)

Write-Host "[+] Checking Python..."
$python = Get-Command python -ErrorAction SilentlyContinue
$pythonCmd = "python"
if (-not $python) {
  $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
  if ($pyLauncher) {
    $pythonCmd = "py -3"
  } else {
    Write-Error "Python not found in PATH. Please install Python 3.10+ and retry."
    exit 1
  }
}

if ($Install) {
  Write-Host "[+] Installing required dependencies (requirements.txt)..."
  & $pythonCmd -m pip install --upgrade pip
  & $pythonCmd -m pip install -r requirements.txt
  if ($LASTEXITCODE -ne 0) { Write-Error "Failed to install required packages."; exit 1 }
  if ($Optional) {
    Write-Host "[+] Installing optional dependencies (requirements-optional.txt)..."
    & $pythonCmd -m pip install -r requirements-optional.txt
    if ($LASTEXITCODE -ne 0) { Write-Error "Failed to install optional packages."; exit 1 }
  }
}

Write-Host "[+] Launching API and GUI..."
& $pythonCmd tools\run_app.py
if ($LASTEXITCODE -ne 0 -and -not $Install) {
  Write-Host "[i] If this is a first run, retry with -Install."
}
exit $LASTEXITCODE
