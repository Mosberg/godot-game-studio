#!/usr/bin/env python3
"""Godot Game Studio - ComfyUI MCP server.

Talks to a running ComfyUI (default http://127.0.0.1:8188) over its HTTP API. Builds standard txt2img /
img2img / upscale graphs itself (checkpoint + LoRA chain), runs your own API-format workflows with
parameter overrides, and post-processes results into game-ready pixel art.
"""
from __future__ import annotations

import functools
import json
import os
import random
import sys
import time
import traceback
import urllib.parse
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import studio_common as sc  # noqa: E402
from studio_common import fail, ok  # noqa: E402

mcp = sc.make_server(
    "comfyui",
    "Generate game art with a local ComfyUI. Start with comfy_status, then comfy_list_models. Use "
    "comfy_txt2img for quick generations (supports LoRAs), comfy_game_asset for presets (sprite, icon, tile, "
    "portrait, background) that also clean up the result, and comfy_run_workflow to execute your own "
    "API-format workflow JSON with overrides. Generated files are downloaded to the output folder you choose.",
)

BASE = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")
USER_WORKFLOWS = Path(os.environ.get("COMFY_WORKFLOWS_DIR", "") or (sc.PLUGIN_ROOT / "comfy_workflows"))

PRESETS: dict[str, dict[str, Any]] = {
    "sprite": {"prefix": "single character game sprite, full body, centered, simple flat colors, clean outline, plain white background, ",
               "negative": "blurry, multiple characters, cropped, text, watermark, background scenery, photo",
               "width": 768, "height": 768, "pixel": 64, "remove_bg": True},
    "icon": {"prefix": "game inventory icon, single object centered, bold readable silhouette, plain white background, ",
             "negative": "blurry, text, watermark, multiple objects, scenery",
             "width": 768, "height": 768, "pixel": 32, "remove_bg": True},
    "tile": {"prefix": "seamless tileable game texture, top-down, even lighting, no perspective, ",
             "negative": "border, frame, vignette, text, objects, uneven lighting",
             "width": 768, "height": 768, "pixel": 64, "seamless": True},
    "portrait": {"prefix": "character portrait bust, dialogue portrait, expressive face, painterly game art, ",
                 "negative": "blurry, deformed, text, watermark, extra limbs", "width": 768, "height": 1024},
    "background": {"prefix": "wide game background scene, layered depth, atmospheric, no characters, ",
                   "negative": "text, watermark, characters, ui", "width": 1344, "height": 768},
    "concept": {"prefix": "game concept art, ", "negative": "blurry, text, watermark", "width": 1024, "height": 1024},
}


def safe(fn):
    @functools.wraps(fn)
    def wrapper(*a, **k):
        try:
            return fn(*a, **k)
        except Exception as exc:  # noqa: BLE001
            msg = f"{type(exc).__name__}: {exc}"
            hint = ""
            if "refused" in msg.lower() or "urlopen" in msg.lower() or "timed out" in msg.lower():
                hint = f"Is ComfyUI running at {BASE}? Set COMFYUI_URL if it lives elsewhere."
            return fail(msg, hint=hint, trace=traceback.format_exc()[-1200:])
    return wrapper


def api(method: str, path: str, payload: Any = None, timeout: int = 30) -> Any:
    return sc.http_json(method, BASE + path, payload, timeout)


def object_info(node: str = "") -> dict:
    return api("GET", "/object_info" + (f"/{node}" if node else ""), timeout=60)


def combo_values(node: str, field: str) -> list[str]:
    try:
        info = object_info(node).get(node, {})
        spec = info.get("input", {}).get("required", {}).get(field) or info.get("input", {}).get("optional", {}).get(field)
        if spec and isinstance(spec[0], list):
            return list(spec[0])
    except Exception:  # noqa: BLE001
        pass
    return []


