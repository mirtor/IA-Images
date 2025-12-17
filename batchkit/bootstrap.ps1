# bootstrap.ps1 — instala/descarga lo necesario y lanza la app
# Funciona estando en la raiz o en batchkit; vendors puede estar en cualquiera

$ErrorActionPreference = "Stop"

# --- Localiza rutas base ---
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if ((Split-Path -Leaf $scriptDir) -ieq "batchkit") {
  $root = Split-Path -Parent $scriptDir   # raiz del proyecto
  $kit  = $scriptDir
} else {
  $root = $scriptDir
  $kit  = Join-Path $root "batchkit"
}
Set-Location $root
Write-Host "== IA-Images bootstrap ==" -ForegroundColor Cyan
Write-Host "Project root: $root"
Write-Host "Batchkit dir: $kit"

# vendors: prioriza en raiz; si no existe, usa vendors dentro de batchkit
$vendorsDir = if (Test-Path (Join-Path $root "vendors")) { Join-Path $root "vendors" } else { Join-Path $kit "vendors" }
Write-Host "Vendors dir:  $vendorsDir"

# ---------------- helpers ----------------
function Test-Command($name) { try { Get-Command $name -ErrorAction Stop | Out-Null; $true } catch { $false } }
function Ensure-Dir($p) { if (-not (Test-Path $p)) { New-Item -ItemType Directory -Path $p | Out-Null } }
function Is-Admin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  $p  = New-Object Security.Principal.WindowsPrincipal($id)
  return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}
function Get-Python310 {
  $pf = "$env:ProgramFiles\Python310\python.exe"
  $la = "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe"
  if (Test-Path $pf) { return $pf }
  if (Test-Path $la) { return $la }
  if (Test-Command "py") {
    try {
      $exe = & py -3.10 -c "import sys; print(sys.executable)"
      if ($LASTEXITCODE -eq 0 -and $exe -and (Test-Path $exe)) { return $exe.Trim() }
    } catch {}
  }
  return $null
}
function Install-Python310 {
  param([string]$vendorPath)

  $silentArgsUser = '/quiet','InstallAllUsers=0',"TargetDir=$env:LOCALAPPDATA\Programs\Python\Python310",'Include_launcher=1','PrependPath=1','SimpleInstall=1'
  $silentArgsAll  = '/quiet','InstallAllUsers=1',"TargetDir=$env:ProgramFiles\Python310",'Include_launcher=1','PrependPath=1','SimpleInstall=1'

  if (-not (Test-Path $vendorPath)) {
    Write-Host "Descargando Python 3.10.11..." -ForegroundColor Yellow
    $vendorPath = Join-Path $env:TEMP "python-3.10.11-amd64.exe"
    Invoke-WebRequest -UseBasicParsing -Uri "https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe" -OutFile $vendorPath
  } else {
    Write-Host "Usando instalador local: $vendorPath"
  }

  Write-Host "Instalando Python (per-user, silencioso)..." -ForegroundColor DarkCyan
  $p = Start-Process -FilePath $vendorPath -ArgumentList $silentArgsUser -Wait -PassThru
  $py = Get-Python310
  if ($py) { return $py }

  if (Is-Admin) {
    Write-Host "Reintentando instalacion (all-users, silencioso)..." -ForegroundColor DarkCyan
    $p = Start-Process -FilePath $vendorPath -ArgumentList $silentArgsAll -Wait -PassThru
    $py = Get-Python310
    if ($py) { return $py }
  }

  Write-Host "No se pudo instalar silenciosamente. Abriendo instalador en modo GUI..." -ForegroundColor Yellow
  Start-Process -FilePath $vendorPath
  Write-Host "Cuando termine la instalacion, pulsa una tecla para continuar..." -ForegroundColor Yellow
  [void][System.Console]::ReadKey($true)
  return (Get-Python310)
}

# ------------ Rutas de vendors ------------
$pyLocalExe     = Join-Path $vendorsDir "python-3.10.11-amd64.exe"
$localA1111Dir  = Join-Path $vendorsDir "stable-diffusion-webui"      # carpeta ya descomprimida
$localA1111Zip  = Join-Path $vendorsDir "stable-diffusion-webui.zip"  # opcional
$zipUrlA1111    = "https://codeload.github.com/AUTOMATIC1111/stable-diffusion-webui/zip/refs/heads/master"

