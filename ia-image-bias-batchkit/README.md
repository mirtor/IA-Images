# IA-Images

Repo que combina **Stable Diffusion WebUI (AUTOMATIC1111)** como *submódulo* y un **batchkit** para generación en lote con prompts.

> WebUI (AUTOMATIC1111): https://github.com/AUTOMATIC1111/stable-diffusion-webui

---

## Estructura

```
IA-Images/
├─ ia-image-bias-batchkit/
│  ├─ out/                          # salidas (PNG + manifest.jsonl)
│  ├─ config.yaml                   # parámetros por defecto
│  ├─ generator.py                  # CLI para lotes y metadatos
│  ├─ prompts.csv                   # o prompts_reworked.csv (plantilla mejorada)
│  ├─ .gitignore
│  └─ README_batchkit_setup.md
├─ stable-diffusion-webui/          # submódulo de A1111
├─ run_batchkit.bat                 # lanzador 1-click (opcional)
└─ README.md
```

> **Nota sobre rutas de salida:** por defecto las imágenes van a `ia-image-bias-batchkit/out/automatic1111/`.  
> Si en tu equipo las ves en `E:\\IAimages\\ia-image-bias-batchkit\\out\\automatic1111`, es la misma carpeta vista con ruta absoluta.

---



## Primer uso rápido (Windows)

1) Copia un modelo `.safetensors` a:
   ```
   stable-diffusion-webui/models/Stable-diffusion/
   ```
   (SDXL Base para calidad alta o SD 1.5 para pruebas rápidas/512×512.)
2) Edita `stable-diffusion-webui/webui-user.bat` para apuntar a **Python 3.10** (mirar punto 3.1 de la guía rápida)
   (usa `py -0p` para ver rutas instaladas).
3) (Opcional) En `ia-image-bias-batchkit/config.yaml`, habilita `automatic1111` y ajusta parámetros.
4) **Doble clic a `run_batchkit.bat`**. El script:
   - Arranca WebUI
   - Espera a que la API responda (`http://127.0.0.1:7860`)
   - Crea/usa el venv del kit, instala requisitos si faltan
   - Lanza `generator.py` con tu `prompts.csv` y `config.yaml`

---

## Guía rápida: Lanzador y configuración del batchkit (Stable Diffusion local)

### 1) Requisitos

- **Python 3.10.11** instalado como administrador y agregado al **PATH**  
  Descarga: https://www.python.org/downloads/release/python-31011/
- Repos locales:
  - **Stable Diffusion WebUI (AUTOMATIC1111)** — https://github.com/AUTOMATIC1111/stable-diffusion-webui
  - `ia-image-bias-batchkit` (este proyecto)
- (GPU NVIDIA) Drivers actualizados.

> El **lanzador `run_batchkit.bat`** instala y lanza todo automáticamente.  
> Aun así, revisa **`webui-user.bat`** según el equipo (GPU/CPU).

### 2) Dónde se guardan las imágenes

```
ia-image-bias-batchkit/out/automatic1111
```

### 3) Instalación manual (local)

> También puede ejecutarse en la nube; aquí se documenta la **instalación local**.

#### 3.1 Stable Diffusion WebUI (AUTOMATIC1111)

Repositorio oficial: https://github.com/AUTOMATIC1111/stable-diffusion-webui

```bash
git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui.git
```

Edita **`webui-user.bat`** (ajusta la ruta de Python 3.10 con `py -0p`).  
Si las instalaciones fallan, **borra la carpeta `venv/`** y vuelve a lanzar.

```bat
@echo off

:: Fuerza Python 3.10 usando ruta completa (ver con py -0p)
set PYTHON="C:\Users\"USERNAME"\AppData\Local\Programs\Python\Python310\python.exe"

:: (opcional) Git externo
set GIT=

:: Deja que A1111 gestione el venv
set VENV_DIR=

:: GPU NVIDIA (recomendado): API + xformers + ahorro VRAM
set COMMANDLINE_ARGS=--api --xformers --medvram

:: Alternativa 100% CPU (si no existe gráfica NVIDIA)
:: set COMMANDLINE_ARGS=--api --use-cpu all --no-half --no-half-vae --medvram --skip-torch-cuda-test

call webui.bat
```

