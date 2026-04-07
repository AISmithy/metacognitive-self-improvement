[CmdletBinding()]
param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$Root       = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $Root "backend"
$RunDir     = Join-Path $Root ".run"

New-Item -ItemType Directory -Force $RunDir | Out-Null

function Import-EnvFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) { continue }
        $parts = $trimmed.Split("=", 2)
        [Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim(), "Process")
    }
}

function Get-RunningProcess {
    param([string]$PidFile)
    if (-not (Test-Path $PidFile)) { return $null }
    $raw = (Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
    $processId = 0
    if (-not [int]::TryParse($raw, [ref]$processId)) { return $null }
    return Get-Process -Id $processId -ErrorAction SilentlyContinue
}

function Find-Python {
    $candidates = @(
        (Join-Path $Root ".venv\Scripts\python.exe"),
        "C:\Users\nisha\AppData\Local\Programs\Python\Python311\python.exe",
        "C:\Users\nisha\AppData\Local\Programs\Python\Python312\python.exe",
        "C:\Users\nisha\AppData\Local\Programs\Python\Python310\python.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) { return $candidate }
    }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) { return $python.Source }
    throw "Python 3.11+ not found. Install Python or create a .venv at the repo root."
}

function Ensure-BackendDependencies {
    param([string]$PythonExe)
    & $PythonExe -c "import fastapi, uvicorn, sqlmodel, openai" 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { return }
    Write-Host "Installing backend dependencies..."
    Push-Location $BackendDir
    try {
        & $PythonExe -m pip install -e . | Out-Host
        if ($LASTEXITCODE -ne 0) { throw "pip install failed." }
    } finally {
        Pop-Location
    }
}

Import-EnvFile (Join-Path $Root ".env.local")
Import-EnvFile (Join-Path $BackendDir ".env.local")

$PythonExe = Find-Python

Ensure-BackendDependencies -PythonExe $PythonExe

$PidFile = Join-Path $RunDir "backend.pid"
$OutLog  = Join-Path $RunDir "backend.out.log"
$ErrLog  = Join-Path $RunDir "backend.err.log"

$existing = Get-RunningProcess -PidFile $PidFile
if ($existing) {
    Write-Host "Backend already running (PID $($existing.Id))."
} else {
    $proc = Start-Process `
        -FilePath $PythonExe `
        -ArgumentList "-m", "uvicorn", "app.main:app",
                      "--host", "127.0.0.1",
                      "--port", "$Port",
                      "--reload" `
        -WorkingDirectory $BackendDir `
        -PassThru `
        -RedirectStandardOutput $OutLog `
        -RedirectStandardError  $ErrLog

    Set-Content $PidFile $proc.Id
    Start-Sleep -Seconds 2

    Write-Host ""
    Write-Host "Backend started (PID $($proc.Id))."
}

Write-Host ""
Write-Host "API:      http://127.0.0.1:$Port/api/state"
Write-Host "Docs:     http://127.0.0.1:$Port/docs"
Write-Host "Logs:     $RunDir\backend.*.log"
Write-Host ""
Write-Host "Stop with:  .\stop.ps1"
