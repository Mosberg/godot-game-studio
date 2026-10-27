#!/usr/bin/env python3
"""Godot Game Studio - Blender MCP server.

Headless Blender automation (run Python, procedural props, convert/optimise, render, sprite sheets)
plus a live bridge to a running Blender (UI or headless) through the Claude Bridge add-on.
"""
from __future__ import annotations

import functools
import json
import os
import shutil
import sys
import traceback
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import studio_common as sc  # noqa: E402
from studio_common import fail, ok  # noqa: E402

mcp = sc.make_server(
    "blender",
    "Drive Blender for game art. Headless tools need BLENDER_PATH (or blender on PATH). Use "
    "blender_generate_asset for quick props, blender_run_python for anything custom, blender_render_sprites "
    "to turn 3D models into 2D sprite sheets, and blender_export_for_godot to ship a .glb into a Godot project. "
    "For a running Blender use blender_install_addon once, then the blender_bridge_* tools.",
)

SCRIPTS = sc.PLUGIN_ROOT / "blender_scripts"
ADDON = sc.PLUGIN_ROOT / "blender_addon" / "claude_bridge.py"
BRIDGE_PORT = int(os.environ.get("BLENDER_BRIDGE_PORT", "9876") or 9876)
_headless_pid: Optional[int] = None

KINDS = ["crate", "barrel", "rock", "pine_tree", "round_tree", "house", "tower", "coin", "gem", "sword",
         "platform", "mushroom", "chest", "fence"]

PRELUDE = (
    "import bpy, bmesh, math, os, sys, json, random\n"
    "import mathutils\n"
    "from mathutils import Vector, Matrix, Euler\n"
    "sys.path.insert(0, r'%s')\n" % str(SCRIPTS).replace("\\", "/")
)


def safe(fn):
    @functools.wraps(fn)
    def wrapper(*a, **k):
        try:
            return fn(*a, **k)
        except Exception as exc:  # noqa: BLE001
            return fail(f"{type(exc).__name__}: {exc}", trace=traceback.format_exc()[-1500:])
    return wrapper


def blender_exe() -> str:
    exe = sc.find_blender()
    if not exe:
        raise FileNotFoundError(
            "Blender not found. Set BLENDER_PATH to blender.exe (e.g. C:\\Program Files\\Blender Foundation\\"
            "Blender 4.x\\blender.exe) or add it to PATH.")
    return exe


def run_script(script: Path, args: dict, blend_file: str = "", timeout: int = 300) -> dict:
    """Run a script from blender_scripts/ headless with a JSON args file; returns parsed result."""
    exe = blender_exe()
    args = dict(args)
    result_path = sc.tmp_file(".json", "bl_result_")
    args_path = sc.tmp_file(".json", "bl_args_")
    args["result_path"] = str(result_path)
    args_path.write_text(json.dumps(args), encoding="utf-8")
    cmd = [exe, "-b"]
    if blend_file:
        cmd.append(str(Path(blend_file).resolve()))
    cmd += ["--factory-startup", "--python-exit-code", "1", "--python", str(script), "--", str(args_path)]
    res = sc.run(cmd, timeout=timeout)
    data: Any = None
    if result_path.exists():
        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = None
        result_path.unlink(missing_ok=True)
    args_path.unlink(missing_ok=True)
    res["data"] = data
    res["success"] = res["returncode"] == 0 and data is not None
    return res


def tail_errors(res: dict) -> str:
    text = (res.get("stderr", "") + "\n" + res.get("stdout", "")).strip()
    lines = [l for l in text.splitlines() if "Error" in l or "Traceback" in l or l.startswith("  File")]
    return "\n".join(lines[-14:]) or text[-1200:]


# =========================================================================== #
# info / generic
# =========================================================================== #
@mcp.tool()
@safe
def blender_info() -> str:
    """Blender executable, version, bridge status and available procedural asset kinds."""
    exe = sc.find_blender()
    info: dict[str, Any] = {"executable": exe, "asset_kinds": KINDS}
    if exe:
        r = sc.run([exe, "--version"], timeout=60)
        info["version"] = (r["stdout"] or r["stderr"]).strip().splitlines()[0] if (r["stdout"] or r["stderr"]) else "?"
    else:
        info["hint"] = "Set BLENDER_PATH to your blender executable."
    try:
        info["bridge"] = _bridge("ping", timeout=2)
    except Exception as exc:  # noqa: BLE001
        info["bridge"] = f"not connected ({type(exc).__name__})"
    return ok(**info)