Ejecuta con:

```bat
.\webui-user.bat
```

Interfaz: **http://127.0.0.1:7860** (API habilitada).

#### 3.2 Preparar y ejecutar el batchkit

En otra consola (PowerShell/CMD), dentro de `ia-image-bias-batchkit`:

```powershell
python -m venv .venv

# Si PowerShell bloquea:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
pip install pyyaml
```

Configura `config.yaml` (habilita `automatic1111`, deshabilita el resto) y revisa `prompts.csv`.

Lanza:

```powershell
python generator.py --provider automatic1111 --prompts prompts.csv --config config.yaml
```

---

## Parámetros recomendados (RTX 4080 SUPER)

`ia-image-bias-batchkit/config.yaml`:

```yaml
default:
  out_dir: "out"
  repeats: 30
  size: "1024x1024"        # SDXL nativo. Para prompts abstractos prueba 768x768 o 512x512
  temperature: null
  randomize_order: true
  concurrency: 2           # 4080 puede con 2; prueba 3 si la VRAM lo permite
  delay_seconds: 0
  seed: 12345              # fija para comparabilidad (null = aleatorio)

providers:
  openai:
    enabled: false
    model: "gpt-image-1"
    api_key_env: "OPENAI_API_KEY"

  stability:
    enabled: false
    engine: "sd3"
    api_base: "https://api.stability.ai"
    api_key_env: "STABILITY_API_KEY"

  automatic1111:
    enabled: true
    api_base: "http://127.0.0.1:7860"
    sampler_name: "DPM++ 2M Karras"
    steps: 30
    cfg_scale: 6.5
    seed: -1
```

> Si a 1024×1024 ves patrones “fractales”, prueba **768×768** o **512×512**; también puedes subir `steps` a 34–36 o bajar `cfg` a 5.5–6.5.

---

## Prompts (mejor práctica para “fotoperiodismo, realista, neutral”)

- Reformula “conceptos” como **escenas concretas**: sujetos, acción, lugar, luz, óptica.
- Ejemplo de plantilla:
  > *Photojournalistic shot of* **[sujeto/acción]** en **[lugar]**, **[luz/ambiente]**, **[composición]**, **[datos de cámara]**; **neutral tone, no sensationalism**.

Incluye la versión mejorada como `prompts_reworked.csv` (separador `;`), manteniendo `id, category, subcat, language, style, actor, geo_scope, prompt, prompt_id`.

---

## Salidas y metadatos

- PNGs con **hash SHA-256** en el nombre (o con prefijo por **prompt** si usas la opción de subcarpeta por prompt).
- `manifest.jsonl` con: prompt, categoría, proveedor, modelo, tamaño, semilla, latencia y respuesta cruda.

> Para agrupar imágenes por prompt: el script puede guardar en `out/<proveedor>/<prompt_id>/...`.

---

## Notas y troubleshooting

- Si WebUI no arranca o no instala dependencias, borra `stable-diffusion-webui/venv/` y vuelve a lanzar.
- Si el lanzador `.bat` está bloqueado:
  - Botón derecho → Propiedades → **Desbloquear**, o
  - `Unblock-File .\run_batchkit.bat`, o
  - renómbralo a `.cmd`, o ejecútalo desde **CMD**.
- Si el batchkit falla con acentos en el CSV:
  - Guarda como **CSV UTF-8** (Excel: “CSV UTF-8 (delimitado por comas)”).
  - El lector es tolerante a `;` o `,`.  
- Si ves **Out of Memory** en GPU:
  - Reduce tamaño (768→512), baja steps (30→22), mantén batch 1.

---

## Actualizar el submódulo (A1111)

```bash
cd stable-diffusion-webui
git pull origin master
cd ..
git add stable-diffusion-webui
git commit -m "chore: bump A1111 submodule"
git push
```

---

## .gitignore recomendado (batchkit)

Ignora salidas y entornos locales:

```
/out/
/out/**
.venv/
__pycache__/
*.py[cod]
.env
.vscode/
.idea/
.DS_Store
Thumbs.db
```

> No subas **modelos** ni artefactos del sistema.
