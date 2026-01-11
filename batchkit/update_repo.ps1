param([string]$RepoRoot)

Set-Location $RepoRoot

# No es repo git
if (-not (Test-Path ".git")) {
    return
}

try {
    git fetch origin | Out-Null

    $branch = git branch --show-current
    if (-not $branch) {
        Write-Host "No se pudo detectar la rama actual." -ForegroundColor Yellow
        return
    }

    # CAMBIOS LOCALES
    $dirty = git status --porcelain
    if ($dirty) {
        Write-Host ""
        Write-Host "Cambios locales detectados." -ForegroundColor Yellow
        Write-Host "El proyecto NO se puede actualizar automaticamente." -ForegroundColor Yellow
        Write-Host ""

        $resp = Read-Host "Deseas DESCARTAR los cambios y actualizar? (S/N)"
        if ($resp.ToUpper() -ne "S") {
            Write-Host "Actualizacion cancelada por el usuario." -ForegroundColor Yellow
            Write-Host ""
            return
        }

        Write-Host ""
        Write-Host "Descartando cambios locales..." -ForegroundColor Cyan
        git reset --hard HEAD | Out-Null
        git clean -fd | Out-Null
        Write-Host "Cambios locales descartados." -ForegroundColor Green
        Write-Host ""
    }

    $local  = git rev-parse HEAD
    $remote = git rev-parse origin/$branch

    if ($local -eq $remote) {
        Write-Host "El proyecto ya esta en la ultima version." -ForegroundColor Green
        return
    }

    Write-Host ""
    Write-Host "Actualizacion disponible del proyecto." -ForegroundColor Cyan
    Write-Host "Aplicando actualizacion..." -ForegroundColor Cyan

    git pull --rebase

    Write-Host ""
    Write-Host "Proyecto actualizado correctamente." -ForegroundColor Green
    Write-Host ""
}
catch {
    Write-Host "Aviso: no se pudo comprobar o aplicar la actualizacion." -ForegroundColor Yellow
}
