# app_gui.py — UI para IA-Images (Tkinter + ttkbootstrap)
# Vive dentro de batchkit/
# - out_dir relativo a la RAÍZ del proyecto (PROJECT)
# - .env dentro de batchkit/
# - Samplers autoload cuando la API está lista
# - Forzamos --out al ejecutar lote/test
# - Bloque de WebUI sólo visible con proveedor automatic1111
# - Selector de CSV de prompts (por defecto PROJECT/prompts_template.csv)
import os, sys, subprocess, threading, time, webbrowser, yaml, pathlib, requests, shutil, tkinter as tk
from tkinter import filedialog, scrolledtext, simpledialog
from tkinter import ttk

try:
    import ttkbootstrap as tb
except Exception:
    tb = None

# Paths
ROOT    = pathlib.Path(__file__).resolve().parent      # .../IA-Images/batchkit
PROJECT = ROOT.parent                                  # .../IA-Images
KIT     = ROOT
CFG     = KIT / "config.yaml"
ENV     = KIT / ".env"

OPENAI_ENV = "OPENAI_API_KEY"
STAB_ENV   = "STABILITY_API_KEY"

# --------- util cfg/env ----------
def read_cfg():
    with open(CFG, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def write_cfg(data: dict):
    with open(CFG, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True)

def read_env():
    d = {}
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            line=line.strip()
            if not line or line.startswith("#") or "=" not in line: continue
            k,v = line.split("=",1); d[k.strip()] = v.strip()
    return d

def write_env(d: dict):
    ENV.write_text("\n".join(f"{k}={v}" for k,v in d.items() if v) + "\n", encoding="utf-8")

def ensure_venv_and_reqs(log):
    venv_py = KIT / ".venv" / "Scripts" / "python.exe"
    if not venv_py.exists():
        log("Creando venv del kit…")
        subprocess.check_call([sys.executable, "-m", "venv", str(KIT/".venv")])
    py = str(venv_py)
    log("Preparando entorno (solo la primera vez)…")
    subprocess.check_call([py, "-m", "pip", "install", "--upgrade", "pip"])
    req = KIT / "requirements.txt"
    if req.exists():
        subprocess.check_call([py, "-m", "pip", "install", "-r", str(req)])
    subprocess.check_call([py, "-m", "pip", "install", "pyyaml", "requests", "tqdm", "pillow", "python-dotenv", "ttkbootstrap"])
    return py

def _abs_out_from_gui(outdir_str: str) -> pathlib.Path:
    p = pathlib.Path(outdir_str or "out")
    return p if p.is_absolute() else (PROJECT / p).resolve()

# --------- helpers A1111 ----------
def patch_a1111_repo_urls(webui_dir, log):
    """
    Parchea modules/launch_utils.py para reemplazar:
      https://github.com/Stability-AI/stablediffusion.git  ->  https://github.com/CompVis/stable-diffusion.git
    Idempotente.
    """
    try:
        lu = pathlib.Path(webui_dir) / "modules" / "launch_utils.py"
        if not lu.exists():
            log("Aviso: no encuentro modules/launch_utils.py; omito parche.")
            return
        txt = lu.read_text(encoding="utf-8", errors="ignore")
        old = "https://github.com/Stability-AI/stablediffusion.git"
        new = "https://github.com/CompVis/stable-diffusion.git"
        if old in txt:
            log("Parcheando URL del repo SD (Stability-AI -> CompVis)…")
            txt = txt.replace(old, new)
            lu.write_text(txt, encoding="utf-8")
            log("✓ Parche aplicado.")
    except Exception as e:
        log(f"Aviso: no se pudo aplicar parche de repos: {e}")

def _find_vendors_root():
    # vendors puede estar en PROJECT/ o en batchkit/
    a = PROJECT / "vendors"
    b = KIT / "vendors"
    if a.exists(): return a
    if b.exists(): return b
    return None

def seed_local_repos(webui_dir, log):
    """
    Si existen repos predescargados en vendors/repositories/*,
    los copia a stable-diffusion-webui/repositories antes de arrancar.
    Así A1111 no intenta clonar.
    """
    try:
        vendors = _find_vendors_root()
        if not vendors: 
            return
        src = vendors / "repositories"
        dst = pathlib.Path(webui_dir) / "repositories"
        if not src.exists():
            return
        dst.mkdir(parents=True, exist_ok=True)
        copied_any = False
        for child in src.iterdir():
            if not child.is_dir(): 
                continue
            target = dst / child.name
            if target.exists():
                continue
            log(f"Sembrando repo local: {child.name}")
            shutil.copytree(child, target)
            copied_any = True
        if copied_any:
            log("✓ Repos locales copiados a webui/repositories.")
    except Exception as e:
        log(f"Aviso: no se pudieron sembrar repos locales: {e}")

# --------- Tooltips ----------
class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget; self.text = text; self.tip = None
        widget.bind("<Enter>", self.show); widget.bind("<Leave>", self.hide)
    def show(self, _=None):
        if self.tip or not self.text: return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True); tw.wm_geometry(f"+{x}+{y}")
        lab = tk.Label(tw, text=self.text, justify="left", relief="solid",
                       borderwidth=1, background="#ffffe0", font=("Segoe UI", 9))
        lab.pack(ipadx=6, ipady=3)
    def hide(self, _=None):
        if self.tip: self.tip.destroy(); self.tip = None

