$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$preferredPython = Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"
$python = ""

if (Test-Path $preferredPython) {
    $python = $preferredPython
}

if (-not $python) {
    $python = (& python -c "import sys; print(sys.executable)" 2>$null | Select-Object -First 1).Trim()
}

if (-not $python) {
    $python = (Get-Command python.exe -ErrorAction Stop).Source
}

$pythonw = Join-Path (Split-Path -Parent $python) "pythonw.exe"
if (-not (Test-Path $pythonw)) {
    throw "pythonw.exe not found next to python.exe: $pythonw"
}

$scriptPath = Join-Path $repoRoot "codex_notify.py"

Write-Host "Starting notifier in background..."
Write-Host "Pythonw: $pythonw"
Write-Host "Script: $scriptPath"
Write-Host "Repo: $repoRoot"

$process = Start-Process -FilePath $pythonw -ArgumentList $scriptPath -WorkingDirectory $repoRoot -PassThru

Write-Host ""
Write-Host ("Started PID {0}" -f $process.Id)
