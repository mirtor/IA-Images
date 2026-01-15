param([string]$RepoRoot)

Set-Location $RepoRoot

# No es repo git
if (-not (Test-Path ".git")) { return }

function Fail($msg) {
    Write-Host $msg -ForegroundColor Yellow
    return
}

try {
    # Fetch
    git fetch --prune origin | Out-Null
    if ($LASTEXITCODE -ne 0) { Fail "Aviso: git fetch fallo. No se pudo comprobar la actualizacion."; return }

    # Rama local (puede estar vacia si detached HEAD)
    $branch = (git branch --show-current).Trim()

    # Determinar ref remoto objetivo
    $remoteRef = $null

    if ($branch) {
        # Verifica si existe origin/<branch>
        git rev-parse --verify "origin/$branch" | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $remoteRef = "origin/$branch"
        }
    }

    if (-not $remoteRef) {
        # Intentar origin/HEAD (suele apuntar a la rama por defecto)
        $headRef = (git symbolic-ref -q --short refs/remotes/origin/HEAD).Trim()  # devuelve algo como "origin/main"
        if ($headRef) {
            $remoteRef = $headRef
        }
    }

    if (-not $remoteRef) {
        # Fallbacks comunes
        git rev-parse --verify "origin/main" | Out-Null
        if ($LASTEXITCODE -eq 0) { $remoteRef = "origin/main" }
    }
    if (-not $remoteRef) {
        git rev-parse --verify "origin/master" | Out-Null
        if ($LASTEXITCODE -eq 0) { $remoteRef = "origin/master" }
    }

    if (-not $remoteRef) { Fail "No se pudo detectar la rama remota objetivo (origin/main o origin/master)."; return }

    # Cambios locales -> preguntar
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
        if ($LASTEXITCODE -ne 0) { Fail "Error: git reset fallo. No se pudo descartar cambios."; return }

        git clean -fd | Out-Null
        if ($LASTEXITCODE -ne 0) { Fail "Error: git clean fallo. No se pudo limpiar archivos."; return }

        Write-Host "Cambios locales descartados." -ForegroundColor Green
        Write-Host ""
    }

    # Comparar commits
    $local  = (git rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0) { Fail "Error: no se pudo leer HEAD local."; return }

    $remote = (git rev-parse $remoteRef).Trim()
    if ($LASTEXITCODE -ne 0) { Fail "Error: no se pudo leer $remoteRef."; return }

    if ($local -eq $remote) {
        Write-Host "El proyecto ya esta en la ultima version." -ForegroundColor Green
        return
    }

    # Confirmar si realmente hay commits por traer
    $behind = (git rev-list --count "HEAD..$remoteRef").Trim()
    if ($LASTEXITCODE -ne 0) { Fail "Error: no se pudo calcular diferencias con $remoteRef."; return }

    if ([int]$behind -le 0) {
        Write-Host "El proyecto ya esta en la ultima version." -ForegroundColor Green
        return
    }

    Write-Host ""
    Write-Host "Actualizacion disponible del proyecto ($behind commit/s)." -ForegroundColor Cyan
    Write-Host "Aplicando actualizacion..." -ForegroundColor Cyan

    git pull --rebase origin ($remoteRef -replace "^origin/","") | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "Error: no se pudo aplicar la actualizacion (git pull --rebase fallo)." -ForegroundColor Yellow
        Write-Host "Revisa conflictos o ejecuta git pull manualmente." -ForegroundColor Yellow
        Write-Host ""
        return
    }

    Write-Host ""
    Write-Host "Proyecto actualizado correctamente." -ForegroundColor Green
    Write-Host ""
}
catch {
    Write-Host "Aviso: no se pudo comprobar o aplicar la actualizacion." -ForegroundColor Yellow
}
