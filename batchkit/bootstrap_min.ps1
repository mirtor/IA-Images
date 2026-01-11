# bootstrap_min.ps1 — arranque mínimo de IA-Images
# - Vive en batchkit/
# - Instala Python 3.10 desde vendors si no existe
# - Instala Git si no existe
# - Auto-actualiza el repo UNA SOLA VEZ
# - Crea venv y lanza app_gui.py

$ErrorActionPreference = "Stop"

Write-Host "== IA-Images bootstrap (GUI) ==" -ForegroundColor Cyan

# --------------------------------------------------
# Rutas base
# --------------------------------------------------
$kit  = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $kit
Set-Location $kit

Write-Host "Project root: $root"
Write-Host "Batchkit dir:  $kit"

# vendors
$vendors = if (Test-Path (Join-Path $root "vendors")) {
    Join-Path $root "vendors"
} else {
    Join-Path $kit "vendors"
}
Write-Host "Vendors dir:   $vendors"

# --------------------------------------------------
# app_gui.py (obligatorio)
# --------------------------------------------------
$appGui = Join-Path $kit "app_gui.py"
if (-not (Test-Path $appGui)) {
    Write-Host "ERROR: No se encuentra app_gui.py" -ForegroundColor Red
    exit 1
}

# --------------------------------------------------
# Python 3.10
# --------------------------------------------------
function Get-Python310 {
    $paths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "$env:ProgramFiles\Python310\python.exe"
    )
    foreach ($p in $paths) { if (Test-Path $p) { return $p } }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        try {
            $exe = & py -3.10 -c "import sys; print(sys.executable)"
            if ($exe -and (Test-Path $exe)) { return $exe.Trim() }
        } catch {}
    }
    return $null
}

function Install-Python310 {
    $installer = Join-Path $vendors "python-3.10.11-amd64.exe"
    if (-not (Test-Path $installer)) {
        Write-Host "ERROR: Instalador Python no encontrado" -ForegroundColor Red
        exit 1
    }
    Write-Host "Instalando Python 3.10..." -ForegroundColor Yellow
    Start-Process $installer `
        -ArgumentList '/quiet','InstallAllUsers=0','Include_launcher=1','PrependPath=1' `
        -Wait
}

$PY = Get-Python310
if (-not $PY) { Install-Python310; $PY = Get-Python310 }
if (-not $PY) { Write-Host "ERROR: Python no disponible" -ForegroundColor Red; exit 1 }
Write-Host "Python listo: $PY" -ForegroundColor Green

# --------------------------------------------------
# Git
# --------------------------------------------------
function Get-Git {
    try {
        $p = Start-Process git -ArgumentList "--version" -NoNewWindow -Wait -PassThru
        if ($p.ExitCode -eq 0) { return (Get-Command git).Source }
    } catch {}
    return $null
}

function Install-Git {
    $installer = Join-Path $vendors "Git-2.52.0-64-bit.exe"
    if (-not (Test-Path $installer)) {
        Write-Host "ERROR: Git no encontrado en vendors" -ForegroundColor Red
        exit 1
    }
    Write-Host "Instalando Git..." -ForegroundColor Yellow
    Start-Process $installer `
        -ArgumentList '/VERYSILENT','/NORESTART','/SP-' `
        -Wait
}

$GIT = Get-Git
if (-not $GIT) { Install-Git; $GIT = Get-Git }
if (-not $GIT) { Write-Host "ERROR: Git no disponible" -ForegroundColor Red; exit 1 }
Write-Host "Git listo: $GIT" -ForegroundColor Green

# --------------------------------------------------
# Auto-update del repo (UNA SOLA VEZ, SEGURO)
# --------------------------------------------------
$checker = Join-Path $kit "update_repo.ps1"
if (Test-Path $checker) {
    & powershell -NoProfile -ExecutionPolicy Bypass `
        -File $checker -RepoRoot $root
}

# --------------------------------------------------
# venv + deps
# --------------------------------------------------
$venvDir = Join-Path $kit ".venv"
$venvPy  = Join-Path $venvDir "Scripts\python.exe"
$venvPyW = Join-Path $venvDir "Scripts\pythonw.exe"

if (-not (Test-Path $venvPy)) {
    Write-Host "Creando venv..." -ForegroundColor Cyan
    & $PY -m venv $venvDir
}

& $venvPy -m pip install --upgrade pip | Out-Null
& $venvPy -m pip install ttkbootstrap pyyaml requests pillow python-dotenv tqdm | Out-Null

# --------------------------------------------------
# Lanzar GUI
# --------------------------------------------------
Write-Host "Lanzando interfaz grafica..." -ForegroundColor Cyan

Start-Process `
    -FilePath $venvPy `
    -ArgumentList "-u", "`"$appGui`"" `
    -WorkingDirectory $kit `
    -WindowStyle Hidden

Write-Host "Listo." -ForegroundColor Green
