param(
    [string]$ProjectRoot = "E:\Project\smart_document_organizer-main"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -Path $ProjectRoot)) {
    throw "Project root not found: $ProjectRoot"
}

Set-Location -Path $ProjectRoot

# Keep GUI startup on Windows and avoid WSL backend launch logic.
$env:GUI_SKIP_WSL_BACKEND_START = "1"
$env:STARTUP_PROFILE = "full"

function Resolve-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return "py"
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return "python"
    }
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "C:\Python313\python.exe",
        "C:\Python312\python.exe",
        "C:\Python311\python.exe",
        "C:\Python310\python.exe"
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -Path $candidate)) {
            return $candidate
        }
    }
    try {
        $globMatches = Get-ChildItem "C:\Users\*\AppData\Local\Programs\Python\Python3*\python.exe" -ErrorAction Stop
        if ($globMatches -and $globMatches[0].FullName) {
            return $globMatches[0].FullName
        }
    }
    catch {
        # best-effort discovery
    }
    return $null
}

$pythonCmd = Resolve-PythonCommand
if (-not $pythonCmd) {
    throw "No Python launcher found (py/python) and no known python.exe path detected."
}

& "$pythonCmd" Start.py --gui --profile full
