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

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$taskName = "Codex VS Code Notifier"
$pythonw = Get-PreferredPythonw -RepoRoot $repoRoot
$scriptPath = Join-Path $repoRoot "codex_notify.py"
$workDir = $repoRoot
$logDir = Join-Path $repoRoot "logs"
$stdoutLog = Join-Path $logDir "scheduler-stdout.log"
$stderrLog = Join-Path $logDir "scheduler-stderr.log"

New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$taskCommand = @(
    "cd /d ""$workDir""",
    "&&",
    """$pythonw"" ""$scriptPath""",
    "1>>""$stdoutLog""",
    "2>>""$stderrLog"""
) -join " "

$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c $taskCommand"
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Runs the Codex VS Code completion notifier in the background at sign-in." `
    -Force | Out-Null

Start-ScheduledTask -TaskName $taskName

Write-Host "Installed scheduled task: $taskName"
Write-Host "Repo: $repoRoot"
Write-Host "Pythonw: $pythonw"
Write-Host "Stdout log: $stdoutLog"
Write-Host "Stderr log: $stderrLog"
