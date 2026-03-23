$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$startupDir = [Environment]::GetFolderPath("Startup")
$startupLauncher = Join-Path $startupDir "CodexNotifier.vbs"
$sourceLauncher = Join-Path $repoRoot "run_codex_notifier_hidden.vbs"

if (-not (Test-Path $sourceLauncher)) {
    throw "Launcher not found: $sourceLauncher"
}

Copy-Item -Path $sourceLauncher -Destination $startupLauncher -Force

Write-Host "Installed startup launcher:"
Write-Host $startupLauncher
Write-Host ""
Write-Host "It will run when you sign in to Windows."
