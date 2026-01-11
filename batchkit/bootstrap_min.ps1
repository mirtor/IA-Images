# bootstrap_min.ps1 — arranque mínimo de IA-Images
# - Vive en batchkit/
# - Instala Python 3.10 desde vendors si no existe
# - Crea venv y lanza app_gui.py
# - NO toca Stable Diffusion

$ErrorActionPreference = "Stop"

Write-Host "== IA-Images bootstrap (GUI) ==" -ForegroundColor Cyan

# --------------------------------------------------
# Rutas base (CLAVE)
# --------------------------------------------------
$kit  = Split-Path -Parent $MyInvocation.MyCommand.Path   # .../IA-Images/batchkit
$root = Split-Path -Parent $kit                           # .../IA-Images

Set-Location $kit

Write-Host "Project root: $root"
Write-Host "Batchkit dir:  $kit"

# vendors: raíz > batchkit
$vendors = if (Test-Path (Join-Path $root "vendors")) {
    Join-Path $root "vendors"
} else {
    Join-Path $kit "vendors"
}

Write-Host "Vendors dir:   $vendors"

# --------------------------------------------------
# Localiza app_gui.py (OBLIGATORIO)
# --------------------------------------------------
$appGui = Join-Path $kit "app_gui.py"
if (-not (Test-Path $appGui)) {
    Write-Host "ERROR: No se encuentra app_gui.py en $kit" -ForegroundColor Red
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
    foreach ($p in $paths) {
        if (Test-Path $p) { return $p }
    }
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
        Write-Host "ERROR: No se encuentra python-3.10.11-amd64.exe en vendors" -ForegroundColor Red
        exit 1
    }

    Write-Host "Instalando Python 3.10 (silencioso, per-user)..." -ForegroundColor Yellow
    Start-Process -FilePath $installer `
        -ArgumentList '/quiet','InstallAllUsers=0','Include_launcher=1','PrependPath=1' `
        -Wait
}

$PY = Get-Python310
if (-not $PY) {
    Install-Python310
    $PY = Get-Python310
}

if (-not $PY) {
    Write-Host "ERROR: No se pudo instalar Python 3.10" -ForegroundColor Red
    exit 1
}

Write-Host "Python listo: $PY" -ForegroundColor Green

# --------------------------------------------------
# Got 2.52
# --------------------------------------------------
function Get-Git {
    try {
        $p = Start-Process "git" -ArgumentList "--version" -NoNewWindow -Wait -PassThru
        if ($p.ExitCode -eq 0) {
            return (Get-Command git).Source
        }
    } catch {}
    return $null
}

# --------------------------------------------------
# Git (OBLIGATORIO para Automatic1111)
# --------------------------------------------------
function Install-Git {
    $gitInstaller = Join-Path $vendors "Git-2.52.0-64-bit.exe"
    if (-not (Test-Path $gitInstaller)) {
        Write-Host ""
        Write-Host "ERROR: Git no está instalado y no se encuentra el instalador en vendors." -ForegroundColor Red
        Write-Host "Se esperaba:" -ForegroundColor Yellow
        Write-Host $gitInstaller -ForegroundColor Cyan
        Write-Host ""
        exit 1
    }

    Write-Host "Instalando Git (silencioso)..." -ForegroundColor Yellow

    Start-Process -FilePath $gitInstaller `
        -ArgumentList '/VERYSILENT','/NORESTART','/NOCANCEL','/SP-','/SUPPRESSMSGBOXES' `
        -Wait
}

$GIT = Get-Git
if (-not $GIT) {
    Install-Git
    $GIT = Get-Git
}

if (-not $GIT) {
    Write-Host ""
    Write-Host "ERROR: Git no pudo instalarse correctamente." -ForegroundColor Red
    Write-Host "Reinicia sesión o el sistema y vuelve a ejecutar." -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

Write-Host "Git listo: $GIT" -ForegroundColor Green


# --------------------------------------------------
# Auto-update del repo (seguro)
# --------------------------------------------------
if (Test-Path (Join-Path $root ".git")) {
    try {
        git fetch origin | Out-Null

        $local  = git rev-parse HEAD
        $remote = git rev-parse origin/main

        if ($local -ne $remote) {
            Write-Host "Actualización disponible del proyecto." -ForegroundColor Yellow
            Write-Host "Aplicando actualización..." -ForegroundColor Cyan

            $updater = Join-Path $kit "update_repo.ps1"
            if (Test-Path $updater) {
                Start-Process powershell `
                    -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-File",$updater,"-RepoRoot",$root `
                    -Wait
                exit 0
            }
        }
    } catch {
        Write-Host "Aviso: no se pudo comprobar actualización del repo." -ForegroundColor Yellow
    }
}


# --------------------------------------------------
# venv del batchkit
# --------------------------------------------------
$venvDir = Join-Path $kit ".venv"
$venvPy  = Join-Path $venvDir "Scripts\python.exe"
$venvPyW = Join-Path $venvDir "Scripts\pythonw.exe"

if (-not (Test-Path $venvPy)) {
    Write-Host "Creando entorno virtual (.venv)..." -ForegroundColor Cyan
    & $PY -m venv $venvDir
}

# pip básico
& $venvPy -m pip install --upgrade pip | Out-Null

$req = Join-Path $kit "requirements.txt"
if (Test-Path $req) {
    & $venvPy -m pip install -r $req | Out-Null
}

# asegurar dependencias mínimas GUI
& $venvPy -m pip install ttkbootstrap pyyaml requests pillow python-dotenv tqdm | Out-Null

# --------------------------------------------------
# Lanzar GUI (SIN consola)
# --------------------------------------------------
Write-Host "Lanzando interfaz gráfica..." -ForegroundColor Cyan

if (Test-Path $venvPyW) {
    Start-Process -WorkingDirectory $kit -FilePath $venvPyW -ArgumentList $appGui | Out-Null
} else {
    Start-Process -WorkingDirectory $kit -FilePath $venvPy  -ArgumentList $appGui | Out-Null
}

Write-Host "Listo. Puedes cerrar esta ventana." -ForegroundColor Green
