$ErrorActionPreference = "Stop"

$startupDir = [Environment]::GetFolderPath("Startup")
$startupLauncher = Join-Path $startupDir "CodexNotifier.vbs"

if (Test-Path $startupLauncher) {
    Remove-Item -Path $startupLauncher -Force
    Write-Host "Removed startup launcher:"
    Write-Host $startupLauncher
} else {
    Write-Host "Startup launcher not found:"
    Write-Host $startupLauncher
}
