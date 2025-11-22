@echo off
setlocal ENABLEEXTENSIONS

REM === Paths relative to repo root ===
set "ROOT=%~dp0"
set "WEBUI_DIR=%ROOT%stable-diffusion-webui"
set "KIT_DIR=%ROOT%ia-image-bias-batchkit"

REM Override de tamaño (vacío para usar config.yaml)
set "OVERRIDE_SIZE=512x512"

echo [1/5] Lanzando WebUI (AUTOMATIC1111)...
pushd "%WEBUI_DIR%"
start "" cmd /c call webui-user.bat
popd

echo [2/5] Esperando a que la API responda...
for /L %%i in (1,1,60) do (
  powershell -NoProfile -Command ^
    "try{(Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:7860/sdapi/v1/samplers' -TimeoutSec 2)>$null;exit 0}catch{exit 1}"
  if not errorlevel 1 goto :API_READY
  >nul ping 127.0.0.1 -n 2
)
echo [!] No se detecto la API tras ~60 intentos.
goto :END

:API_READY
echo [OK] API detectada.

echo [3/5] Preparando entorno del batchkit...
pushd "%KIT_DIR%"
if not exist ".venv\Scripts\python.exe" (
  echo    - Creando venv con Python 3.10...
  py -3.10 -m venv .venv
)

".venv\Scripts\python.exe" -c "import tqdm" 2>nul
if errorlevel 1 (
  echo    - Instalando requirements...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  ".venv\Scripts\python.exe" -m pip install pyyaml
)

echo [4/5] Ejecutando generacion por lotes...
set "EXTRA_ARGS="
if not "%OVERRIDE_SIZE%"=="" set "EXTRA_ARGS=--size %OVERRIDE_SIZE%"

".venv\Scripts\python.exe" generator.py --provider automatic1111 --prompts prompts.csv --config config.yaml %EXTRA_ARGS%
set "RET=%ERRORLEVEL%"
popd

echo [5/5] Hecho. Codigo de salida: %RET%

:END
endlocal
