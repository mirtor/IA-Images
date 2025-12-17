@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Carpeta donde está Start.bat
set "SCRIPT_DIR=%~dp0"

REM Ruta por defecto: raiz
set "BOOTSTRAP=%SCRIPT_DIR%bootstrap.ps1"

REM Si no existe en raiz, probar en batchkit\
if not exist "%BOOTSTRAP%" (
  if exist "%SCRIPT_DIR%batchkit\bootstrap.ps1" (
    set "BOOTSTRAP=%SCRIPT_DIR%batchkit\bootstrap.ps1"
  )
)

REM Si no se encontró en ninguno de los dos sitios, abortar
if not exist "%BOOTSTRAP%" (
  echo [ERROR] No se encontro 'bootstrap.ps1' ni en la raiz ni en 'batchkit\'.
  exit /b 1
)

REM Ejecutar el bootstrap con PowerShell permitiendo scripts
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%BOOTSTRAP%"
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
  echo.
  echo Hubo un error durante la preparacion. Revisa la ventana anterior para mas detalles.
  pause
)

endlocal & exit /b %RC%
