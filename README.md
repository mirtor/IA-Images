# IA‑Images (Windows)

Interfaz sencilla para ejecutar lotes de generación de imágenes con **Stable Diffusion WebUI (AUTOMATIC1111)** o APIs (OpenAI/Stability). Pensado para que cualquier persona lo ponga en marcha con doble clic, sin instalar nada manualmente.

---

## ✅ Requisitos

- **Windows 10/11** (64‑bit).
- **Conexión a Internet** (recomendada). Si no hay, puedes incluir `vendors\stable-diffusion-webui` ya descomprimido.
- **GPU NVIDIA** opcional. Si no hay, funciona en **CPU** (más lento).
- Permisos para ejecutar **PowerShell** (el lanzador usa `ExecutionPolicy Bypass`).

---

## 📦 ¿Qué viene en el ZIP?

Estructura recomendada del proyecto:

```
IA-Images/
├─ Start.bat
├─ bootstrap.ps1                 # Bootstrap: instala Python, prepara WebUI y lanza la GUI
├─ vendors/                      # Recursos opcionales
│  ├─ python-3.10.11-amd64.exe   # Instalador offline de Python 3.10 (opcional)
│  └─ stable-diffusion-webui/    # Copia LOCAL descomprimida de A1111 (opcional)
├─ stable-diffusion-webui/       # Se crea al primer inicio (si no existe)
└─ batchkit/
   ├─ app_gui.py                 # La aplicación gráfica (Tkinter + ttkbootstrap)
   ├─ generator.py               # Ejecuta los lotes
   ├─ config.yaml                # Config por defecto
   ├─ prompts_template.csv       # Plantilla CSV de prompts
   ├─ requirements.txt           # Dependencias del kit
   └─ .venv/                     # Se crea automáticamente
```

> **Ligero por defecto**: no hace falta incluir `stable-diffusion-webui` en el ZIP. Si está ausente, el **bootstrap** intentará descargarlo en tiempo de ejecución.  
> Si **no** habrá Internet, incluye `vendors\stable-diffusion-webui` **descomprimido** y el bootstrap lo copiará automáticamente.

---

## ▶️ Puesta en marcha (1er uso)

1. **Descomprime** el ZIP en una carpeta sin permisos especiales (p.ej. `C:\IA-Images`).  
2. **Doble clic** en `Start.bat`.
3. El **bootstrap** hará automáticamente:
   - Buscar/instalar **Python 3.10** (usa el instalador local de `vendors` si está, o lo descarga).
   - Preparar **Stable Diffusion WebUI**:
     - Si existe `vendors\stable-diffusion-webui` → **lo copia** a `.\stable-diffusion-webui`.
     - Si hay Internet y no existe copia local → **descarga ZIP** oficial y lo extrae.
   - Crear `stable-diffusion-webui\webui-user.bat` con:
     - **GPU NVIDIA**: `--api --xformers --medvram`
     - **Sin GPU**: `--api --use-cpu all --no-half --no-half-vae --medvram --skip-torch-cuda-test`
   - Crear un **entorno virtual** `batchkit\.venv` e instalar dependencias.
   - **Arrancar** Stable Diffusion WebUI en segundo plano.
   - **Lanzar** la interfaz gráfica `batchkit\app_gui.py` (con `pythonw`, sin consola).

> ⚠️ **Modelos**: copia tus modelos `.safetensors` a `stable-diffusion-webui\models\Stable-diffusion\`. Sin un modelo cargado, A1111 puede tardar más o no responder hasta que lo selecciones en la WebUI.

---

## 🖥️ La aplicación (GUI)

### Cabecera
- **Carpeta de salida (out_dir)**: ruta donde se guardarán los resultados. Si pones una **ruta relativa**, se resuelve desde la **raíz del proyecto**.

### Parámetros (se guardan en `batchkit\config.yaml`)
- **Size**: `WxH` (p.ej. `512x512`, `1024x1024`).
- **Repeats**: repeticiones por prompt.
- **Concurrency**: prompts simultáneos (sube con cuidado).
- **Delay (s)**: pausa entre llamadas.
- **Seed**: `-1` aleatorio.
- **Temperature** (si el proveedor la soporta).
- **Randomize order**: barajar prompts.

### Proveedor
- **automatic1111** (local). Muestra bloque para WebUI con:
  - **API base** (por defecto `http://127.0.0.1:7860`).
  - **Sampler**, **Steps**, **CFG**, **Seed**.
  - Botones: **Arrancar/Parar WebUI**, **Probar API 7860**, **Abrir WebUI** (navegador).
