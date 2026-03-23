param(
    [string]$InputPath = ".\\sounds\\smallnotify.mp3",
    [string]$OutputPath = ".\\sounds\\smallnotify.wav"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$inputFullPath = Join-Path $repoRoot $InputPath
$outputFullPath = Join-Path $repoRoot $OutputPath

if (-not (Test-Path $inputFullPath)) {
    throw "Input sound file not found: $inputFullPath"
}

$outputDir = Split-Path -Parent $outputFullPath
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

ffmpeg -y -i $inputFullPath -ac 2 -ar 44100 $outputFullPath | Out-Null

Write-Host "Converted sound:"
Write-Host $outputFullPath
