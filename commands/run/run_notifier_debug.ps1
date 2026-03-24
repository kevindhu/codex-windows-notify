$ErrorActionPreference = "Stop"

$repoRoot = Split-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) -Parent
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

$logDir = Join-Path $repoRoot "logs"
$debugLog = Join-Path $logDir "manual-debug.log"

New-Item -ItemType Directory -Path $logDir -Force | Out-Null

Write-Host "Running notifier in foreground..."
Write-Host "Python: $python"
Write-Host "Repo: $repoRoot"
Write-Host "Debug log: $debugLog"
Write-Host ""
Write-Host "Press Ctrl+C to stop."
Write-Host ""

Set-Location $repoRoot
& $python ".\codex_notify.py" --verbose 2>&1 | Tee-Object -FilePath $debugLog -Append
