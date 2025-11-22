#!/usr/bin/env python3
import os, csv, json, time, base64, hashlib, random, argparse, pathlib, sys, datetime
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List
from tqdm import tqdm
import re

# Try to load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

try:
    import yaml
except Exception:
    print("Please 'pip install pyyaml' or add it to requirements if you want to use YAML configs.", file=sys.stderr)
    yaml = None

# Optional providers
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

import requests
from PIL import Image
from io import BytesIO

@dataclass
class RunConfig:
    out_dir: str = "out"
    repeats: int = 3
    size: str = "1024x1024"
    temperature: Optional[float] = None
    randomize_order: bool = True
    concurrency: int = 1
    delay_seconds: float = 0.0
    seed: Optional[int] = None

@dataclass
class ProviderConfig:
    enabled: bool = False
    # OpenAI
    model: Optional[str] = None
    api_key_env: Optional[str] = None
    # Stability
    engine: Optional[str] = None
    api_base: Optional[str] = None
    # Automatic1111
    sampler_name: Optional[str] = None
    steps: Optional[int] = None
    cfg_scale: Optional[float] = None

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def timestamp() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"

def ensure_dir(p: str):
    pathlib.Path(p).mkdir(parents=True, exist_ok=True)

def save_image_bytes(img_bytes: bytes, path: str):
    with open(path, "wb") as f:
        f.write(img_bytes)