@mcp.tool()
@safe
def blender_run_python(code: str, blend_file: str = "", save_to: str = "", timeout: int = 180) -> str:
    """Run Python (bpy) headless in Blender. Optionally open `blend_file` first and `save_to` a .blend after.
    Prelude gives you bpy, bmesh, math, os, sys, json, random, mathutils, Vector, Matrix, Euler and puts
    blender_scripts/ on sys.path (import _common for clear_scene/make_material/export_model helpers).
    print() output is returned; print '@@RESULT@@' + json.dumps(x) for structured results."""
    exe = blender_exe()
    script = sc.tmp_file(".py", "bl_user_")
    body = PRELUDE + code
    if save_to:
        body += f"\nbpy.ops.wm.save_as_mainfile(filepath=r'{Path(save_to).resolve()}')\n"
    script.write_text(body, encoding="utf-8")
    cmd = [exe, "-b"]
    if blend_file:
        cmd.append(str(Path(blend_file).resolve()))
    cmd += ["--factory-startup", "--python-exit-code", "1", "--python", str(script)]
    res = sc.run(cmd, timeout=timeout)
    script.unlink(missing_ok=True)
    result = None
    kept = []
    for line in res["stdout"].splitlines():
        if "@@RESULT@@" in line:
            try:
                result = json.loads(line.split("@@RESULT@@", 1)[1])
            except json.JSONDecodeError:
                result = line.split("@@RESULT@@", 1)[1]
        else:
            kept.append(line)
    return ok(success=res["returncode"] == 0, returncode=res["returncode"], result=result,
              stdout="\n".join(kept)[-5000:], errors=tail_errors(res) if res["returncode"] else "",
              timed_out=res["timed_out"])


# =========================================================================== #
# procedural assets / conversion
# =========================================================================== #
@mcp.tool()
@safe
def blender_list_asset_kinds() -> str:
    """List procedural prop generators: crate, barrel, rock, pine_tree, round_tree, house, tower, coin, gem, sword, platform, mushroom, chest, fence."""
    return ok(kinds=KINDS, params="size (metres), color/top_color/roof_color/trim_color as '#rrggbb', layers (pine_tree)")


@mcp.tool()
@safe
def blender_generate_asset(kind: str, output_glb: str, params: Optional[dict] = None, seed: int = 1,
                           output_blend: str = "", flat_shading: bool = True, bevel: float = 0.0,
                           scale: float = 1.0) -> str:
    """Generate a low-poly prop and export a .glb (and optionally a .blend). Origin is bottom-centre, 1 unit = 1 m.
    Example: kind='crate', output_glb='<project>/assets/models/crate.glb', params={'size': 1.0, 'color': '#a8743c'}."""
    if kind not in KINDS:
        return fail(f"unknown kind '{kind}'", kinds=KINDS)
    out_glb = Path(output_glb)
    out_glb.parent.mkdir(parents=True, exist_ok=True)
    args = {"kind": kind, "params": params or {}, "seed": seed, "flat": flat_shading, "bevel": bevel,
            "scale": scale if scale != 1.0 else None, "output_glb": str(out_glb.resolve())}
    if output_blend:
        Path(output_blend).parent.mkdir(parents=True, exist_ok=True)
        args["output_blend"] = str(Path(output_blend).resolve())
    res = run_script(SCRIPTS / "asset_generators.py", args)
    if not res["success"]:
        return fail("generation failed", details=tail_errors(res))
    return ok(**res["data"])


@mcp.tool()
@safe
def blender_convert(input_path: str, output_path: str, scale: float = 1.0, origin: str = "",
                    decimate_ratio: float = 0.0, merge_distance: float = 0.0, triangulate: bool = False,
                    animations: bool = True) -> str:
    """Convert/clean a model between .glb/.gltf/.fbx/.obj/.stl/.ply/.dae/.blend. origin: 'bottom'|'center'|''.
    decimate_ratio 0.5 halves the triangles. Returns size and face counts."""
    args = {"input": str(Path(input_path).resolve()), "output": str(Path(output_path).resolve()),
            "scale": scale, "origin": origin or None, "decimate_ratio": decimate_ratio or None,
            "merge_distance": merge_distance or None, "triangulate": triangulate, "animations": animations}
    res = run_script(SCRIPTS / "convert_model.py", args)
    return ok(**res["data"]) if res["success"] else fail("conversion failed", details=tail_errors(res))