# --------------------------------------------------------------------------- #
# graph builders
# --------------------------------------------------------------------------- #
def build_txt2img(checkpoint: str, prompt: str, negative: str, width: int, height: int, steps: int, cfg: float,
                  seed: int, sampler: str, scheduler: str, loras: list[dict], prefix: str,
                  init_image: str = "", denoise: float = 1.0) -> dict:
    g: dict[str, Any] = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
    }
    model: list = ["1", 0]
    clip: list = ["1", 1]
    nid = 10
    for lo in loras:
        key = str(nid)
        g[key] = {"class_type": "LoraLoader", "inputs": {
            "lora_name": lo["name"], "strength_model": float(lo.get("strength", 0.8)),
            "strength_clip": float(lo.get("strength_clip", lo.get("strength", 0.8))),
            "model": model, "clip": clip}}
        model, clip = [key, 0], [key, 1]
        nid += 1
    g["2"] = {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": clip}}
    g["3"] = {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": clip}}
    if init_image:
        g["4"] = {"class_type": "LoadImage", "inputs": {"image": init_image}}
        g["5"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["4", 0], "vae": ["1", 2]}}
        latent: list = ["5", 0]
    else:
        g["5"] = {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}}
        latent = ["5", 0]
    g["6"] = {"class_type": "KSampler", "inputs": {
        "seed": seed, "steps": steps, "cfg": cfg, "sampler_name": sampler, "scheduler": scheduler,
        "denoise": denoise, "model": model, "positive": ["2", 0], "negative": ["3", 0], "latent_image": latent}}
    g["7"] = {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["1", 2]}}
    g["8"] = {"class_type": "SaveImage", "inputs": {"images": ["7", 0], "filename_prefix": prefix}}
    return g


def build_upscale(image_name: str, model_name: str, prefix: str) -> dict:
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "2": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": model_name}},
        "3": {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["2", 0], "image": ["1", 0]}},
        "4": {"class_type": "SaveImage", "inputs": {"images": ["3", 0], "filename_prefix": prefix}},
    }


# --------------------------------------------------------------------------- #
# queue / wait / download
# --------------------------------------------------------------------------- #
def queue_prompt(graph: dict) -> str:
    resp = api("POST", "/prompt", {"prompt": graph, "client_id": "godot-game-studio"}, timeout=60)
    if "prompt_id" not in resp:
        raise RuntimeError(f"ComfyUI rejected the workflow: {json.dumps(resp)[:1500]}")
    return resp["prompt_id"]


def wait_for(prompt_id: str, timeout: int) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        hist = api("GET", f"/history/{prompt_id}", timeout=30)
        entry = hist.get(prompt_id)
        if entry:
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                msgs = [m for m in status.get("messages", []) if m and m[0] == "execution_error"]
                raise RuntimeError("workflow failed: " + (json.dumps(msgs[-1][1])[:1500] if msgs else "unknown error"))
            if entry.get("outputs") or status.get("completed"):
                return entry
        time.sleep(1.0)
    raise TimeoutError(f"timed out after {timeout}s waiting for prompt {prompt_id} (still queued/running; see comfy_history)")


def collect_images(entry: dict) -> list[dict]:
    images = []
    for node_id, out in entry.get("outputs", {}).items():
        for im in out.get("images", []):
            if im.get("type", "output") in ("output", "temp"):
                images.append({**im, "node": node_id})
    return images