def write_jsonl(path: str, rows: List[Dict[str, Any]]):
    with open(path, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def load_prompts_csv(path: str) -> List[Dict[str, str]]:
    # intenta codificaciones típicas
    encodings = ("utf-8", "utf-8-sig", "cp1252", "latin-1")
    last_err = None
    raw_text = None
    for enc in encodings:
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                raw_text = f.read()
            break
        except UnicodeDecodeError as e:
            last_err = e
            continue
    if raw_text is None:
        raise last_err or RuntimeError(f"No se pudo leer {path}")

    # detecta delimitador (coma o punto y coma)
    try:
        dialect = csv.Sniffer().sniff(raw_text[:4096], delimiters=";,")
        delimiter = dialect.delimiter
    except Exception:
        delimiter = ";" if ";" in raw_text[:4096] else ","

    # parsea con DictReader usando el delimitador detectado
    reader = csv.DictReader(raw_text.splitlines(), delimiter=delimiter)
    rows = [dict((k.strip().lower(), (v or "")) for k, v in r.items()) for r in reader]
    return rows

def safe_name(s: str) -> str:
    """Convierte cualquier texto en un nombre de carpeta seguro para Windows/Linux."""
    if not s:
        return "noid"
    s = re.sub(r'[^A-Za-z0-9._-]+', '_', str(s)).strip('_')
    return (s or "noid")[:64]


# ---------- Providers ----------

def gen_openai(prompt: str, size: str, model: str, api_key: str) -> Dict[str, Any]:
    if OpenAI is None:
        raise RuntimeError("OpenAI SDK not installed. Run: pip install openai")
    client = OpenAI(api_key=api_key)
    resp = client.images.generate(
        model=model,
        prompt=prompt,
        size=size,
        n=1,
    )
    b64 = resp.data[0].b64_json
    img_bytes = base64.b64decode(b64)
    return {"image_bytes": img_bytes, "raw_response": resp.to_dict()}

def gen_stability(prompt: str, size: str, engine: str, api_base: str, api_key: str, seed: Optional[int] = None) -> Dict[str, Any]:
    # size: "1024x1024"
    w, h = (int(x) for x in size.split("x"))
    url = f"{api_base}/v2beta/stable-image/generate/{engine}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "image/*,application/json",
    }
    data = {
        "prompt": prompt,
        "output_format": "png",
        "width": w,
        "height": h,
    }
    if seed is not None:
        data["seed"] = seed
    r = requests.post(url, headers=headers, data=data, timeout=300)
    if r.status_code == 200 and r.headers.get("Content-Type","").startswith("image"):
        img_bytes = r.content
        return {"image_bytes": img_bytes, "raw_response": {"headers": dict(r.headers)}}
    else:
        try:
            err = r.json()
        except Exception:
            err = {"text": r.text, "status": r.status_code}
        raise RuntimeError(f"Stability API error: {err}")

def gen_automatic1111(prompt: str, size: str, api_base: str, sampler_name: str, steps: int, cfg_scale: float, seed: int) -> Dict[str, Any]:
    w, h = (int(x) for x in size.split("x"))
    url = f"{api_base}/sdapi/v1/txt2img"
    payload = {
        "prompt": prompt,
        "width": w,
        "height": h,
        "sampler_name": sampler_name,
        "steps": steps,
        "cfg_scale": cfg_scale,
        "seed": seed if seed is not None else -1,
        "batch_size": 1
    }
    r = requests.post(url, json=payload, timeout=300)
    r.raise_for_status()
    data = r.json()
    if "images" not in data or not data["images"]:
        raise RuntimeError("Automatic1111 returned no images.")
    img_b64 = data["images"][0].split(",",1)[-1] if "," in data["images"][0] else data["images"][0]
    img_bytes = base64.b64decode(img_b64)
    return {"image_bytes": img_bytes, "raw_response": data}

# ---------- Runner ----------

def main():
    parser = argparse.ArgumentParser(description="Batch image generation for bias study")
    parser.add_argument("--provider", required=True, choices=["openai","stability","automatic1111"], help="Which provider to use")
    parser.add_argument("--config", default="config.yaml", help="YAML config file")
    parser.add_argument("--prompts", default="prompts.csv", help="CSV with prompts")
    parser.add_argument("--out", default=None, help="Output directory (overrides config)")
    parser.add_argument("--repeats", type=int, default=None, help="Times to repeat each prompt (overrides config)")
    parser.add_argument("--size", default=None, help="Image size, e.g. 1024x1024 (overrides config)")
    args = parser.parse_args()

    if yaml is None:
        raise RuntimeError("YAML support not available. Please install pyyaml.")

    with open(args.config, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    run = cfg.get("default", {})
    rc = RunConfig(
        out_dir = args.out or run.get("out_dir", "out"),
        repeats = args.repeats or int(run.get("repeats", 3)),
        size = args.size or run.get("size", "1024x1024"),
        temperature = run.get("temperature", None),
        randomize_order = bool(run.get("randomize_order", True)),
        concurrency = int(run.get("concurrency", 1)),
        delay_seconds = float(run.get("delay_seconds", 0)),
        seed = run.get("seed", None),
    )

    providers = cfg.get("providers", {})
    pconf = providers.get(args.provider, {})
    pc = ProviderConfig(
        enabled = bool(pconf.get("enabled", False)),
        model = pconf.get("model"),
        api_key_env = pconf.get("api_key_env"),
        engine = pconf.get("engine"),
        api_base = pconf.get("api_base"),
        sampler_name = pconf.get("sampler_name"),
        steps = pconf.get("steps"),
        cfg_scale = pconf.get("cfg_scale"),
    )
    if not pc.enabled:
        print(f"WARNING: Provider '{args.provider}' is disabled in config. Continuing anyway.", file=sys.stderr)

    # Load prompts
    prompts = load_prompts_csv(args.prompts)
    if rc.randomize_order:
        random.shuffle(prompts)

    # Output dirs
    out_root = os.path.join(rc.out_dir, args.provider)
    ensure_dir(out_root)
    manifest_path = os.path.join(out_root, "manifest.jsonl")
    meta_rows = []

    for idx, pr in enumerate(tqdm(prompts, desc="Prompts"), start=1):
        prompt_id = pr.get("id") or pr.get("prompt_id") or f"prompt{idx}"
        prompt_dir = os.path.join(out_root, safe_name(prompt_id))
        ensure_dir(prompt_dir)

        for rep in range(rc.repeats):
            prompt_text = pr["prompt"]
            t0 = time.time()
            try:
                if args.provider == "openai":
                    api_key = os.getenv(pc.api_key_env or "OPENAI_API_KEY")
                    if not api_key:
                        raise RuntimeError("Missing OPENAI_API_KEY env var.")
                    out = gen_openai(prompt_text, rc.size, pc.model or "gpt-image-1", api_key)

                elif args.provider == "stability":
                    api_key = os.getenv(pc.api_key_env or "STABILITY_API_KEY")
                    if not api_key:
                        raise RuntimeError("Missing STABILITY_API_KEY env var.")
                    out = gen_stability(prompt_text, rc.size, pc.engine or "sd3", pc.api_base or "https://api.stability.ai", api_key, seed=rc.seed)

                elif args.provider == "automatic1111":
                    out = gen_automatic1111(prompt_text, rc.size, pc.api_base or "http://127.0.0.1:7860", pc.sampler_name or "DPM++ 2M Karras", int(pc.steps or 30), float(pc.cfg_scale or 6.5), rc.seed if rc.seed is not None else -1)

                img_bytes = out["image_bytes"]
                img_hash = sha256_bytes(img_bytes)[:16]
                fname = f"{safe_name(prompt_id)}_rep{rep+1}_{img_hash}.png"
                fpath = os.path.join(prompt_dir, fname)
                save_image_bytes(img_bytes, fpath)

                meta = {
                    "timestamp": timestamp(),
                    "provider": args.provider,
                    "model": pc.model or pc.engine or pc.sampler_name or "unknown",
                    "size": rc.size,
                    "prompt_id": prompt_id,   # ← usa este, no pr["id"]
                    "prompt_category": pr.get("category"),
                    "prompt_subcat": pr.get("subcat"),
                    "language": pr.get("language"),
                    "style": pr.get("style"),
                    "actor": pr.get("actor"),
                    "geo_scope": pr.get("geo_scope"),
                    "prompt": prompt_text,
                    "replicate_index": rep+1,
                    "seed": rc.seed,
                    "sha256_16": img_hash,
                    "file_path": fpath,
                    "raw_response_meta": out.get("raw_response", {}),
                    "latency_seconds": round(time.time()-t0, 3),
                }

                meta_rows.append(meta)

            except Exception as e:
                meta_rows.append({
                    "timestamp": timestamp(),
                    "provider": args.provider,
                    "error": str(e),
                    "prompt_id": pr["id"],
                    "replicate_index": rep+1,
                    "prompt": prompt_text,
                })

            if rc.delay_seconds:
                time.sleep(rc.delay_seconds)

        # flush metadata after each prompt
        if meta_rows:
            write_jsonl(manifest_path, meta_rows)
            meta_rows = []

    print(f"Done. Manifest: {manifest_path}")

if __name__ == "__main__":
    main()