@mcp.tool()
@safe
def blender_inspect(model_path: str = "", blend_file: str = "") -> str:
    """Inspect a model/.blend for game-readiness: triangles, size, UVs, materials, armatures, actions, issues."""
    if not model_path and not blend_file:
        return fail("give model_path (glb/fbx/obj/...) or blend_file")
    args = {"model": str(Path(model_path).resolve())} if model_path else {}
    res = run_script(SCRIPTS / "inspect_model.py", args, blend_file=blend_file)
    return ok(**res["data"]) if res["success"] else fail("inspect failed", details=tail_errors(res))


@mcp.tool()
@safe
def blender_export_for_godot(input_path: str, project_path: str = "", subfolder: str = "assets/models",
                             name: str = "", scale: float = 1.0, origin: str = "bottom",
                             animations: bool = True) -> str:
    """Convert any model/.blend to .glb inside a Godot project (default res://assets/models). Then run
    godot_import. Godot's import hints work in object names: -col, -colonly, -convcol, -navmesh, -occ, -noimp, -loop."""
    base = project_path or sc.default_project_dir() or os.getcwd()
    root = Path(base).resolve()
    if not (root / "project.godot").exists():
        return fail(f"{root} is not a Godot project (no project.godot)")
    src = Path(input_path).resolve()
    out = root / subfolder / f"{name or src.stem}.glb"
    args = {"input": str(src), "output": str(out), "scale": scale, "origin": origin or None, "animations": animations}
    res = run_script(SCRIPTS / "convert_model.py", args)
    if not res["success"]:
        return fail("export failed", details=tail_errors(res))
    rel = "res://" + str(out.relative_to(root)).replace("\\", "/")
    return ok(godot_path=rel, **res["data"], next="Run godot_import, then instance it as a PackedScene.")


@mcp.tool()
@safe
def blender_render_still(blend_file: str, output_png: str, engine: str = "eevee", samples: int = 32,
                         width: int = 1024, height: int = 1024, frame: int = -1, transparent: bool = False,
                         timeout: int = 600) -> str:
    """Render a still from a .blend (camera must exist). engine: eevee|cycles|workbench."""
    out = Path(output_png).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    code = f"""
from _common import pick_engine
sc = bpy.context.scene
sc.render.engine = pick_engine({engine!r})
if sc.render.engine == 'CYCLES':
    sc.cycles.samples = {int(samples)}
sc.render.resolution_x, sc.render.resolution_y = {int(width)}, {int(height)}
sc.render.resolution_percentage = 100
sc.render.film_transparent = {bool(transparent)}
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_mode = 'RGBA' if {bool(transparent)} else 'RGB'
if {int(frame)} >= 0:
    sc.frame_set({int(frame)})
sc.render.filepath = r'{out}'
bpy.ops.render.render(write_still=True)
print('@@RESULT@@' + json.dumps({{'path': r'{out}', 'engine': sc.render.engine}}))
"""
    return blender_run_python(code, blend_file=blend_file, timeout=timeout)


