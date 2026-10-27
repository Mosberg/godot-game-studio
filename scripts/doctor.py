#!/usr/bin/env python3
"""Command-line health check: python scripts/doctor.py"""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp"))
import studio_common as sc  # noqa: E402


def version(exe, flag="--version"):
    if not exe:
        return ""
    r = sc.run([exe, flag], timeout=30)
    out = (r["stdout"] or r["stderr"]).strip().splitlines()
    return out[0] if out else ""


def main():
    rows = []
    godot = sc.find_godot()
    rows.append(("Godot", godot, version(godot)))
    dn = shutil.which("dotnet")
    rows.append((".NET SDK", dn, version(dn)))
    blender = sc.find_blender()
    rows.append(("Blender", blender, version(blender)))
    gimp = sc.find_gimp()
    rows.append(("GIMP", gimp, version(gimp)))
    rows.append(("ffmpeg", sc.find_ffmpeg(), ""))
    url = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
    try:
        stats = sc.http_json("GET", url + "/system_stats", timeout=3)
        rows.append(("ComfyUI", url, "online " + str(stats.get("system", {}).get("comfyui_version", ""))))
    except Exception as exc:  # noqa: BLE001
        rows.append(("ComfyUI", None, f"offline ({type(exc).__name__})"))
    for mod in ("mcp", "PIL", "numpy", "rembg"):
        try:
            __import__(mod)
            rows.append((f"python:{mod}", "ok", ""))
        except ImportError:
            rows.append((f"python:{mod}", None, "pip install -r requirements.txt" if mod != "rembg" else "optional"))
    width = max(len(r[0]) for r in rows)
    for name, where, info in rows:
        print(f"{'OK ' if where else '-- '} {name.ljust(width)}  {where or 'not found'}  {info}")
    print("\nEnv: GODOT_PATH BLENDER_PATH GIMP_PATH FFMPEG_PATH COMFYUI_URL GAME_PROJECT_DIR")
    return 0


if __name__ == "__main__":
    sys.exit(main())
