[CmdletBinding()]
param(
    [switch]$KeepPidFiles
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$RunDir = Join-Path $Root ".run"

function Stop-TrackedProcess {
    param(
        [string]$Name,
        [string]$PidFile
    )

    if (-not (Test-Path $PidFile)) {
        Write-Host "$Name is not tracked."
        return
    }

    $raw = (Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
    $processId = 0
    if (-not [int]::TryParse($raw, [ref]$processId)) {
        Write-Host "$Name pid file is invalid."
        if (-not $KeepPidFiles) { Remove-Item $PidFile -ErrorAction SilentlyContinue }
        return
    }

    # Kill the entire process tree so uvicorn's reloader child processes also stop.
    $killed = $false
    $tree = @($processId)
    # Collect child PIDs (WMI)
    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $processId" -ErrorAction SilentlyContinue
    foreach ($child in $children) { $tree += $child.ProcessId }

    foreach ($procId in $tree) {
        $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if ($p) {
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            $killed = $true
        }
    }

    if ($killed) {
        Write-Host "Stopped $Name (PID $processId + $($tree.Count - 1) child(ren))."
    } else {
        Write-Host "$Name was not running."
    }

    if (-not $KeepPidFiles) { Remove-Item $PidFile -ErrorAction SilentlyContinue }
}

if (-not (Test-Path $RunDir)) {
    Write-Host ".run directory not found. Nothing to stop."
    exit 0
}

Stop-TrackedProcess -Name "backend" -PidFile (Join-Path $RunDir "backend.pid")
