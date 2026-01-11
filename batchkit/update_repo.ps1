param(
    [string]$RepoRoot
)

$ErrorActionPreference = "Stop"

Set-Location $RepoRoot

Write-Host "== Actualizando IA-Images ==" -ForegroundColor Cyan

# Comprobación básica
if (-not (Test-Path ".git")) {
    Write-Host "No es un repositorio Git, se omite actualización." -ForegroundColor Yellow
    exit 0
}

if (git status --porcelain) {
    Write-Host "Cambios locales detectados. No se auto-actualiza." -ForegroundColor Red
    exit 1
}

git fetch origin

$local  = git rev-parse HEAD
$remote = git rev-parse origin/main

if ($local -eq $remote) {
    Write-Host "Repositorio ya actualizado." -ForegroundColor Green
    exit 0
}

Write-Host "Actualizaciones detectadas. Aplicando..." -ForegroundColor Yellow

git pull --rebase

Write-Host "Repositorio actualizado correctamente." -ForegroundColor Green

# Relanzar app
$startBat = Join-Path $RepoRoot "start.bat"
if (Test-Path $startBat) {
    Start-Process -FilePath $startBat
}
