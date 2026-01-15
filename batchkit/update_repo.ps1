param(
    [Parameter(Mandatory=$true)][string]$RepoRoot,
    [Parameter(Mandatory=$true)][string]$RemoteUrl
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $RepoRoot)) { return }
Set-Location $RepoRoot

# Si no hay RemoteUrl valido, no hacemos nada
if (-not $RemoteUrl -or $RemoteUrl -match "PON_AQUI_TU_REPO") {
    Write-Host "Aviso: RemoteUrl no configurado. Omito auto-update." -ForegroundColor Yellow
    return
}

function Has-Git {
    return [bool](Get-Command git -ErrorAction SilentlyContinue)
}

function Is-Dirty {
    $s = git status --porcelain
    return [bool]$s
}

function Ask-Discard {
    $ans = Read-Host "Hay cambios locales sin guardar. Quieres descartarlos y actualizar? (y/N)"
    return ($ans -eq "y" -or $ans -eq "Y")
}

function Safe-Reset-Hard {
    git reset --hard | Out-Null
    git clean -fd | Out-Null
}

function Get-Branch {
    $b = (git branch --show-current)
    if ($b) { return $b.Trim() }
    return "main"
}

function Update-Repo-With-Git {
    git fetch origin | Out-Null

    $branch = Get-Branch
    $local  = (git rev-parse HEAD).Trim()
    $remote = (git rev-parse "origin/$branch").Trim()

    if ($local -eq $remote) {
        Write-Host "El proyecto ya esta en la ultima version." -ForegroundColor Green
        return
    }

    if (Is-Dirty) {
        Write-Host ""
        Write-Host "Cambios locales detectados." -ForegroundColor Yellow
        if (Ask-Discard) {
            Write-Host "Descartando cambios locales..." -ForegroundColor Yellow
            Safe-Reset-Hard
        } else {
            Write-Host "No se actualiza automaticamente." -ForegroundColor Yellow
            return
        }
    }

    Write-Host ""
    Write-Host "Actualizacion disponible. Aplicando..." -ForegroundColor Cyan
    git pull --rebase | Out-Null
    Write-Host "Proyecto actualizado correctamente." -ForegroundColor Green
}

function Copy-Updated-ZipClone-To-RepoRoot {
    param([string]$Src, [string]$Dst)

    # Carpetas/archivos a NO tocar
    $excludeDirs = @(
        "out",
        "stable-diffusion-webui",
        "vendors",
        ".venv"
    )

    $excludeFiles = @(
        "batchkit\.env",
        "batchkit\config.yaml"
    )

    # Copia general (sin borrar nada del usuario)
    # Robocopy devuelve codigos con bits; 0/1 son OK (sin cambios / con cambios)
    $args = @(
        "`"$Src`"", "`"$Dst`"",
        "/E", "/COPY:DAT", "/R:1", "/W:1", "/NP", "/NFL", "/NDL"
    )

    foreach ($d in $excludeDirs) { $args += @("/XD", (Join-Path $Dst $d)) }
    foreach ($f in $excludeFiles) { $args += @("/XF", (Join-Path $Dst $f)) }

    $p = Start-Process -FilePath "robocopy" -ArgumentList $args -NoNewWindow -Wait -PassThru
    if ($p.ExitCode -ge 8) {
        throw "Robocopy fallo con codigo $($p.ExitCode)"
    }
}

function Update-Repo-From-ZipUser {
    if (-not (Has-Git)) {
        Write-Host "Aviso: Git no disponible, no puedo actualizar un ZIP sin Git." -ForegroundColor Yellow
        return
    }

    # Si hay cambios locales (en ZIP no hay .git pero puede haber edits), preguntamos igualmente
    # (solo comprobamos si existen archivos modificados respecto a nada? no se puede comparar)
    # Regla: si existen .env/config locales, los respetamos SIEMPRE por exclusiones.

    $tmp = Join-Path $env:TEMP ("iaimages_update_" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $tmp | Out-Null

    try {
        Write-Host ""
        Write-Host "El proyecto parece venir de un ZIP (sin .git)." -ForegroundColor Yellow
        Write-Host "Descargando ultima version y convirtiendo a repo..." -ForegroundColor Cyan

        git clone --depth 1 $RemoteUrl $tmp | Out-Null

        # Copiar (incluye .git del clone), sin pisar config/.env/out/webui
        Copy-Updated-ZipClone-To-RepoRoot -Src $tmp -Dst $RepoRoot

        Write-Host "Proyecto actualizado correctamente (ZIP -> repo)." -ForegroundColor Green
    }
    finally {
        try { Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue } catch {}
    }
}

# -----------------------------
# MAIN
# -----------------------------
if (-not (Has-Git)) {
    Write-Host "Aviso: Git no disponible. Omito auto-update." -ForegroundColor Yellow
    return
}

if (Test-Path (Join-Path $RepoRoot ".git")) {
    # Repo normal
    try {
        # Asegura origin (por si acaso)
        $hasOrigin = $false
        try {
            $remotes = git remote
            if ($remotes -match "origin") { $hasOrigin = $true }
        } catch {}

        if (-not $hasOrigin) {
            git remote add origin $RemoteUrl | Out-Null
        }

        Update-Repo-With-Git
    } catch {
        Write-Host "Aviso: no se pudo comprobar o aplicar la actualizacion (git)." -ForegroundColor Yellow
    }
} else {
    # ZIP
    try {
        Update-Repo-From-ZipUser
    } catch {
        Write-Host "Aviso: no se pudo actualizar desde ZIP." -ForegroundColor Yellow
    }
}