# ---------------- Python 3.10 ----------------
$PY = Get-Python310
if (-not $PY) {
  Write-Host "Python 3.10 no encontrado. Instalando..." -ForegroundColor Yellow
  $PY = Install-Python310 -vendorPath $pyLocalExe
}
if (-not $PY) { Write-Host "No pude instalar/encontrar Python 3.10. Aborto." -ForegroundColor Red; exit 1 }
Write-Host "Python 3.10 listo: $PY" -ForegroundColor Green

# ---------------- Stable Diffusion WebUI  ----------------
$webuiDir = Join-Path $root "stable-diffusion-webui"
if (-not (Test-Path $webuiDir)) {
  Write-Host "Preparando Stable Diffusion WebUI (AUTOMATIC1111)..." -ForegroundColor Cyan

  if (Test-Path $localA1111Dir) {
    Write-Host "Usando carpeta local: $localA1111Dir" -ForegroundColor Green
    Ensure-Dir $webuiDir
    Copy-Item -Path (Join-Path $localA1111Dir '*') -Destination $webuiDir -Recurse -Force
  }
  elseif (Test-Path $localA1111Zip) {
    Write-Host "Usando ZIP local: $localA1111Zip" -ForegroundColor Green
    $tmpUnzip = Join-Path $env:TEMP "a1111_unzip"
    if (Test-Path $tmpUnzip) { Remove-Item -Recurse -Force $tmpUnzip }
    Expand-Archive -Path $localA1111Zip -DestinationPath $tmpUnzip -Force
    Move-Item -Force (Join-Path $tmpUnzip "stable-diffusion-webui-master") $webuiDir
    Remove-Item $tmpUnzip -Recurse -Force
  }
  else {
    Write-Host "No hay copia local. Intentando descarga..." -ForegroundColor Yellow
    $zipPath  = Join-Path $env:TEMP "stable-diffusion-webui.zip"
    $tmpUnzip = Join-Path $env:TEMP "a1111_unzip"
    if (Test-Path $zipPath)  { Remove-Item -Force $zipPath }
    if (Test-Path $tmpUnzip) { Remove-Item -Recurse -Force $tmpUnzip }
    Invoke-WebRequest -UseBasicParsing -Uri $zipUrlA1111 -OutFile $zipPath
    Expand-Archive -Path $zipPath -DestinationPath $tmpUnzip -Force
    Move-Item -Force (Join-Path $tmpUnzip "stable-diffusion-webui-master") $webuiDir
    Remove-Item $zipPath -Force
    Remove-Item $tmpUnzip -Recurse -Force
  }
} else {
  Write-Host "Carpeta A1111 ya existe; se reutiliza."
}

# ---------------- Detectar GPU ----------------
function Has-Nvidia {
  try { $p = Start-Process -FilePath "cmd.exe" -ArgumentList "/c","nvidia-smi" -NoNewWindow -PassThru -Wait; return ($p.ExitCode -eq 0) }
  catch { return $false }
}
$hasNvidia = Has-Nvidia
if ($hasNvidia) { Write-Host "GPU NVIDIA detectada." -ForegroundColor Green }
else { Write-Host "No se detecta GPU NVIDIA. Se configurará modo CPU." -ForegroundColor Yellow }

# ---------------- webui-user.bat ----------------
$cmdArgs = if ($hasNvidia) { "--api --xformers --medvram" } else { "--api --use-cpu all --no-half --no-half-vae --medvram --skip-torch-cuda-test" }
$webuiUser = Join-Path $webuiDir "webui-user.bat"
@"
@echo off
set "PYTHON=$PY"
set VENV_DIR=
set "COMMANDLINE_ARGS=$cmdArgs"
call webui.bat
"@ | Out-File -FilePath $webuiUser -Encoding ASCII -Force
Write-Host "webui-user.bat configurado." -ForegroundColor Green

# ---------------- Recordatorio modelos ----------------
$modelsDir = Join-Path $webuiDir "models\Stable-diffusion"
Ensure-Dir $modelsDir
Write-Host "Recuerda copiar un modelo (.safetensors) en: $modelsDir" -ForegroundColor Yellow

# ---------------- venv batchkit ----------------
$venv   = Join-Path $kit ".venv"
$venvPy = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
  Write-Host "Creando venv de batchkit..."
  & $PY -m venv $venv
}
Write-Host "Instalando requirements del batchkit..."
& $venvPy -m pip install --upgrade pip
$req = Join-Path $kit "requirements.txt"
if (Test-Path $req) { & $venvPy -m pip install -r $req }
& $venvPy -m pip install pyyaml requests tqdm pillow python-dotenv ttkbootstrap

# ---------------- Arrancar WebUI (oculto, en paralelo) ----------------
Write-Host "Arrancando Stable Diffusion WebUI (oculto)..." -ForegroundColor Cyan