def download(img: dict, dest_dir: Path, name: str) -> Path:
    q = urllib.parse.urlencode({"filename": img["filename"], "subfolder": img.get("subfolder", ""),
                                "type": img.get("type", "output")})
    status, body = sc.http_request("GET", f"{BASE}/view?{q}", timeout=120)
    if status != 200:
        raise RuntimeError(f"/view returned HTTP {status}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(img["filename"]).suffix or ".png"
    path = dest_dir / f"{name}{ext}"
    path.write_bytes(body)
    return path


def run_and_fetch(graph: dict, out_dir: str, name: str, timeout: int) -> tuple[list[Path], dict]:
    pid = queue_prompt(graph)
    entry = wait_for(pid, timeout)
    imgs = collect_images(entry)
    if not imgs:
        raise RuntimeError("workflow finished but produced no images (does it have a SaveImage node?)")
    dest = Path(out_dir).resolve()
    paths = [download(im, dest, name if len(imgs) == 1 else f"{name}_{i}") for i, im in enumerate(imgs)]
    return paths, {"prompt_id": pid}


def pick_default(kind: str, node: str, field: str, given: str) -> str:
    if given:
        return given
    vals = combo_values(node, field)
    if not vals:
        raise RuntimeError(f"no {kind} installed - put one in ComfyUI/models and pass its name")
    return vals[0]


# =========================================================================== #
# tools
# =========================================================================== #
@mcp.tool()
@safe
def comfy_status() -> str:
    """Check the ComfyUI server: version, devices/VRAM, queue depth."""
    stats = api("GET", "/system_stats", timeout=10)
    try:
        q = api("GET", "/queue", timeout=10)
        queue = {"running": len(q.get("queue_running", [])), "pending": len(q.get("queue_pending", []))}
    except Exception:  # noqa: BLE001
        queue = {}
    return ok(url=BASE, system=stats.get("system", {}), devices=stats.get("devices", []), queue=queue,
              workflows_dir=str(USER_WORKFLOWS))


@mcp.tool()
@safe
def comfy_list_models() -> str:
    """List installed checkpoints, LoRAs, VAEs, upscale models, ControlNets and samplers/schedulers."""
    return ok(
        checkpoints=combo_values("CheckpointLoaderSimple", "ckpt_name"),
        loras=combo_values("LoraLoader", "lora_name"),
        vae=combo_values("VAELoader", "vae_name"),
        upscalers=combo_values("UpscaleModelLoader", "model_name"),
        controlnets=combo_values("ControlNetLoader", "control_net_name"),
        samplers=combo_values("KSampler", "sampler_name"),
        schedulers=combo_values("KSampler", "scheduler"),
    )


@mcp.tool()
@safe
def comfy_list_nodes(search: str = "", limit: int = 60) -> str:
    """Search the node classes available in this ComfyUI (including custom nodes), e.g. 'pixel', 'rembg', 'controlnet'."""
    info = object_info()
    names = sorted(n for n in info if search.lower() in n.lower() or search.lower() in info[n].get("display_name", "").lower())
    return ok(count=len(names), nodes=[{"class": n, "display": info[n].get("display_name", n),
                                        "category": info[n].get("category", "")} for n in names[:limit]])


@mcp.tool()
@safe
def comfy_node_info(class_type: str) -> str:
    """Show a node's inputs and outputs (to hand-write or patch workflows)."""
    info = object_info(class_type).get(class_type)
    return ok(**info) if info else fail(f"node '{class_type}' not found")


@mcp.tool()
@safe
def comfy_txt2img(prompt: str, output_dir: str, name: str = "gen", negative: str = "blurry, low quality, watermark, text",
                  checkpoint: str = "", width: int = 768, height: int = 768, steps: int = 25, cfg: float = 7.0,
                  seed: int = -1, sampler: str = "euler", scheduler: str = "normal",
                  loras: Optional[list[dict]] = None, timeout: int = 600) -> str:
    """Text to image. loras = [{'name': 'pixel_art.safetensors', 'strength': 0.8}]. checkpoint defaults to the first installed.
    SDXL wants ~1024px; SD1.5 ~512px. Returns saved file paths and the seed."""
    ckpt = pick_default("checkpoint", "CheckpointLoaderSimple", "ckpt_name", checkpoint)
    seed = random.randint(0, 2**32 - 1) if seed < 0 else seed
    graph = build_txt2img(ckpt, prompt, negative, width, height, steps, cfg, seed, sampler, scheduler,
                          loras or [], f"studio_{name}")
    paths, meta = run_and_fetch(graph, output_dir, name, timeout)
    return ok(files=[str(p) for p in paths], seed=seed, checkpoint=ckpt, **meta)


@mcp.tool()
@safe
def comfy_img2img(image_path: str, prompt: str, output_dir: str, name: str = "variation", denoise: float = 0.55,
                  negative: str = "blurry, low quality, watermark, text", checkpoint: str = "", steps: int = 25,
                  cfg: float = 7.0, seed: int = -1, sampler: str = "euler", scheduler: str = "normal",
                  loras: Optional[list[dict]] = None, timeout: int = 600) -> str:
    """Image to image: restyle or iterate on an existing picture. Lower denoise keeps more of the original."""
    uploaded = _upload(image_path)
    ckpt = pick_default("checkpoint", "CheckpointLoaderSimple", "ckpt_name", checkpoint)
    seed = random.randint(0, 2**32 - 1) if seed < 0 else seed
    graph = build_txt2img(ckpt, prompt, negative, 0, 0, steps, cfg, seed, sampler, scheduler, loras or [],
                          f"studio_{name}", init_image=uploaded, denoise=denoise)
    paths, meta = run_and_fetch(graph, output_dir, name, timeout)
    return ok(files=[str(p) for p in paths], seed=seed, **meta)


@mcp.tool()
@safe
def comfy_upscale(image_path: str, output_dir: str, name: str = "upscaled", model: str = "", timeout: int = 600) -> str:
    """Upscale an image with an installed upscale model (e.g. 4x-UltraSharp, RealESRGAN)."""
    uploaded = _upload(image_path)
    model_name = pick_default("upscale model", "UpscaleModelLoader", "model_name", model)
    paths, meta = run_and_fetch(build_upscale(uploaded, model_name, f"studio_{name}"), output_dir, name, timeout)
    return ok(files=[str(p) for p in paths], model=model_name, **meta)


@mcp.tool()
@safe
def comfy_game_asset(preset: str, subject: str, output_dir: str, name: str = "", style: str = "",
                     checkpoint: str = "", loras: Optional[list[dict]] = None, seed: int = -1,
                     palette: str = "", pixel_size: int = 0, steps: int = 25, cfg: float = 7.0,
                     timeout: int = 600) -> str:
    """Generate a game-ready asset from a preset: sprite | icon | tile | portrait | background | concept.
    Post-processing per preset: background removal (sprite/icon), seamless blend (tile), and when pixel_size > 0
    or the preset is pixel-oriented, downscale to a crisp pixel-art image (nearest-neighbour) and optionally
    snap to `palette` (pico8, gameboy, sweetie16, grayscale4, or a list of #hex colours separated by commas).
    Pass pixel_size=-1 to skip pixelation and keep the full-resolution image."""
    import studio_images as si
    if preset not in PRESETS:
        return fail(f"unknown preset '{preset}'", presets=list(PRESETS))
    cfg_p = PRESETS[preset]
    prompt = f"{cfg_p['prefix']}{subject}" + (f", {style}" if style else "")
    ckpt = pick_default("checkpoint", "CheckpointLoaderSimple", "ckpt_name", checkpoint)
    seed = random.randint(0, 2**32 - 1) if seed < 0 else seed
    stem = sc.safe_name(name or subject)[:40] or preset
    raw_dir = Path(output_dir).resolve() / "_raw"
    graph = build_txt2img(ckpt, prompt, cfg_p["negative"], cfg_p["width"], cfg_p["height"], steps, cfg, seed,
                          "euler", "normal", loras or [], f"studio_{stem}")
    paths, meta = run_and_fetch(graph, str(raw_dir), stem, timeout)
    img = si.load_rgba(paths[0])
    steps_done: list[str] = []
    if cfg_p.get("remove_bg"):
        img = si.remove_background(img, tolerance=48)
        img = si.trim(img, padding=1)
        steps_done.append("background removed + trimmed")
    if cfg_p.get("seamless"):
        img = si.make_seamless(img)
        steps_done.append("seamless blend")
    target = pixel_size if pixel_size != 0 else int(cfg_p.get("pixel", 0))
    if target > 0:
        scale = target / max(img.width, img.height)
        img = si.pixelate(img, max(1, round(img.width * scale)), max(1, round(img.height * scale)))
        steps_done.append(f"pixelated to {img.width}x{img.height}")
        if palette:
            pal = si.resolve_palette(palette if palette in si.PALETTES else [c.strip() for c in palette.split(",")])
            img = si.quantize_to_palette(img, pal)
            steps_done.append("palette snapped")
    final = si.save(img, Path(output_dir).resolve() / f"{stem}.png")
    return ok(file=final, raw=str(paths[0]), seed=seed, size=[img.width, img.height], processing=steps_done,
              note="Import with Nearest filtering for pixel art (godot_set_pixel_art_defaults).", **meta)


def _upload(path: str, overwrite: bool = True) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    ctype = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
    body, header = sc.multipart_body({"overwrite": "true" if overwrite else "false", "type": "input"},
                                     {"image": (p.name, p.read_bytes(), ctype)})
    status, resp = sc.http_request("POST", BASE + "/upload/image", raw_body=body,
                                   headers={"Content-Type": header}, timeout=60)
    if status >= 400:
        raise RuntimeError(f"upload failed: HTTP {status} {resp[:300]!r}")
    data = json.loads(resp.decode("utf-8"))
    return (data["subfolder"] + "/" if data.get("subfolder") else "") + data["name"]


@mcp.tool()
@safe
def comfy_upload_image(image_path: str) -> str:
    """Upload an image to ComfyUI's input folder; returns the name to use in LoadImage nodes."""
    return ok(name=_upload(image_path))


@mcp.tool()
@safe
def comfy_list_workflows() -> str:
    """List saved API-format workflow JSON files in the user workflow folder (COMFY_WORKFLOWS_DIR)."""
    USER_WORKFLOWS.mkdir(parents=True, exist_ok=True)
    files = sorted(p.name for p in USER_WORKFLOWS.glob("*.json"))
    return ok(directory=str(USER_WORKFLOWS), workflows=files,
              tip="In ComfyUI enable dev options, then 'Save (API Format)' and drop the file in this folder.")


@mcp.tool()
@safe
def comfy_run_workflow(workflow: str, output_dir: str, overrides: Optional[dict] = None, name: str = "workflow",
                       timeout: int = 900) -> str:
    """Run an API-format workflow (a path, a filename in the workflows folder, or inline JSON text).
    overrides patches inputs: {"6.text": "a red dragon", "3.seed": 42, "5.width": 512}  (node_id.input -> value).
    Downloads every image the workflow saves."""
    text = workflow.strip()
    if text.startswith("{"):
        graph = json.loads(text)
    else:
        p = Path(text)
        if not p.exists():
            p = USER_WORKFLOWS / text
            if not p.exists() and not text.endswith(".json"):
                p = USER_WORKFLOWS / (text + ".json")
        if not p.exists():
            return fail(f"workflow not found: {workflow}", looked_in=str(USER_WORKFLOWS))
        graph = json.loads(p.read_text(encoding="utf-8"))
    if "nodes" in graph and "prompt" not in graph and "links" in graph:
        return fail("This is a UI-format workflow. Re-export with 'Save (API Format)' from ComfyUI.")
    graph = graph.get("prompt", graph)
    applied = []
    for key, value in (overrides or {}).items():
        node, _, field = key.partition(".")
        if node not in graph or not field:
            return fail(f"bad override '{key}': use node_id.input_name; nodes: {sorted(graph)[:30]}")
        graph[node].setdefault("inputs", {})[field] = value
        applied.append(key)
    paths, meta = run_and_fetch(graph, output_dir, name, timeout)
    return ok(files=[str(p) for p in paths], overrides=applied, **meta)


@mcp.tool()
@safe
def comfy_queue_workflow(workflow_json: str) -> str:
    """Queue an API-format workflow without waiting; returns the prompt_id (poll with comfy_history)."""
    return ok(prompt_id=queue_prompt(json.loads(workflow_json)))


@mcp.tool()
@safe
def comfy_history(prompt_id: str = "", limit: int = 5) -> str:
    """Show the status/outputs of a prompt, or the most recent runs."""
    if prompt_id:
        return ok(history=api("GET", f"/history/{prompt_id}"))
    hist = api("GET", f"/history?max_items={limit}")
    return ok(runs=[{"prompt_id": k, "status": v.get("status", {}).get("status_str"),
                     "images": [i["filename"] for i in collect_images(v)]} for k, v in hist.items()])


@mcp.tool()
@safe
def comfy_download(filename: str, output_path: str, subfolder: str = "", type: str = "output") -> str:
    """Download any file from ComfyUI's output/input/temp folders."""
    img = {"filename": filename, "subfolder": subfolder, "type": type}
    dest = Path(output_path)
    saved = download(img, dest.parent, dest.stem)
    if saved != dest:
        saved.replace(dest)
    return ok(file=str(dest))


@mcp.tool()
@safe
def comfy_interrupt() -> str:
    """Stop the currently running generation."""
    api("POST", "/interrupt", {})
    return ok(interrupted=True)


@mcp.tool()
@safe
def comfy_clear_queue() -> str:
    """Clear all pending jobs."""
    api("POST", "/queue", {"clear": True})
    return ok(cleared=True)


@mcp.tool()
@safe
def comfy_free_memory(unload_models: bool = True) -> str:
    """Free VRAM (unload models and free cached memory) - useful before launching Godot/Blender renders on the same GPU."""
    api("POST", "/free", {"unload_models": unload_models, "free_memory": True})
    return ok(freed=True)


if __name__ == "__main__":
    mcp.run()