@mcp.tool()
@safe
def blender_render_sprites(model_path: str, output_png: str, directions: int = 8, size: int = 128,
                           elevation: float = 30.0, engine: str = "eevee", samples: int = 16,
                           frames: Optional[list[int]] = None, action: str = "", columns: int = 0,
                           blend_file: str = "", margin: float = 1.15, keep_frames: bool = False,
                           timeout: int = 900) -> str:
    """Render a 3D model to a 2D sprite sheet: rows = view directions, columns = animation frames.
    elevation 30 = isometric-ish, 90 = top-down, 0 = side. frames=[start,end,step] renders an animation
    (optionally `action` name). Falls back to Cycles automatically if Eevee cannot run (no GPU/GL).
    Writes the sheet PNG plus <name>.atlas.json (cell size, rows=directions, columns=frames)."""
    import studio_images as si
    out_png = Path(output_png).resolve()
    frames_dir = sc.scratch_dir("sprites") / sc.safe_name(out_png.stem)
    shutil.rmtree(frames_dir, ignore_errors=True)
    frames_dir.mkdir(parents=True)
    args = {"model": str(Path(model_path).resolve()) if model_path else None, "out_dir": str(frames_dir),
            "directions": directions, "size": size, "elevation": elevation, "engine": engine, "samples": samples,
            "frames": frames, "action": action or None, "margin": margin}
    res = run_script(SCRIPTS / "render_spritesheet.py", args, blend_file=blend_file, timeout=timeout)
    used_engine = engine
    if not res["success"] and engine.lower() in ("eevee", "workbench"):
        args["engine"] = "cycles"
        args["samples"] = max(8, min(samples, 24))
        res = run_script(SCRIPTS / "render_spritesheet.py", args, blend_file=blend_file, timeout=timeout)
        used_engine = "cycles (fallback)"
    if not res["success"]:
        return fail("sprite render failed", details=tail_errors(res))
    data = res["data"]
    per_dir = data["frames_per_direction"]
    ordered = [f"{frames_dir}/dir{d}_f{i}.png" for d in range(data["directions"]) for i in range(per_dir)]
    sheet, atlas = si.pack_spritesheet(ordered, columns=per_dir, padding=0, uniform=True)
    si.save(sheet, out_png)
    atlas.update({"directions": data["directions"], "frames_per_direction": per_dir, "elevation": elevation,
                  "layout": "rows=directions (0=front, rotating counter-clockwise), columns=frames"})
    atlas_path = si.write_json(out_png.with_suffix(".atlas.json"), atlas)
    if not keep_frames:
        shutil.rmtree(frames_dir, ignore_errors=True)
    return ok(sheet=str(out_png), atlas=atlas_path, engine=used_engine, cell=atlas["cell"],
              directions=data["directions"], frames_per_direction=per_dir,
              godot_hint="Use Sprite2D with hframes=frames_per_direction, vframes=directions and set frame_coords, "
                         "or build SpriteFrames; keep texture filter Nearest for pixel art.")


# =========================================================================== #
# live bridge
# =========================================================================== #
def _bridge(cmd: str, args: Optional[dict] = None, timeout: float = 120.0) -> dict:
    payload: dict[str, Any] = {"cmd": cmd, "args": args or {}}
    token = os.environ.get("BLENDER_BRIDGE_TOKEN", "").strip()
    if token:
        payload["token"] = token
    resp = sc.tcp_json_call("127.0.0.1", BRIDGE_PORT, payload, timeout=timeout)
    if not resp.get("ok"):
        raise RuntimeError(resp.get("error", "bridge error") + (("\n" + resp["trace"]) if resp.get("trace") else ""))
    return resp.get("result", {})


@mcp.tool()
@safe
def blender_install_addon() -> str:
    """Install and enable the Claude Bridge add-on in your Blender user preferences (once). After that every
    Blender session you open starts the bridge on 127.0.0.1:9876 automatically (sidebar > Claude)."""
    exe = blender_exe()
    script = sc.tmp_file(".py", "bl_install_")
    script.write_text(
        "import bpy, os, shutil, json\n"
        f"src = r'{ADDON}'\n"
        "dst_dir = bpy.utils.user_resource('SCRIPTS', path='addons', create=True)\n"
        "dst = os.path.join(dst_dir, 'claude_bridge.py')\n"
        "shutil.copy(src, dst)\n"
        "enabled = False\n"
        "try:\n"
        "    bpy.ops.preferences.addon_enable(module='claude_bridge')\n"
        "    bpy.ops.wm.save_userpref()\n"
        "    enabled = True\n"
        "except Exception as e:\n"
        "    print('enable failed', e)\n"
        "print('@@RESULT@@' + json.dumps({'installed_to': dst, 'enabled': enabled}))\n", encoding="utf-8")
    res = sc.run([exe, "-b", "--python", str(script)], timeout=120)
    script.unlink(missing_ok=True)
    data = None
    for line in res["stdout"].splitlines():
        if "@@RESULT@@" in line:
            data = json.loads(line.split("@@RESULT@@", 1)[1])
    if not data:
        return fail("install failed", details=tail_errors(res))
    return ok(**data, note="Restart Blender (or enable 'Claude Bridge' in Preferences > Add-ons), then call blender_bridge_status.")