# 1) Creamos (si no existe) un lanzador VBScript que ejecuta un .bat oculto
$runHiddenVbs = Join-Path $vendorsDir "run_hidden.vbs"
if (-not (Test-Path $runHiddenVbs)) {
  @"
' run_hidden.vbs — ejecuta un .bat oculto, situando el CWD al del .bat
If WScript.Arguments.Count = 0 Then WScript.Quit 1
Set fso = CreateObject("Scripting.FileSystemObject")
batPath = WScript.Arguments(0)
If Not fso.FileExists(batPath) Then WScript.Quit 2
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = fso.GetParentFolderName(batPath)
cmd = "cmd.exe /c call " & Chr(34) & batPath & Chr(34)
' 0 = oculto, False = no esperar
shell.Run cmd, 0, False
"@ | Out-File -FilePath $runHiddenVbs -Encoding ASCII -Force
}

# 2) Lanzamos webui-user.bat oculto con wscript.exe
$webuiUser = Join-Path $webuiDir "webui-user.bat"
if (-not (Test-Path $webuiUser)) {
  Write-Host "ERROR: no existe $webuiUser" -ForegroundColor Red
  exit 1
}
Start-Process -FilePath "wscript.exe" -ArgumentList "`"$runHiddenVbs`"","`"$webuiUser`"" | Out-Null


# ---------------- Probar API (rápido) ----------------
function Test-A1111Api {
  param([string]$base = "http://127.0.0.1:7860")
  try { $r = Invoke-WebRequest -UseBasicParsing -Uri "$base/sdapi/v1/progress?skip_current_image=true" -TimeoutSec 2; return $r.StatusCode -eq 200 }
  catch { return $false }
}
Write-Host "Comprobando API 7860..." -NoNewline
for ($i=0; $i -lt 25; $i++) { if (Test-A1111Api) { Write-Host " OK" -ForegroundColor Green; break }; Start-Sleep -Seconds 1 }
if (-not (Test-A1111Api)) { Write-Host "`nLa API puede tardar mas; sigue iniciando en 2º plano." -ForegroundColor Yellow }

# ---------------- Lanzar GUI ----------------
# Busca app_gui.py en raíz o en batchkit/
$guiRoot    = Join-Path $root "app_gui.py"
$guiInKit   = Join-Path $root "batchkit\app_gui.py"

$guiPath = $null
$workDir = $root
if (Test-Path $guiRoot) {
  $guiPath = $guiRoot
  $workDir = $root
} elseif (Test-Path $guiInKit) {
  $guiPath = $guiInKit
  $workDir = (Join-Path $root "batchkit")
} else {
  Write-Host "ERROR: no encuentro app_gui.py ni en $guiRoot ni en $guiInKit" -ForegroundColor Red
  exit 1
}

$venvPy  = Join-Path $venv "Scripts\python.exe"
$venvPyW = Join-Path $venv "Scripts\pythonw.exe"

Write-Host "Intérprete venv (python):  $venvPy"
Write-Host "Intérprete venv (pythonw): $venvPyW"
Write-Host "Ruta GUI: $guiPath"
Write-Host "WorkingDir GUI: $workDir"

if (-not (Test-Path $venvPy)) {
  Write-Host "ERROR: no encuentro el intérprete del venv en $venvPy" -ForegroundColor Red
  exit 1
}

# Preferimos pythonw.exe (sin consola) si existe
if (Test-Path $venvPyW) {
  Write-Host "Lanzando interfaz (pythonw)..." -ForegroundColor Cyan
  Start-Process -WorkingDirectory $workDir -FilePath $venvPyW -ArgumentList @($guiPath) `
    -WindowStyle Normal | Out-Null
} else {
  Write-Host "Lanzando interfaz (python)..." -ForegroundColor Cyan
  Start-Process -WorkingDirectory $workDir -FilePath $venvPy -ArgumentList @($guiPath) `
    -WindowStyle Normal | Out-Null
}

# Fallback: si en 3s no detectamos proceso, ejecuta en primer plano para mostrar errores
Start-Sleep -Seconds 3
$running = Get-Process | Where-Object { $_.Path -and ($_.Path -ieq $venvPyW -or $_.Path -ieq $venvPy) }
if (-not $running) {
  Write-Host "No parece haberse lanzado la GUI; intento en primer plano para ver errores..." -ForegroundColor Yellow
  & $venvPy $guiPath
}

Write-Host "Listo. Puedes cerrar esta ventana." -ForegroundColor Green