- **openai** / **stability**: campos de modelo/engine y **Guardar .env (API keys)**.

### Acciones
- **Seleccionar CSV**: elige el archivo de **prompts** a ejecutar (por defecto `batchkit\prompts_template.csv` como guía).
- **Ejecutar Lote**: lanza `generator.py` con el proveedor seleccionado.
- **Parar Lote**: termina el proceso del lote.
- **Test imagen**: te pide un prompt y genera **1** imagen rápida.
- **Abrir carpeta de salida**: abre el directorio `out\<provider>\...`.
- **Limpiar log**: limpia la consola integrada.

---

## 🧾 Formato del CSV de prompts

El lector es tolerante con **codificación** (`utf-8`, `utf-8-sig`, `cp1252`, `latin-1`) y **delimitador** (coma o punto y coma).  
Cabecera **recomendada** (puedes añadir/omitir columnas salvo `prompt`):

```csv
id,category,subcat,language,style,actor,geo_scope,prompt
p001,people,portrait,en,cinematic,,,A portrait of a woman...
p002,landscape,,,watercolor,,,Mountain valley at sunrise...
```

- La columna **`id`** (si está) se usa para nombrar carpetas; si no, se genera `prompt<N>`.
- La columna **`prompt`** es **obligatoria**.

---

## 📂 Salida y manifiesto

Las imágenes se guardan en:

```
<out_dir>/<provider>/<safe_id>/
  └─ <safe_id>_rep<k>_<sha16>.png
```

Y se escribe un **manifiesto** por proveedor:

```
<out_dir>/<provider>/manifest.jsonl
```

Cada línea incluye metadatos: `timestamp`, `provider`, `model/engine`, `size`, `prompt_id`, `prompt`, `replicate_index`, `seed`, `sha256_16`, `file_path`, latencia y metadatos crudos de la API si aplica.

---

## 🔧 Problemas frecuentes

- **La GUI no abre** tras `Start.bat`  
  Re‑ejecuta `Start.bat`. Si sigue igual, abre `PowerShell` y ejecuta:
  ```powershell
  Set-Location 'C:\ruta\IA-Images'
  powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1
  ```
  Verás el error exacto en consola (p.ej. permisos, ruta, etc.).

- **WebUI (A1111) tarda / API 7860 no responde**  
  Es normal al primer arranque o si falta el modelo. Abre **Abrir WebUI**, selecciona un modelo en el desplegable y espera a que cargue.

- **Sin GPU NVIDIA**  
  El bootstrap configura modo **CPU** automáticamente (`--use-cpu all`). Será más lento, pero funciona.

- **Git pide usuario/contraseña**  
  No usamos Git para clonar por defecto: el bootstrap prioriza **carpeta local** o **ZIP** oficial.

- **“ModuleNotFoundError: yaml”** u otros paquetes  
  Asegúrate de ejecutar la GUI **siempre** a través de `Start.bat`/`bootstrap.ps1`, que crean el **venv** y instalan dependencias.

- **Rutas con espacios**  
  El bootstrap **cita** las rutas críticas (PYTHON/ARGS). Si moviste carpetas, vuelve a ejecutar `Start.bat`.

---

## 🔁 Actualizar componentes

- **Stable Diffusion WebUI**: sustituye la carpeta `stable-diffusion-webui` por una versión nueva o coloca una carpeta actualizada en `vendors\stable-diffusion-webui` y vuelve a ejecutar `Start.bat`.
- **Configuración**: `batchkit\config.yaml` y `.env` (API Keys) viven en `batchkit\`.
- **App**: `batchkit\app_gui.py` y `batchkit\generator.py` (puedes reemplazarlos y relanzar).

---

## 📝 Licencia y créditos

- **Stable Diffusion WebUI (AUTOMATIC1111)**: licencia del proyecto original.
- Este lanzador/GUI se distribuye “tal cual”. Úsalo bajo tu propia responsabilidad.
- Gracias a los autores de `tqdm`, `requests`, `Pillow`, `ttkbootstrap`, etc.

---

## 🧪 Comprobación rápida

1. Ejecuta `Start.bat`.
2. En la GUI: deja **automatic1111**, **Size** 512×512, y pulsa **Test imagen** con un prompt corto.
3. Abre **Abrir carpeta de salida** para ver la imagen y el `manifest.jsonl`.

¡Listo! Si quieres usar tus propios prompts, pulsa **Seleccionar CSV**, elige tu archivo y luego **Ejecutar Lote**.
