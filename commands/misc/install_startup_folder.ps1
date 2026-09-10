$ErrorActionPreference = "Stop"

function Get-PreferredPythonw {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot
    )

    $repoUserHome = Split-Path (Split-Path $RepoRoot -Parent) -Parent
    $candidates = @(
        (Join-Path $repoUserHome "AppData\Local\Programs\Python\Python311\pythonw.exe"),
        (Join-Path $repoUserHome "AppData\Local\Programs\Python\Python312\pythonw.exe"),
        (Join-Path $repoUserHome "miniconda3\pythonw.exe")
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    $pythonFromCommand = ""
    try {
        $pythonFromCommand = (& python -c "import sys; print(sys.executable)" 2>$null | Select-Object -First 1).Trim()
    } catch {}

    if ($pythonFromCommand) {
        $siblingPythonw = Join-Path (Split-Path -Parent $pythonFromCommand) "pythonw.exe"
        if (Test-Path $siblingPythonw) {
            return $siblingPythonw
        }
    }

    $python = (Get-Command python.exe -ErrorAction Stop).Source
    $pythonw = Join-Path (Split-Path -Parent $python) "pythonw.exe"
    if (Test-Path $pythonw) {
        return $pythonw
    }

    throw "pythonw.exe not found for repo root: $RepoRoot"
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$startupDir = [Environment]::GetFolderPath("Startup")
$startupLauncher = Join-Path $startupDir "CodexNotifier.cmd"
$legacyShortcut = Join-Path $startupDir "CodexNotifier.lnk"
$legacyLauncher = Join-Path $startupDir "CodexNotifier.vbs"
$scriptPath = Join-Path $repoRoot "codex_notify.py"
$pythonw = Get-PreferredPythonw -RepoRoot $repoRoot

if (-not (Test-Path $scriptPath)) {
    throw "Notifier entrypoint not found: $scriptPath"
}

if (Test-Path $legacyLauncher) {
    Remove-Item -Path $legacyLauncher -Force
}

if (Test-Path $legacyShortcut) {
    Remove-Item -Path $legacyShortcut -Force
}

$launcherContent = @(
    "@echo off",
    ('cd /d "{0}"' -f $repoRoot),
    ('start "" /b "{0}" "{1}"' -f $pythonw, $scriptPath)
)
Set-Content -Path $startupLauncher -Value $launcherContent -Encoding ASCII

Write-Host "Installed startup launcher:"
Write-Host $startupLauncher
Write-Host "Pythonw:"
Write-Host $pythonw
Write-Host ""
Write-Host "It will run when you sign in to Windows."
