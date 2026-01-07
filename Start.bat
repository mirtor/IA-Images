@echo off
setlocal EnableExtensions

powershell -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0batchkit\bootstrap_min.ps1"

if %ERRORLEVEL% NEQ 0 (
  echo.
  echo Hubo un error durante el arranque.
  pause
)

endlocal
