$ErrorActionPreference = "Stop"

$startupDir = [Environment]::GetFolderPath("Startup")
$startupLauncher = Join-Path $startupDir "CodexNotifier.cmd"
$legacyShortcut = Join-Path $startupDir "CodexNotifier.lnk"
$legacyLauncher = Join-Path $startupDir "CodexNotifier.vbs"

if (Test-Path $startupLauncher) {
    Remove-Item -Path $startupLauncher -Force
    Write-Host "Removed startup launcher:"
    Write-Host $startupLauncher
}

if (Test-Path $legacyShortcut) {
    Remove-Item -Path $legacyShortcut -Force
    Write-Host "Removed legacy startup launcher:"
    Write-Host $legacyShortcut
}

if (Test-Path $legacyLauncher) {
    Remove-Item -Path $legacyLauncher -Force
    Write-Host "Removed legacy startup launcher:"
    Write-Host $legacyLauncher
}

if (-not (Test-Path $startupLauncher) -and -not (Test-Path $legacyShortcut) -and -not (Test-Path $legacyLauncher)) {
    Write-Host "Startup launcher not found:"
    Write-Host $startupLauncher
}