# --------- WebUI / A1111 ----------
def api_alive(api_base="http://127.0.0.1:7860"):
    try:
        r = requests.get(f"{api_base}/sdapi/v1/progress?skip_current_image=true", timeout=2)
        return r.status_code == 200
    except Exception:
        return False

def fetch_samplers(api_base, log=lambda *_: None):
    try:
        r = requests.get(f"{api_base}/sdapi/v1/samplers", timeout=4)
        r.raise_for_status()
        data = r.json()
        names = [s.get("name","") for s in data if s.get("name")]
        return names or []
    except Exception as e:
        log(f"No se pudieron obtener samplers desde {api_base}: {e}")
        return []

def start_webui(webui_dir, log):
    bat = pathlib.Path(webui_dir) / "webui-user.bat"
    if not bat.exists():
        log("ERROR: no encuentro webui-user.bat en esa carpeta.")
        return None
    log("Arrancando Stable Diffusion WebUI…")
    return subprocess.Popen(['cmd','/c','call',str(bat)], cwd=str(webui_dir),
                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

def wait_api_ready(api_base, seconds=60, log=lambda *_: None):
    for _ in range(seconds):
        if api_alive(api_base): break
        time.sleep(1)
    else:
        return "timeout_api"
    for _ in range(seconds):
        if fetch_samplers(api_base, log): return "ready"
        time.sleep(1)
    return "api_up_initializing"

def taskkill_tree(pid, log):
    try:
        subprocess.run(["taskkill","/F","/T","/PID",str(pid)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log(f"✓ Proceso {pid} terminado (árbol).")
    except Exception as e:
        log(f"ERROR al finalizar PID {pid}: {e}")

# --------- ejecución de lote ----------
def run_batch(log, provider: str, size_override=None, set_batch_proc=None, on_finish=None,
              prompts_path="prompts.csv", extra_args=None):
    def _target():
        try:
            venv_py = KIT / ".venv" / "Scripts" / "python.exe"
            py = str(venv_py) if venv_py.exists() else sys.executable
            cmd = [py,"generator.py","--provider",provider,"--prompts",prompts_path,"--config","config.yaml"]
            if size_override: cmd += ["--size", size_override]
            if extra_args:    cmd += list(extra_args)
            log(f"Lanzando lote con proveedor: {provider} …")
            proc = subprocess.Popen(cmd, cwd=str(KIT),
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
            if set_batch_proc: set_batch_proc(proc)
            for line in iter(proc.stdout.readline, b""):
                txt = line.decode(errors="ignore").rstrip()
                if txt: log(txt)
            rc = proc.wait()
            log("✓ Lote terminado." if rc==0 else f"ERROR: generator salió con código {rc}")
        except Exception as e:
            log(f"ERROR: {e}")
        finally:
            if set_batch_proc: set_batch_proc(None)
            if on_finish: on_finish()
    threading.Thread(target=_target, daemon=True).start()

# --------- UI ----------
class App(tb.Window if tb else tk.Tk):
    def __init__(self):
        if tb: super().__init__(themename="cosmo")
        else:  super().__init__()
        self.title("IA Images – Batchkit")
        self.geometry("1160x900")

        self.cfg  = read_cfg()
        self.envd = read_env()

        self.webui_proc = None
        self.batch_proc = None
        self.running_batch = False
        self.env_ready = False

        # ---- prompts CSV seleccionado (por defecto: PROJECT/prompts_template.csv o KIT/prompts.csv)
        default_prompts = PROJECT / "prompts_template.csv"
        if not default_prompts.exists():
            default_prompts = KIT / "prompts.csv"
        self.prompts_path = default_prompts.resolve()

        # --- CABECERA / out_dir ---
        top = ttk.Frame(self); top.pack(fill="x", padx=12, pady=10)
        ttk.Label(top, text="Carpeta de salida (out_dir):").pack(side="left")
        self.outdir_var = tk.StringVar(value=self.cfg.get("default",{}).get("out_dir", str(PROJECT/"out")))
        e_out = ttk.Entry(top, textvariable=self.outdir_var, width=72); e_out.pack(side="left", padx=6)
        Tooltip(e_out, "Directorio raíz donde se guardará out/<provider>/… Si es relativo, se resuelve desde la raíz del proyecto.")
        ttk.Button(top, text="Examinar", command=self.browse_outdir).pack(side="left")

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=12, pady=6)

        # --- DEFAULT PARAMS ---
        frm_def = ttk.LabelFrame(self, text="Parámetros por defecto (config.yaml)")
        frm_def.pack(fill="x", padx=12, pady=6)
        d = self.cfg.get("default", {})

        def add_cell(row, col, label, var, width, tip):
            ttk.Label(frm_def, text=label).grid(
                row=row, column=col, sticky="w", padx=(6,2), pady=3
            )
            ent = ttk.Entry(frm_def, textvariable=var, width=width)
            ent.grid(row=row, column=col+1, sticky="w", padx=(0,10), pady=3)
            Tooltip(ent, tip)
            return ent

        self.size_var    = tk.StringVar(value=d.get("size","512x512"))
        self.repeats_var = tk.StringVar(value=str(d.get("repeats",30)))
        self.conc_var    = tk.StringVar(value=str(d.get("concurrency",1)))
        self.delay_var   = tk.StringVar(value=str(d.get("delay_seconds",0)))
        self.seed_var    = tk.StringVar(value=str(d.get("seed",-1)))
        self.temp_var    = tk.StringVar(
            value="" if d.get("temperature") is None else str(d.get("temperature"))
        )
        self.rand_var    = tk.BooleanVar(value=bool(d.get("randomize_order",True)))

        # Fila 0
        add_cell(0, 0, "Size",        self.size_var,    10, "Tamaño WxH (p. ej. 512x512)")
        add_cell(0, 2, "Repeats",     self.repeats_var, 6,  "Nº de repeticiones por prompt")
        add_cell(0, 4, "Concurrency", self.conc_var,    6,  "Prompts en paralelo")

        # Fila 1
        add_cell(1, 0, "Delay (s)",   self.delay_var,   6,  "Pausa entre llamadas")
        add_cell(1, 2, "Seed",        self.seed_var,    10, "Semilla (-1 = aleatoria)")
        add_cell(1, 4, "Temperature", self.temp_var,    6,  "Solo OpenAI / Stability")

        # Fila 2
        chk = ttk.Checkbutton(frm_def, text="Randomize order", variable=self.rand_var)
        chk.grid(row=2, column=0, columnspan=2, sticky="w", padx=6, pady=6)
        Tooltip(chk, "Barajar el orden de los prompts")

        ttk.Button(
            frm_def,
            text="Guardar config.yaml",
            command=self.on_save_cfg
        ).grid(row=2, column=4, columnspan=2, sticky="e", padx=6, pady=6)

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=12, pady=6)

        # --- PROVEEDOR selector ---
        sel = ttk.Frame(self); sel.pack(fill="x", padx=12, pady=6)
        ttk.Label(sel, text="Proveedor:").pack(side="left")
        self.provider_var = tk.StringVar(value=self._initial_provider_name())
        self.cmb_provider = ttk.Combobox(sel, textvariable=self.provider_var, state="readonly",
                                         values=["automatic1111","openai","stability"], width=22)
        self.cmb_provider.pack(side="left", padx=8)
        self.cmb_provider.bind("<<ComboboxSelected>>", lambda e: self._on_provider_change())

        PROVIDER_URLS = {
            "automatic1111": "https://github.com/AUTOMATIC1111/stable-diffusion-webui",
            "stability":     "https://platform.stability.ai/",
            "openai":        "https://platform.openai.com/",
        }

        self.btn_provider_web = ttk.Button(
            sel,
            text="Abrir web",
            command=lambda: webbrowser.open(PROVIDER_URLS.get(self.provider_var.get(), ""))
        )
        self.btn_provider_web.pack(side="left", padx=6)


        ttk.Button(sel, text="Guardar .env (API keys)", command=self.on_save_env).pack(side="left", padx=12)

        # contenedor proveedores
        self.prov_container = ttk.Frame(self); self.prov_container.pack(fill="x", padx=12, pady=6)

        # Colores de fondo por proveedor
        self.bg_auto = "#E8F5FF"
        self.bg_oai  = "#E8FFF2"
        self.bg_stab = "#FFF6E5"

        # --- AUTOMATIC1111 ---
        self.frm_auto_bg = tk.Frame(self.prov_container, bg=self.bg_auto, bd=1, relief="solid")
        
        # --- Bloque instalación / ayuda Automatic1111 ---
        install_box = ttk.LabelFrame(
            self.frm_auto_bg,
            text="Instalación de Automatic1111 (Stable Diffusion en local)"
        )
        install_box.pack(fill="x", padx=8, pady=(0, 10))

        msg = (
            "Si ya tienes Automatic1111 instalado en otra ubicación, introduce la ruta correcta y la URL de la API.\n"
            "Si no lo tienes instalado, o quieres reinstalarlo,puedes hacerlo automáticamente en la carpeta del proyecto. \n"
            "   El primer Arranque de la WebUI finaliza el proceso de instalación. \n"
            "   Se debe mantener abierta la ventana de símbolo de sistema con Stable Diffusion en segundo plano."
        )

        lbl = ttk.Label(
            install_box,
            text=msg,
            justify="left",
            wraplength=760
        )
        lbl.pack(anchor="w", padx=10, pady=(6, 8))

        btns = ttk.Frame(install_box)
        btns.pack(anchor="w", padx=10, pady=(0, 8))

        ttk.Button(
            btns,
            text="Instalar / Reinstalar Automatic1111",
            command=self.on_install_a1111
        ).pack(side="left")

        ttk.Button(
            btns,
            text="Abrir repositorio (GitHub)",
            command=lambda: webbrowser.open(
                "https://github.com/AUTOMATIC1111/stable-diffusion-webui"
            )
        ).pack(side="left", padx=8)


       # --- Bloque configuración Automatic1111 ---
        self.frm_auto = ttk.LabelFrame(
            self.frm_auto_bg,
            text="Configuración Automatic1111 (Stable Diffusion local)"
        )
        self.frm_auto.columnconfigure(0, weight=0)
        self.frm_auto.columnconfigure(1, weight=1)
        self.frm_auto.columnconfigure(2, weight=0)
        self.frm_auto.columnconfigure(3, weight=1)

        self.frm_auto.configure(style="Card.TLabelframe")

        a = self.cfg.get("providers", {}).get("automatic1111", {})

        self.auto_api_var     = tk.StringVar(value=a.get("api_base", "http://127.0.0.1:7860"))
        self.auto_sampler_var = tk.StringVar(value=a.get("sampler_name", "DPM++ 2M Karras"))
        self.auto_steps_var   = tk.StringVar(value=str(a.get("steps", 32)))
        self.auto_cfg_var     = tk.StringVar(value=str(a.get("cfg_scale", 6.0)))

        def add_auto_cell(row, col, label, var, width, tip):
            ttk.Label(
                self.frm_auto,
                text=label,
                anchor="e"
            ).grid(
                row=row,
                column=col,
                sticky="e",
                padx=(6, 2),
                pady=2
            )

            ent = ttk.Entry(
                self.frm_auto,
                textvariable=var,
                width=width
            )
            ent.grid(
                row=row,
                column=col + 1,
                sticky="w",
                padx=(0, 8),
                pady=2
            )
            Tooltip(ent, tip)
            return ent


        # Fila 0
        add_auto_cell(
            0, 0,
            "API base",
            self.auto_api_var,
            46,
            "URL local de Automatic1111 (http://127.0.0.1:7860)"
        )
        add_auto_cell(
            0, 2,
            "Steps",
            self.auto_steps_var,
            8,
            "Pasos de muestreo (más = más detalle / más tiempo)"
        )

        # Fila 1
        ttk.Label(self.frm_auto, text="Sampler").grid(
            row=1, column=0, sticky="w", padx=(3,2), pady=(2, 0)
        )
        self.cb_sampler = ttk.Combobox(
            self.frm_auto,
            textvariable=self.auto_sampler_var,
            width=44
        )
        self.cb_sampler.grid(
            row=1, column=1, sticky="w", padx=(0,12), pady=(2, 0)
        )
        Tooltip(
            self.cb_sampler,
            "Se rellena automáticamente desde la API cuando está disponible.\nTambién puedes escribir uno manualmente."
        )

        add_auto_cell(
            1, 2,
            "CFG",
            self.auto_cfg_var,
            8,
            "Escala de guía (6–8 suele ser un buen rango)"
        )

        # --- Bloque control WebUI ---
        sub = ttk.LabelFrame(self.frm_auto, text="Stable Diffusion local")
        sub.grid(row=2, column=0, columnspan=4, sticky="we", padx=6, pady=(10, 6))

        rsub = 0
        ttk.Label(sub, text="Carpeta Stable Diffusion WebUI:").grid(
            row=rsub, column=0, sticky="w", padx=6, pady=4
        )
        self.webui_var = tk.StringVar(value=str(PROJECT / "stable-diffusion-webui"))
        e = ttk.Entry(sub, textvariable=self.webui_var, width=62)
        e.grid(row=rsub, column=1, sticky="w", padx=6, pady=4)
        Tooltip(e, "Ruta donde está instalado AUTOMATIC1111")

        ttk.Button(
            sub,
            text="Examinar",
            command=self.browse_webui
        ).grid(row=rsub, column=2, padx=6, pady=4, sticky="w")

        rsub += 1
        ttk.Button(sub, text="Arrancar WebUI",  command=self.on_start_webui).grid(row=rsub, column=0, padx=6, pady=4, sticky="w")
        ttk.Button(sub, text="Parar WebUI",     command=self.on_stop_webui).grid(row=rsub, column=1, padx=6, pady=4, sticky="w")
        ttk.Button(sub, text="Probar API 7860", command=self.on_probe_api).grid(row=rsub, column=2, padx=6, pady=4, sticky="w")
        ttk.Button(
            sub,
            text="Abrir WebUI",
            command=lambda: webbrowser.open("http://127.0.0.1:7860")
        ).grid(row=rsub, column=3, padx=6, pady=4, sticky="w")

        self.frm_auto.pack(fill="x", padx=8, pady=8)


        # --- OPENAI ---
        self.frm_oai_bg = tk.Frame(self.prov_container, bg=self.bg_oai, bd=1, relief="solid")
        self.frm_oai = ttk.LabelFrame(self.frm_oai_bg, text="OpenAI")
        oai = self.cfg.get("providers",{}).get("openai",{})
        self.oai_model_var   = tk.StringVar(value=oai.get("model","gpt-image-1"))
        self.env_oai_key_var = tk.StringVar(value=self.envd.get(OPENAI_ENV,""))

        ro=0
        ttk.Label(self.frm_oai, text="Model").grid(row=ro, column=0, sticky="w", padx=(6,2), pady=3)
        self.cb_oai_model = ttk.Combobox(self.frm_oai, textvariable=self.oai_model_var, width=28)
        self.cb_oai_model['values'] = ["gpt-image-1","o4-mini"]
        self.cb_oai_model.grid(row=ro, column=1, sticky="w", padx=6, pady=3)
        Tooltip(self.cb_oai_model, "Modelo de imágenes de OpenAI. Puedes escribir otro.")
        ro+=1
        ttk.Label(self.frm_oai, text="API KEY").grid(row=ro, column=0, sticky="w", padx=(6,2), pady=3)
        e=ttk.Entry(self.frm_oai, textvariable=self.env_oai_key_var, width=40, show="•"); e.grid(row=ro, column=1, sticky="w", padx=6, pady=3)
        Tooltip(e, "Tu clave secreta de OpenAI (se guarda en .env).")

        self.frm_oai.pack(fill="x", padx=8, pady=8)

        # --- STABILITY ---
        self.frm_stab_bg = tk.Frame(self.prov_container, bg=self.bg_stab, bd=1, relief="solid")
        self.frm_stab = ttk.LabelFrame(self.frm_stab_bg, text="Stability AI")
        stab = self.cfg.get("providers",{}).get("stability",{})
        self.stab_engine_var   = tk.StringVar(value=stab.get("engine","sd3"))
        self.stab_api_base_var = tk.StringVar(value=stab.get("api_base","https://api.stability.ai"))
        self.env_stab_key_var  = tk.StringVar(value=self.envd.get(STAB_ENV,""))

        rs=0
        ttk.Label(self.frm_stab, text="Engine").grid(row=rs, column=0, sticky="w", padx=(6,2), pady=3)
        self.cb_stab_engine = ttk.Combobox(self.frm_stab, textvariable=self.stab_engine_var, width=28)
        self.cb_stab_engine['values'] = ["sd3","sd3-turbo","sd3-large"]
        self.cb_stab_engine.grid(row=rs, column=1, sticky="w", padx=6, pady=3)
        Tooltip(self.cb_stab_engine, "Motor/versión de Stability. Puedes escribir otro.")
        rs+=1
        ttk.Label(self.frm_stab, text="API base").grid(row=rs, column=0, sticky="w", padx=(6,2), pady=3)
        e=ttk.Entry(self.frm_stab, textvariable=self.stab_api_base_var, width=40); e.grid(row=rs, column=1, sticky="w", padx=6, pady=3)
        Tooltip(e, "Endpoint REST, normalmente https://api.stability.ai")
        rs+=1
        ttk.Label(self.frm_stab, text="API KEY").grid(row=rs, column=0, sticky="w", padx=(6,2), pady=3)
        e=ttk.Entry(self.frm_stab, textvariable=self.env_stab_key_var, width=40, show="•"); e.grid(row=rs, column=1, sticky="w", padx=6, pady=3)
        Tooltip(e, "Tu clave secreta de Stability (se guarda en .env).")

        self.frm_stab.pack(fill="x", padx=8, pady=8)

        # Oculta/enseña bloques por proveedor
        self.frm_auto_bg.pack_forget();  self.frm_oai_bg.pack_forget();  self.frm_stab_bg.pack_forget()
        self.frm_auto.pack(fill="x", padx=8, pady=8)
        self.frm_oai.pack(fill="x", padx=8, pady=8)
        self.frm_stab.pack(fill="x", padx=8, pady=8)
        self._on_provider_change()

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=12, pady=6)

        # --- Acciones ---
        act = ttk.Frame(self); act.pack(fill="x", padx=12, pady=6)
        ttk.Button(act, text="Ejecutar Lote", command=self.on_run_batch).pack(side="left", padx=12)
        ttk.Button(act, text="Parar Lote", command=self.on_stop_batch).pack(side="left")
        ttk.Button(act, text="Test imagen", command=self.on_test_image).pack(side="left", padx=12)
        ttk.Button(act, text="Abrir carpeta de salida", command=self.open_out).pack(side="left")
        ttk.Button(act, text="Elegir CSV de prompts…", command=self.browse_prompts_csv).pack(side="left", padx=6)
        self.lbl_prompts = ttk.Label(act, text=f"CSV: {self._shorten(self.prompts_path)}")
        self.lbl_prompts.pack(side="left", padx=8)
        ttk.Button(act, text="Limpiar log", command=self.clear_log).pack(side="right")

        # --- Log RO ---
        self.logbox = scrolledtext.ScrolledText(self, height=22, font=("Consolas", 10), state="disabled")
        self.logbox.pack(fill="both", expand=True, padx=12, pady=6)

        self._try_auto_reload_samplers()

    # ---------- helpers UI ----------
    def _shorten(self, p: pathlib.Path, maxlen=60) -> str:
        s = str(p)
        return s if len(s) <= maxlen else "…" + s[-(maxlen-1):]

    def clear_log(self):
        self.logbox.configure(state="normal"); self.logbox.delete("1.0", tk.END); self.logbox.configure(state="disabled")

    def log(self, msg):
        self.logbox.configure(state="normal"); self.logbox.insert(tk.END, msg+"\n"); self.logbox.see(tk.END); self.logbox.configure(state="disabled")

    def _initial_provider_name(self):
        prov = self.cfg.get("providers", {})
        for name in ["automatic1111","openai","stability"]:
            if prov.get(name,{}).get("enabled", False): return name
        return "automatic1111"

    def _on_provider_change(self):
        for w in (self.frm_auto_bg, self.frm_oai_bg, self.frm_stab_bg):
            w.pack_forget()
        p = self.provider_var.get()
        if p == "automatic1111":
            self.frm_auto_bg.pack(fill="x", padx=8, pady=6)
            self._try_auto_reload_samplers()
        elif p == "openai":
            self.frm_oai_bg.pack(fill="x", padx=8, pady=6)
        elif p == "stability":
            self.frm_stab_bg.pack(fill="x", padx=8, pady=6)

    def _try_auto_reload_samplers(self):
        base = self.auto_api_var.get().strip() or "http://127.0.0.1:7860"
        def _run():
            if not api_alive(base): return
            sams = fetch_samplers(base, self.log)
            if sams:
                self.cb_sampler['values'] = sams
        threading.Thread(target=_run, daemon=True).start()

    def browse_webui(self):
        p = filedialog.askdirectory(initialdir=str(PROJECT))
        if p: self.webui_var.set(p)

    def browse_outdir(self):
        p = filedialog.askdirectory(initialdir=str(PROJECT))
        if p: self.outdir_var.set(p)

    def browse_prompts_csv(self):
        p = filedialog.askopenfilename(
            initialdir=str(PROJECT),
            title="Selecciona un CSV de prompts",
            filetypes=[("CSV files","*.csv"), ("All files","*.*")]
        )
        if p:
            self.prompts_path = pathlib.Path(p).resolve()
            self.lbl_prompts.configure(text=f"CSV: {self._shorten(self.prompts_path)}")
            self.log(f"CSV seleccionado: {self.prompts_path}")

    # ---------- WebUI ----------
    def on_install_a1111(self):
        """
        Lanza el instalador de Automatic1111 (bootstrap específico).
        """
        self.log("Iniciando instalación de Automatic1111…")

        # buscamos bootstrap específico
        script = PROJECT / "batchkit" / "bootstrap_automatic1111.ps1"
        if not script.exists():
            self.log("ERROR: No se encuentra bootstrap_automatic1111.ps1")
            return

        try:
            subprocess.Popen(
                [
                    "cmd.exe",
                    "/k",  # <- CLAVE: mantiene la consola abierta
                    "powershell",
                    "-NoLogo",
                    "-NoProfile",
                    "-ExecutionPolicy", "Bypass",
                    "-File", str(script)
                ],
                cwd=str(PROJECT)
            )
            self.log("Instalador lanzado en una ventana separada.")
        except Exception as e:
            self.log(f"ERROR lanzando instalador: {e}")


    def on_start_webui(self):
        webui_path = pathlib.Path(self.webui_var.get())
        if not webui_path.exists():
            self.log("❌ Automatic1111 no está instalado.")
            self.log("Pulsa 'Instalar Automatic1111' o configura la ruta correctamente.")
            return

        bat = webui_path / "webui-user.bat"
        if not bat.exists():
            self.log("❌ Falta webui-user.bat. Automatic1111 no está inicializado.")
            self.log("Pulsa 'Instalar Automatic1111' o configura la ruta correctamente.")
            return

        if self.provider_var.get() != "automatic1111":
            self.log("WebUI solo aplica a 'automatic1111'."); return
        if not self.webui_var.get().strip():
            self.log("Selecciona la carpeta de Stable Diffusion WebUI."); return
        webui_dir = pathlib.Path(self.webui_var.get())
        if not (webui_dir / "webui-user.bat").exists():
            self.log("Automatic1111 no parece estar instalado en esa ruta.")
            self.log("Usa el botón 'Instalar / Reinstalar Automatic1111' o revisa la carpeta.")
            return
        if self.webui_proc and self.webui_proc.poll() is None:
            self.log("WebUI ya está ejecutándose."); return

        # Antes de lanzar: siembra repos locales (si existen) y parchea URL rota
        seed_local_repos(self.webui_var.get(), self.log)
        #patch_a1111_repo_urls(self.webui_var.get(), self.log)

        self.webui_proc = start_webui(self.webui_var.get(), self.log)
        self.log("Esperando API 7860…")
        threading.Thread(target=self._wait_and_report_api, daemon=True).start()

    def _wait_and_report_api(self):
        base = self.auto_api_var.get().strip() or "http://127.0.0.1:7860"
        status = wait_api_ready(base, seconds=60, log=self.log)
        if status == "ready":
            self.log(f"API lista en {base} (modelo cargado).")
            self.cb_sampler['values'] = fetch_samplers(base, self.log)
        elif status == "api_up_initializing":
            self.log(f"API OK en {base}, inicializando modelo… (puede tardar)")
        else:
            self.log("No respondió la API (o tardó demasiado).")

    def on_stop_webui(self):
        if self.webui_proc and self.webui_proc.poll() is None:
            pid = self.webui_proc.pid; taskkill_tree(pid, self.log); self.webui_proc = None
        else:
            self.log("WebUI no está ejecutándose.")

    def on_probe_api(self):
        base = self.auto_api_var.get().strip() or "http://127.0.0.1:7860"
        self.log("API viva ✓" if api_alive(base) else "API no responde ✗")

    # ---------- Guardar config / env ----------
    def on_save_cfg(self):
        try:
            c = self.cfg
            c.setdefault("default", {})
            c.setdefault("providers", {})

            outdir_input = (self.outdir_var.get() or "").strip() or "out"
            abs_out = _abs_out_from_gui(outdir_input)
            try:
                rel = abs_out.relative_to(PROJECT)
                out_dir_to_save = str(rel).replace("\\", "/")
            except ValueError:
                out_dir_to_save = str(abs_out)

            c["default"]["out_dir"] = out_dir_to_save
            c["default"]["size"] = self.size_var.get()
            c["default"]["repeats"] = int(self.repeats_var.get())
            c["default"]["concurrency"] = int(self.conc_var.get())
            c["default"]["delay_seconds"] = float(self.delay_var.get())
            c["default"]["randomize_order"] = bool(self.rand_var.get())
            c["default"]["seed"] = int(self.seed_var.get())
            t = self.temp_var.get().strip()
            c["default"]["temperature"] = None if t == "" else float(t)

            auto = c["providers"]["automatic1111"]
            auto["api_base"] = self.auto_api_var.get()
            auto["sampler_name"] = self.auto_sampler_var.get()
            auto["steps"] = int(self.auto_steps_var.get())
            auto["cfg_scale"] = float(self.auto_cfg_var.get())
            auto["seed"] = int(self.auto_seed_var.get() or -1)

            oai = c["providers"]["openai"]
            oai["model"] = self.oai_model_var.get()
            oai["api_key_env"] = OPENAI_ENV

            stab = c["providers"]["stability"]
            stab["engine"] = self.stab_engine_var.get()
            stab["api_base"] = self.stab_api_base_var.get()
            stab["api_key_env"] = STAB_ENV

            write_cfg(c)
            self.log(f"✓ config.yaml guardado. out_dir = {c['default']['out_dir']}")
        except Exception as e:
            self.log(f"ERROR guardando config: {e}")

    def on_save_env(self):
        try:
            d = read_env()
            d[OPENAI_ENV] = self.env_oai_key_var.get()
            d[STAB_ENV]   = self.env_stab_key_var.get()
            write_env(d)
            self.log("✓ .env guardado.")
        except Exception as e:
            self.log(f"ERROR guardando .env: {e}")

    # ---------- Lote ----------
    def set_batch_proc(self, proc):
        self.batch_proc = proc; self.running_batch = proc is not None

    def _autostart_a1111_if_needed(self):
        base = self.auto_api_var.get().strip() or "http://127.0.0.1:7860"
        if api_alive(base): return True
        self.log("API de A1111 no responde; intentando arrancar WebUI…")
        if not self.webui_var.get().strip():
            self.log("Ruta WebUI no definida. Cancelo."); return False
        self.webui_proc = start_webui(self.webui_var.get(), self.log)
        self.log("Esperando API…")
        status = wait_api_ready(base, seconds=60, log=self.log)
        if status in ("ready","api_up_initializing"):
            if status == "ready":
                self.cb_sampler['values'] = fetch_samplers(base, self.log)
            return True
        self.log("No pude confirmar la API de A1111.")
        return False

    def on_run_batch(self):
        if self.running_batch:
            self.log("Ya hay un lote en ejecución."); return
        if not self.env_ready:
            try:
                ensure_venv_and_reqs(self.log)
                self.env_ready = True
            except Exception as e:
                self.log(f"ERROR preparando entorno: {e}")
                return

        provider = self.provider_var.get()
        if provider == "automatic1111" and not self._autostart_a1111_if_needed():
            return

        run_batch(
            self.log,
            provider=provider,
            size_override=self.size_var.get(),
            set_batch_proc=self.set_batch_proc,
            on_finish=lambda: self.log("Fin de lote."),
            extra_args=["--out", str(_abs_out_from_gui(self.outdir_var.get()))],
            prompts_path=str(self.prompts_path)
        )

    def on_stop_batch(self):
        if self.batch_proc and self.batch_proc.poll() is None:
            pid = self.batch_proc.pid; taskkill_tree(pid, self.log); self.set_batch_proc(None)
        else:
            self.log("No hay lote en ejecución.")

    def on_test_image(self):
        prompt = simpledialog.askstring(
            "Test imagen",
            "Escribe un prompt para una sola imagen:"
        )
        if not prompt:
            return

        try:
            ensure_venv_and_reqs(self.log)
        except Exception as e:
            self.log(f"ERROR preparando entorno: {e}")
            return

        provider = self.provider_var.get()
        if provider == "automatic1111" and not self._autostart_a1111_if_needed():
            return

        # CSV temporal
        tmp_csv = KIT / "_tmp_prompt.csv"
        tmp_csv.write_text(
            "id,category,subcat,language,style,actor,geo_scope,prompt\n"
            f"t1,,,,,,,{prompt.replace(',', ';')}\n",
            encoding="utf-8"
        )

        self.log("Generando 1 imagen de prueba…")

        # Carpeta real de salida del test
        test_out_root = _abs_out_from_gui(self.outdir_var.get()) / "test" / provider

        def _after():
            try:
                pngs = list(test_out_root.rglob("*.png"))
                if pngs:
                    self.log(f"✓ Imagen generada correctamente ({len(pngs)} archivo/s).")
                    self.log(f"Ruta: {pngs[0]}")
                else:
                    self.log("⚠️ El test terminó, pero no se encontró ninguna imagen.")
            except Exception as e:
                self.log(f"Aviso comprobando salida del test: {e}")

            try:
                if tmp_csv.exists():
                    tmp_csv.unlink()
            except Exception:
                pass

            self.log("Fin test.")

        run_batch(
            self.log,
            provider=provider,
            size_override=self.size_var.get(),
            prompts_path=str(tmp_csv.name),
            extra_args=[
                "--repeats", "1",
                "--out", str(_abs_out_from_gui(self.outdir_var.get()) / "test")
            ],
            set_batch_proc=self.set_batch_proc,
            on_finish=_after
        )



    # ---------- salida ----------
    def open_out(self):
        abs_out = _abs_out_from_gui(self.outdir_var.get())
        prov = self.provider_var.get()
        target = abs_out / prov
        target.mkdir(parents=True, exist_ok=True)
        try: os.startfile(str(target))
        except Exception: self.log(f"Carpeta de salida: {target}")

if __name__ == "__main__":
    App().mainloop()
