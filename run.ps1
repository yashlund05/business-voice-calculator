<#
.SYNOPSIS
    Launcher script for Voice Calculator.
.DESCRIPTION
    Runs Voice Calculator using the local Python virtual environment (.venv).
.EXAMPLE
    .\run.ps1
.EXAMPLE
    .\run.ps1 -DebugLog -ConsoleLog
#>

param(
    [switch]$DebugLog,
    [switch]$ConsoleLog,
    [string]$ModelPath = ""
)

$ErrorActionPreference = "Stop"

$VenvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Error "Virtual environment not found at $VenvPython. Run: python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt"
    exit 1
}

$Arguments = @("main.py")

if ($DebugLog) {
    $Arguments += "--debug"
}
if ($ConsoleLog) {
    $Arguments += "--console-log"
}
if ($ModelPath -ne "") {
    $Arguments += @("--model-path", $ModelPath)
}

Write-Host "Starting Voice Calculator..." -ForegroundColor Cyan
& $VenvPython @Arguments