@mcp.tool()
@safe
def blender_start_headless_bridge(blend_file: str = "") -> str:
    """Start a background Blender (no UI) serving the bridge, optionally with a .blend loaded. Stays alive
    between calls so scene state persists - ideal for multi-step modelling without reopening files."""
    global _headless_pid
    exe = blender_exe()
    cmd = [exe, "-b"]
    if blend_file:
        cmd.append(str(Path(blend_file).resolve()))
    cmd += ["--python", str(ADDON), "--", "--serve", "--port", str(BRIDGE_PORT)]
    log = sc.scratch_dir("blender") / "headless_bridge.log"
    _headless_pid = sc.spawn_detached(cmd, log=log)
    return ok(pid=_headless_pid, port=BRIDGE_PORT, log=str(log), hint="Wait ~3s then blender_bridge_status.")


@mcp.tool()
@safe
def blender_stop_headless_bridge() -> str:
    """Stop the background bridge Blender started by blender_start_headless_bridge."""
    global _headless_pid
    stopped = False
    try:
        _bridge("execute", {"code": "import bpy; bpy.ops.wm.quit_blender()"}, timeout=5)
        stopped = True
    except Exception:  # noqa: BLE001 - quitting drops the socket
        stopped = True
    if _headless_pid:
        try:
            os.kill(_headless_pid, 15)
        except OSError:
            pass
        _headless_pid = None
    return ok(stopped=stopped)


@mcp.tool()
@safe
def blender_bridge_status() -> str:
    """Ping the live Blender bridge (version, open file, object count, render engine)."""
    try:
        return ok(**_bridge("ping", timeout=3))
    except Exception as exc:  # noqa: BLE001
        return fail(f"bridge unreachable ({type(exc).__name__}: {exc}). Run blender_install_addon and open Blender, "
                    "or use blender_start_headless_bridge.")


@mcp.tool()
@safe
def blender_bridge_execute(code: str, timeout: int = 120) -> str:
    """Run Python inside the live Blender session. Namespace has bpy, bmesh, mathutils, Vector, Matrix, Euler.
    Assign `result = ...` to return a value; print() output is captured."""
    return ok(**_bridge("execute", {"code": code}, timeout=timeout))


@mcp.tool()
@safe
def blender_bridge_scene_info() -> str:
    """List objects (type, transforms, dimensions, materials, modifiers), collections, actions and render settings."""
    return ok(**_bridge("scene_info"))


@mcp.tool()
@safe
def blender_bridge_screenshot(path: str = "", width: int = 960, height: int = 540) -> str:
    """Capture the 3D viewport (or a quick Workbench render in headless mode) to a PNG you can view."""
    out = path or str(sc.tmp_file(".png", "blender_view_"))
    return ok(**_bridge("screenshot", {"path": out, "width": width, "height": height}, timeout=120))


@mcp.tool()
@safe
def blender_bridge_render(path: str, engine: str = "", samples: int = 0, width: int = 0, height: int = 0,
                          transparent: bool = False, frame: Optional[int] = None) -> str:
    """Full render of the live scene to a PNG."""
    args: dict[str, Any] = {"path": path, "transparent": transparent}
    if engine:
        args["engine"] = engine
    if samples:
        args["samples"] = samples
    if width:
        args["width"] = width
    if height:
        args["height"] = height
    if frame is not None:
        args["frame"] = frame
    return ok(**_bridge("render", args, timeout=900))


@mcp.tool()
@safe
def blender_bridge_export(path: str, selected_only: bool = False, animations: bool = True) -> str:
    """Export the live scene (or selection) to .glb/.gltf/.fbx/.obj - e.g. straight into a Godot project's assets folder."""
    return ok(**_bridge("export", {"path": path, "selected_only": selected_only, "animations": animations}, timeout=300))


@mcp.tool()
@safe
def blender_bridge_command(command: str, args: Optional[dict] = None) -> str:
    """Raw bridge command: ping, scene_info, execute, screenshot, render, export, import, save, open."""
    return ok(**_bridge(command, args or {}, timeout=300))


if __name__ == "__main__":
    mcp.run()
