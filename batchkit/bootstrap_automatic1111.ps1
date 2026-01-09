# bootstrap_automatic1111.ps1
# Instala / reinstala Automatic1111 (Stable Diffusion WebUI)
# NO lanza la GUI principal

try {
    $ErrorActionPreference = "Stop"

    # ---------- RUTAS BASE ----------
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $root = Split-Path -Parent $scriptDir
    $kit  = $scriptDir

    Set-Location $root

    Write-Host "== IA-Images :: Instalador Automatic1111 ==" -ForegroundColor Cyan
    Write-Host "Proyecto : $root"
    Write-Host "Batchkit : $kit"
    Write-Host ""

    # ---------- HELPERS ----------
    function Ensure-Dir($p) {
        if (-not (Test-Path $p)) {
            New-Item -ItemType Directory -Path $p | Out-Null
        }
    }

    function Has-Nvidia {
        try {
            $p = Start-Process "cmd.exe" -ArgumentList "/c","nvidia-smi" -NoNewWindow -Wait -PassThru
            return ($p.ExitCode -eq 0)
        } catch {
            return $false
        }
    }

    # ---------- PYTHON ----------
    function Get-Python310 {
        $candidates = @(
            "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
            "$env:ProgramFiles\Python310\python.exe"
        )
        foreach ($p in $candidates) {
            if (Test-Path $p) { return $p }
        }
        return $null
    }

    $PY = Get-Python310
    if (-not $PY) {
        Write-Host "ERROR: Python 3.10 no encontrado." -ForegroundColor Red
        throw "Python 3.10 requerido"
    }

    Write-Host "Python encontrado: $PY" -ForegroundColor Green
    Write-Host ""

    # ---------- A1111 ----------
    $webuiDir = Join-Path $root "stable-diffusion-webui"
    $zipUrl   = "https://codeload.github.com/AUTOMATIC1111/stable-diffusion-webui/zip/refs/heads/master"
    $zipPath  = Join-Path $env:TEMP "stable-diffusion-webui.zip"
    $tmpDir   = Join-Path $env:TEMP "a1111_tmp"

    if (Test-Path $webuiDir) {
        Write-Host "Eliminando instalacion previa..." -ForegroundColor Yellow
        Remove-Item $webuiDir -Recurse -Force
    }

    Write-Host "Descargando Automatic1111..." -ForegroundColor Cyan
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
    Invoke-WebRequest -UseBasicParsing -Uri $zipUrl -OutFile $zipPath

    if (Test-Path $tmpDir) { Remove-Item $tmpDir -Recurse -Force }
    Expand-Archive -Path $zipPath -DestinationPath $tmpDir -Force

    Move-Item (Join-Path $tmpDir "stable-diffusion-webui-master") $webuiDir
    Remove-Item $tmpDir -Recurse -Force
    Remove-Item $zipPath -Force

    Write-Host "Automatic1111 descargado correctamente." -ForegroundColor Green
    Write-Host ""

    # ---------- GPU ----------
    $hasNvidia = Has-Nvidia
    $cmdArgs = if ($hasNvidia) {
        "--api --xformers --medvram"
        } else {
        "--api --use-cpu all --no-half --no-half-vae --medvram --skip-torch-cuda-test"
        }

    # ---------- webui-user.bat ----------
    $webuiUser = Join-Path $webuiDir "webui-user.bat"

@"
@echo off
set PYTHON=$PY
set VENV_DIR=
set COMMANDLINE_ARGS=$cmdArgs
REM Fuerza repo válido de Stable Diffusion (evita repo eliminado)
set "STABLE_DIFFUSION_REPO=https://github.com/w-e-w/stablediffusion.git"
call webui.bat
"@ | Set-Content -Path $webuiUser -Encoding ASCII -Force

    Write-Host "webui-user.bat configurado." -ForegroundColor Green
    Write-Host ""

    # ---------- MODELOS ----------
    $modelsDir = Join-Path $webuiDir "models\Stable-diffusion"
    Ensure-Dir $modelsDir

    Write-Host "Recuerda copiar un modelo (.safetensors) en:"
    Write-Host $modelsDir -ForegroundColor Cyan
    Write-Host ""

    Write-Host "Instalacion de Automatic1111 COMPLETADA." -ForegroundColor Green
    Write-Host ""
    Write-Host "Pulsa cualquier tecla para cerrar..."
    [void][System.Console]::ReadKey($true)
    exit 0
}
catch {
    Write-Host ""
    Write-Host "ERROR durante la instalacion" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Write-Host "Pulsa cualquier tecla para cerrar..."
    [void][System.Console]::ReadKey($true)
    exit 1
}
