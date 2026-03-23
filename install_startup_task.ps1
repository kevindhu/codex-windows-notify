$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$taskName = "Codex VS Code Notifier"
$pythonw = (Get-Command pythonw.exe -ErrorAction Stop).Source
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
