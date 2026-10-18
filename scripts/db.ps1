<#
.SYNOPSIS
  Manage the project-local PostgreSQL instance used for development and tests.

.DESCRIPTION
  Creates (on first use) and runs an isolated PostgreSQL cluster in
  backend/.pgdata on port 5433, so the project does not depend on Docker or on
  a system PostgreSQL service.

  The PostgreSQL binaries are auto-detected from C:\Program Files\PostgreSQL,
  or set the PGBIN environment variable to the folder containing pg_ctl.exe.

.EXAMPLES
  ./scripts/db.ps1 start
  ./scripts/db.ps1 status
  ./scripts/db.ps1 stop
  ./scripts/db.ps1 reset
#>
param(
    [Parameter(Position = 0)]
    [ValidateSet('start', 'stop', 'status', 'reset')]
    [string]$Action = 'status',

    [int]$Port = 5433,

    [string]$PgBin = $env:PGBIN
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$DataDir = Join-Path $RepoRoot 'backend\.pgdata'
$OutLog = Join-Path $DataDir 'server.log'
$ErrLog = Join-Path $DataDir 'server.err.log'

if (-not $PgBin) {
    $fromProgramFiles = Get-ChildItem 'C:\Program Files\PostgreSQL' -Directory -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending |
        ForEach-Object { Join-Path $_.FullName 'bin' }
    $PgBin = @($fromProgramFiles) | Where-Object { Test-Path (Join-Path $_ 'pg_ctl.exe') } | Select-Object -First 1
}

if (-not $PgBin -or -not (Test-Path (Join-Path $PgBin 'pg_ctl.exe'))) {
    throw "Could not find PostgreSQL binaries. Set the PGBIN environment variable to the folder containing pg_ctl.exe."
}

$pgCtl = Join-Path $PgBin 'pg_ctl.exe'
$pgReady = Join-Path $PgBin 'pg_isready.exe'

function Initialize-DataDir {
    if (-not (Test-Path (Join-Path $DataDir 'PG_VERSION'))) {
        New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
        Write-Host "Initializing PostgreSQL data directory: $DataDir"
        & (Join-Path $PgBin 'initdb.exe') -D $DataDir -U newtonite -A trust -E UTF8 --locale=C | Out-Null
    }
}

function Wait-UntilReady {
    for ($i = 0; $i -lt 40; $i++) {
        & $pgReady -h 127.0.0.1 -p $Port -U newtonite *> $null
        if ($LASTEXITCODE -eq 0) { return }
        Start-Sleep -Milliseconds 500
    }
    throw "PostgreSQL did not become ready on port $Port."
}

function Ensure-Databases {
    foreach ($name in @('newtonite', 'newtonite_test')) {
        & (Join-Path $PgBin 'createdb.exe') -h 127.0.0.1 -p $Port -U newtonite $name 2>$null | Out-Null
    }
}

switch ($Action) {
    'start' {
        Initialize-DataDir
        if (Test-Path (Join-Path $DataDir 'postmaster.pid')) {
            # Clean up a stale pid file left by an unclean shutdown.
            & $pgReady -h 127.0.0.1 -p $Port -U newtonite *> $null
            if ($LASTEXITCODE -ne 0) {
                Remove-Item (Join-Path $DataDir 'postmaster.pid') -Force -ErrorAction SilentlyContinue
            }
        }
        # Launch postgres detached so the shell prompt returns immediately.
        # Quote the data directory because the repo path may contain spaces.
        $quotedDataDir = '"' + $DataDir + '"'
        Start-Process -FilePath (Join-Path $PgBin 'postgres.exe') `
            -ArgumentList @('-D', $quotedDataDir, '-p', $Port, '-c', 'listen_addresses=127.0.0.1', '-c', 'autovacuum=off') `
            -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog -WindowStyle Hidden
        Wait-UntilReady
        Ensure-Databases
        Write-Host "PostgreSQL is running on port $Port (data: $DataDir)"
        Write-Host "Next: cd backend; .\.venv\Scripts\python.exe -m alembic upgrade head; .\.venv\Scripts\python.exe scripts\seed.py"
    }
    'stop' {
        if (Test-Path (Join-Path $DataDir 'PG_VERSION')) {
            & $pgCtl -D $DataDir stop -m fast
        }
        else {
            Write-Host "No project data directory found at $DataDir."
        }
    }
    'status' {
        & $pgReady -h 127.0.0.1 -p $Port -U newtonite
    }
    'reset' {
        if (Test-Path (Join-Path $DataDir 'PG_VERSION')) {
            & $pgCtl -D $DataDir stop -m immediate 2>$null
            Start-Sleep -Seconds 2
        }
        Remove-Item -Recurse -Force $DataDir -ErrorAction SilentlyContinue
        Write-Host "Removed $DataDir. Run 'start', then migrations and seed."
    }
}
