#!/usr/bin/env python3
"""Godot Game Studio - Godot MCP server.

Project/scene/script authoring (pure file manipulation, no engine needed) plus headless engine
runs (check, import, run, test, export, frame capture) and a client for the live editor bridge.
"""
from __future__ import annotations

import functools
import json
import os
import re
import shutil
import sys
import traceback
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import godot_lib as gl  # noqa: E402
import studio_common as sc  # noqa: E402
from studio_common import fail, jdump, ok  # noqa: E402

mcp = sc.make_server(
    "godot",
    "Create, edit, validate, run, test and export Godot 4 projects. Most tools default to the "
    "project in GAME_PROJECT_DIR or the current directory when `project_path` is omitted. Scene "
    "tools write valid .tscn text; use godot_validate_project after bulk changes and godot_run_project "
    "to see real runtime errors. For a live editor use godot_open_editor + godot_install_editor_bridge.",
)

EDITOR_PORT = int(os.environ.get("GODOT_EDITOR_PORT", "9877") or 9877)
_version_cache: dict[str, str] = {}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def safe(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - tools must never crash the server
            return fail(f"{type(exc).__name__}: {exc}", trace=traceback.format_exc()[-1800:])
    return wrapper


def proj(project_path: str = "") -> Path:
    candidates = [project_path, sc.default_project_dir() or "", os.getcwd()]
    for c in candidates:
        if not c:
            continue
        p = sc.resolve_dir(c)
        root = gl.find_project_root(p) if p.exists() else None
        if root:
            return root
    raise ValueError(
        "No Godot project found. Pass project_path (folder containing project.godot), set "
        "GAME_PROJECT_DIR, or run Claude from inside the project folder. "
        "Use godot_create_project to make one.")


def fs(root: Path, res_path: str) -> Path:
    rel = res_path.strip().replace("\\", "/")
    if rel.startswith("res://"):
        rel = rel[6:]
    target = (root / rel).resolve()
    if root.resolve() not in [target, *target.parents]:
        raise ValueError(f"path escapes the project: {res_path}")
    return target


def to_res(root: Path, p: Path) -> str:
    return "res://" + str(p.resolve().relative_to(root.resolve())).replace("\\", "/")


def godot_exe() -> str:
    exe = sc.find_godot()
    if not exe:
        raise FileNotFoundError(
            "Godot executable not found. Set the GODOT_PATH environment variable to your Godot "
            "binary (on Windows prefer the *_console.exe build so output is captured), or add it to PATH.")
    if sc.SYSTEM == "Windows" and exe.lower().endswith(".exe") and "console" not in exe.lower():
        console = exe[:-4] + "_console.exe"
        if os.path.isfile(console):
            return console
    return exe


def godot_version_str() -> str:
    exe = godot_exe()
    if exe not in _version_cache:
        r = sc.run([exe, "--version"], timeout=30)
        _version_cache[exe] = (r["stdout"] or r["stderr"]).strip().splitlines()[-1] if (r["stdout"] or r["stderr"]) else "unknown"
    return _version_cache[exe]


def short_version() -> str:
    m = re.match(r"(\d+)\.(\d+)", godot_version_str())
    return f"{m.group(1)}.{m.group(2)}" if m else "4.7"


def is_dotnet(root: Path) -> bool:
    return any(root.glob("*.csproj")) or any(root.glob("*.sln"))


_PROBLEM_RE = re.compile(r"^\s*(SCRIPT ERROR|ERROR|WARNING|USER ERROR|USER WARNING|Parse Error|Debugger Break)\b", re.I)


def extract_problems(*texts: str, limit: int = 60) -> list[str]:
    out: list[str] = []
    for t in texts:
        lines = (t or "").splitlines()
        for i, line in enumerate(lines):
            if _PROBLEM_RE.match(line):
                msg = line.strip()
                if i + 1 < len(lines) and lines[i + 1].strip().startswith("at:"):
                    msg += "  " + lines[i + 1].strip()
                if msg not in out:
                    out.append(msg)
            if len(out) >= limit:
                return out
    return out


def engine(root: Path, args: list[str], timeout: int = 120, headless: bool = True,
           env: Optional[dict] = None) -> dict:
    cmd = [godot_exe()]
    if headless:
        cmd.append("--headless")
    cmd += ["--path", str(root)] + args
    res = sc.run(cmd, timeout=timeout, cwd=str(root), env=env)
    res["command"] = " ".join(cmd)
    res["problems"] = extract_problems(res["stdout"], res["stderr"])
    return res


def result_from_stdout(stdout: str) -> tuple[Any, str]:
    result = None
    kept = []
    for line in stdout.splitlines():
        if "@@RESULT@@" in line:
            payload = line.split("@@RESULT@@", 1)[1]
            try:
                result = json.loads(payload)
            except json.JSONDecodeError:
                result = payload
        else:
            kept.append(line)
    return result, "\n".join(kept)


def iter_project_files(root: Path, suffixes: tuple[str, ...], skip_addons: bool = True):
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in suffixes:
            continue
        parts = set(p.relative_to(root).parts)
        if ".godot" in parts or ".git" in parts or ".studio_tmp" in parts or "builds" in parts:
            continue
        if skip_addons and "addons" in parts:
            continue
        yield p


VALIDATE_ALL_SCRIPT = "\n".join([
    "extends SceneTree",
    "",
    "func _initialize() -> void:",
    "\tvar bad: Array = []",
    "\tvar checked := 0",
    '\tvar stack: Array = ["res://"]',
    "\twhile stack.size() > 0:",
    "\t\tvar dir_path: String = stack.pop_back()",
    "\t\tvar da := DirAccess.open(dir_path)",
    "\t\tif da == null:",
    "\t\t\tcontinue",
    "\t\tda.list_dir_begin()",
    '\t\tvar f := da.get_next()',
    '\t\twhile f != "":',
    "\t\t\tif da.current_is_dir():",
    '\t\t\t\tif not f.begins_with(".") and f != "addons" and f != "builds":',
    "\t\t\t\t\tstack.append(dir_path.path_join(f))",
    "\t\t\telse:",
    "\t\t\t\tvar ext := f.get_extension()",
    '\t\t\t\tif ext in ["gd", "tscn", "tres", "gdshader"]:',
    "\t\t\t\t\tvar p := dir_path.path_join(f)",
    "\t\t\t\t\tchecked += 1",
    '\t\t\t\t\tvar r = ResourceLoader.load(p, "", ResourceLoader.CACHE_MODE_IGNORE)',
    "\t\t\t\t\tif r == null:",
    "\t\t\t\t\t\tbad.append(p)",
    "\t\t\t\t\telif INSTANTIATE and r is PackedScene:",
    "\t\t\t\t\t\tvar inst = (r as PackedScene).instantiate()",
    "\t\t\t\t\t\tif inst == null:",
    '\t\t\t\t\t\t\tbad.append(p + " (instantiate failed)")',
    "\t\t\t\t\t\telse:",
    "\t\t\t\t\t\t\tinst.free()",
    "\t\t\tf = da.get_next()",
    "\t\tda.list_dir_end()",
    '\tprint("@@RESULT@@" + JSON.stringify({"checked": checked, "failed": bad}))',
    "\tquit()",
    "",
])


def write_tmp_script(root: Path, name: str, code: str) -> Path:
    d = root / ".studio_tmp"
    d.mkdir(exist_ok=True)
    (d / ".gdignore").write_text("", encoding="utf-8")
    p = d / name
    p.write_text(code, encoding="utf-8", newline="\n")
    return p


# =========================================================================== #
# discovery
# =========================================================================== #
@mcp.tool()
@safe
def godot_info() -> str:
    """Report the Godot executable, version, .NET support, editor-bridge status and defaults."""
    exe = sc.find_godot()
    info: dict[str, Any] = {"executable": exe, "platform": sc.SYSTEM,
                            "default_project_dir": sc.default_project_dir()}
    if exe:
        ver = godot_version_str()
        info["version"] = ver
        info["dotnet_build"] = "mono" in ver.lower()
    else:
        info["hint"] = "Set GODOT_PATH to the Godot binary (Windows: use Godot_v4.x_win64_console.exe)."
    try:
        info["editor_bridge"] = sc.tcp_json_call("127.0.0.1", EDITOR_PORT, {"cmd": "ping", "args": {}}, timeout=2)
    except Exception as exc:  # noqa: BLE001
        info["editor_bridge"] = f"not connected ({type(exc).__name__})"
    try:
        info["project"] = str(proj())
    except ValueError:
        info["project"] = None
    return ok(**info)


@mcp.tool()
@safe
def godot_class_reference(class_name: str, detail: bool = False, filter: str = "") -> str:
    """Look up a Godot class (properties, methods, signals, constants) from the INSTALLED engine via
    ClassDB - always matches your exact version. `filter` keeps only members containing the text."""
    if not re.fullmatch(r"[A-Za-z0-9_]+", class_name):
        return fail("class_name must be alphanumeric")
    root = proj()
    script = write_tmp_script(root, "class_ref.gd", gl.CLASS_REF_SCRIPT.replace("__CLASS__", class_name))
    res = engine(root, ["-s", to_res(root, script)], timeout=60)
    data, _ = result_from_stdout(res["stdout"])
    if not isinstance(data, dict):
        return fail("no result from engine", stderr=res["stderr"], stdout=res["stdout"])
    summary = gl.summarize_class(data, detail)
    if filter:
        f = filter.lower()
        for k in ("properties", "methods", "signals", "constants"):
            summary[k] = [x for x in summary.get(k, []) if f in x.lower()]
    return ok(**summary)


@mcp.tool()
@safe
def godot_list_classes(prefix: str = "", limit: int = 300) -> str:
    """List all engine classes (optionally filtered by prefix, e.g. 'Audio', 'Physics')."""
    root = proj()
    script = write_tmp_script(root, "class_list.gd", gl.CLASS_LIST_SCRIPT)
    res = engine(root, ["-s", to_res(root, script)], timeout=60)
    data, _ = result_from_stdout(res["stdout"])
    if not isinstance(data, list):
        return fail("no result from engine", stderr=res["stderr"])
    names = sorted(n for n in data if n.lower().startswith(prefix.lower()))
    return ok(count=len(names), classes=names[:limit])


# =========================================================================== #
# project
# =========================================================================== #
@mcp.tool()
@safe
def godot_create_project(path: str, name: str, kind: str = "2d", renderer: str = "forward_plus",
                         pixel_art: bool = False, dotnet: bool = False,
                         width: int = 1280, height: int = 720) -> str:
    """Create a new Godot 4 project skeleton (folders, project.godot, icon, gitignore, CLAUDE.md,
    main scene). kind: '2d'|'3d'. renderer: 'forward_plus'|'mobile'|'compatibility' (use compatibility
    for web export / old GPUs). pixel_art sets nearest filtering, integer scaling and a 4x viewport."""
    root = sc.resolve_dir(path, create=True)
    version = "4.7"
    try:
        version = short_version()
    except FileNotFoundError:
        pass
    created = gl.create_project(root, name, kind, renderer, dotnet, width, height, pixel_art, version)
    return ok(project=str(root), created=created, godot_features_version=version,
              next="Add scenes with godot_create_scene, then godot_validate_project.")


@mcp.tool()
@safe
def godot_project_info(project_path: str = "") -> str:
    """Summarize a project: name, main scene, renderer, autoloads, input actions, scenes, scripts."""
    root = proj(project_path)
    settings = gl.project_settings((root / "project.godot").read_text(encoding="utf-8"))
    app = settings.get("application", {})
    counts: dict[str, int] = {}
    scenes, scripts = [], []
    for p in iter_project_files(root, (".tscn", ".tres", ".gd", ".cs", ".gdshader", ".png", ".svg", ".wav", ".ogg", ".mp3", ".glb", ".gltf"), skip_addons=False):
        counts[p.suffix.lower()] = counts.get(p.suffix.lower(), 0) + 1
        if p.suffix == ".tscn":
            scenes.append(to_res(root, p))
        elif p.suffix in (".gd", ".cs") and "addons" not in p.parts:
            scripts.append(to_res(root, p))
    return ok(
        project=str(root), name=app.get("config/name"), main_scene=app.get("run/main_scene"),
        features=app.get("config/features"), renderer=settings.get("rendering", {}).get("renderer/rendering_method"),
        autoloads=settings.get("autoload", {}), input_actions=list(settings.get("input", {}).keys()),
        layer_names=settings.get("layer_names", {}), dotnet=is_dotnet(root),
        file_counts=counts, scenes=scenes[:150], scripts=scripts[:200],
        editor_bridge_installed=(root / "addons" / "claude_bridge" / "plugin.cfg").exists(),
        export_presets=(root / "export_presets.cfg").exists(),
    )


@mcp.tool()
@safe
def godot_project_setting_get(project_path: str = "", path: str = "") -> str:
    """Read project.godot settings. path like 'display/window/size/viewport_width' or a whole section
    like 'autoload'. Empty path returns everything (raw Godot literals)."""
    root = proj(project_path)
    settings = gl.project_settings((root / "project.godot").read_text(encoding="utf-8"))
    if not path:
        return ok(settings=settings)
    path = path.strip().strip("/")
    if path in settings:
        return ok(section=path, values=settings[path])
    section, key = gl.split_setting_path(path)
    val = settings.get(section, {}).get(key)
    return ok(path=path, value=val, found=val is not None)


@mcp.tool()
@safe
def godot_project_setting_set(project_path: str = "", path: str = "", value: Any = None,
                              remove: bool = False) -> str:
    """Set (or remove) a project.godot setting. `path` is 'section/key/with/slashes', e.g.
    'display/window/size/viewport_width'. `value` may be a number/bool/list or a Godot literal string
    (e.g. 'Vector2i(320, 180)', '\"canvas_items\"'); plain words are auto-quoted."""
    root = proj(project_path)
    cfg = root / "project.godot"
    text = cfg.read_text(encoding="utf-8")
    section, key = gl.split_setting_path(path)
    if remove:
        text, removed = gl.remove_project_setting(text, section, key)
        cfg.write_text(text, encoding="utf-8", newline="\n")
        return ok(removed=removed, path=path)
    literal = gl.to_literal(value)
    cfg.write_text(gl.set_project_setting(text, section, key, literal), encoding="utf-8", newline="\n")
    return ok(path=path, value=literal)


@mcp.tool()
@safe
def godot_add_autoload(name: str, script_path: str, project_path: str = "", singleton: bool = True) -> str:
    """Register an autoload (global singleton). script_path like res://scripts/autoload/game.gd or a .tscn."""
    root = proj(project_path)
    if not fs(root, script_path).exists():
        return fail(f"{script_path} does not exist yet - write it first")
    prefix = "*" if singleton else ""
    cfg = root / "project.godot"
    cfg.write_text(gl.set_project_setting(cfg.read_text(encoding="utf-8"), "autoload", name,
                                          f'"{prefix}{script_path}"'), encoding="utf-8", newline="\n")
    return ok(autoload=name, path=script_path)


@mcp.tool()
@safe
def godot_add_input_action(action: str, inputs: list[str], project_path: str = "", deadzone: float = 0.2) -> str:
    """Define an input action. inputs: tokens like 'key:A', 'key:Space', 'key:Left', 'mouse:left',
    'joy_button:0', 'joy_axis:0:-1' (axis:value). Replaces an existing action of the same name."""
    root = proj(project_path)
    cfg = root / "project.godot"
    value = gl.input_action_value(inputs, deadzone)
    cfg.write_text(gl.set_project_setting(cfg.read_text(encoding="utf-8"), "input", action, value),
                   encoding="utf-8", newline="\n")
    return ok(action=action, inputs=inputs)


@mcp.tool()
@safe
def godot_add_input_actions_bulk(actions: dict, project_path: str = "") -> str:
    """Define many input actions at once: {"jump": ["key:Space","joy_button:0"], "left": ["key:A","key:Left"]}."""
    root = proj(project_path)
    cfg = root / "project.godot"
    text = cfg.read_text(encoding="utf-8")
    for action, inputs in actions.items():
        text = gl.set_project_setting(text, "input", action, gl.input_action_value(list(inputs)))
    cfg.write_text(text, encoding="utf-8", newline="\n")
    return ok(actions=list(actions))


@mcp.tool()
@safe
def godot_set_layer_names(kind: str, layers: dict, project_path: str = "") -> str:
    """Name physics/render layers. kind: '2d_physics','3d_physics','2d_render','3d_render',
    '2d_navigation','3d_navigation','avoidance'. layers: {"1": "world", "2": "player"}."""
    root = proj(project_path)
    cfg = root / "project.godot"
    text = cfg.read_text(encoding="utf-8")
    for num, label in layers.items():
        text = gl.set_project_setting(text, "layer_names", f"{kind}/layer_{int(num)}", json.dumps(label))
    cfg.write_text(text, encoding="utf-8", newline="\n")
    return ok(kind=kind, layers=layers)


@mcp.tool()
@safe
def godot_set_pixel_art_defaults(project_path: str = "", base_width: int = 320, base_height: int = 180,
                                 window_scale: int = 4) -> str:
    """Apply crisp pixel-art settings: nearest filtering, viewport stretch with integer scale, pixel snapping."""
    root = proj(project_path)
    cfg = root / "project.godot"
    text = cfg.read_text(encoding="utf-8")
    pairs = {
        ("display", "window/size/viewport_width"): str(base_width),
        ("display", "window/size/viewport_height"): str(base_height),
        ("display", "window/size/window_width_override"): str(base_width * window_scale),
        ("display", "window/size/window_height_override"): str(base_height * window_scale),
        ("display", "window/stretch/mode"): '"viewport"',
        ("display", "window/stretch/scale_mode"): '"integer"',
        ("rendering", "textures/canvas_textures/default_texture_filter"): "0",
        ("rendering", "2d/snap/snap_2d_transforms_to_pixel"): "true",
        ("rendering", "2d/snap/snap_2d_vertices_to_pixel"): "true",
    }
    for (sec, key), val in pairs.items():
        text = gl.set_project_setting(text, sec, key, val)
    cfg.write_text(text, encoding="utf-8", newline="\n")
    return ok(applied={f"{s}/{k}": v for (s, k), v in pairs.items()})


@mcp.tool()
@safe
def godot_list_templates() -> str:
    """List bundled GDScript/scene templates (player controllers, state machine, save system, ...)."""
    return ok(templates=gl.list_templates())


@mcp.tool()
@safe
def godot_add_template(template: str, dest: str = "", project_path: str = "", overwrite: bool = False) -> str:
    """Copy a bundled template into the project. template: name from godot_list_templates (e.g.
    'gdscript/player_platformer.gd'). dest defaults to res://scripts/<filename>."""
    root = proj(project_path)
    src = gl.TEMPLATES_DIR / template
    if not src.is_file():
        matches = [t for t in gl.list_templates() if t.endswith(template)]
        if len(matches) != 1:
            return fail(f"unknown template '{template}'", available=gl.list_templates())
        src = gl.TEMPLATES_DIR / matches[0]
    target = fs(root, dest or f"res://scripts/{src.name}")
    if target.exists() and not overwrite:
        return fail(f"{to_res(root, target)} already exists (pass overwrite=true)")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, target)
    return ok(created=to_res(root, target))


# =========================================================================== #
# scripts
# =========================================================================== #
@mcp.tool()
@safe
def godot_write_script(res_path: str, content: str, project_path: str = "", check: bool = True) -> str:
    """Write a .gd/.gdshader/.cs/.cfg/.json (any text) file inside the project, then lint it
    (and run the engine parser for .gd if Godot is available). Returns problems to fix."""
    root = proj(project_path)
    target = fs(root, res_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content.replace("\r\n", "\n"), encoding="utf-8", newline="\n")
    out: dict[str, Any] = {"written": to_res(root, target), "bytes": len(content.encode("utf-8"))}
    if check and target.suffix == ".gd":
        out["lint"] = gl.lint_gdscript(content)
        if sc.find_godot():
            res = engine(root, ["--check-only", "--script", to_res(root, target)], timeout=60)
            out["engine_check"] = {"returncode": res["returncode"], "problems": res["problems"]}
    return ok(**out)


@mcp.tool()
@safe
def godot_check_script(res_path: str, project_path: str = "") -> str:
    """Parse-check a GDScript with the real engine (`--check-only`) plus the structural linter."""
    root = proj(project_path)
    target = fs(root, res_path)
    if not target.exists():
        return fail(f"{res_path} not found")
    lint = gl.lint_gdscript(target.read_text(encoding="utf-8"))
    res = engine(root, ["--check-only", "--script", to_res(root, target)], timeout=60)
    clean = res["returncode"] == 0 and not res["problems"] and not any(i["severity"] == "error" for i in lint)
    return ok(clean=clean, returncode=res["returncode"], problems=res["problems"], lint=lint, stderr=res["stderr"][-1500:])


@mcp.tool()
@safe
def godot_lint(res_path: str, project_path: str = "") -> str:
    """Fast, engine-free GDScript lint (Godot 3 leftovers, mixed indentation, missing colons, brackets)."""
    root = proj(project_path)
    target = fs(root, res_path)
    return ok(file=res_path, issues=gl.lint_gdscript(target.read_text(encoding="utf-8")))


@mcp.tool()
@safe
def godot_format_gdscript(res_path: str, project_path: str = "", lint_only: bool = False) -> str:
    """Format (gdformat) or lint (gdlint) a script using gdtoolkit if installed (pip install gdtoolkit)."""
    root = proj(project_path)
    target = fs(root, res_path)
    tool = "gdlint" if lint_only else "gdformat"
    exe = shutil.which(tool)
    if not exe:
        return fail(f"{tool} not found. Install with: pip install gdtoolkit")
    res = sc.run([exe, str(target)], timeout=60)
    return ok(tool=tool, returncode=res["returncode"], output=(res["stdout"] + res["stderr"]).strip())


@mcp.tool()
@safe
def godot_search(pattern: str, project_path: str = "", glob: str = "*.gd,*.tscn,*.tres,*.cs,*.gdshader,project.godot",
                 regex: bool = False, limit: int = 100) -> str:
    """Search project text files (symbol usages, node names, res:// paths). Returns file:line: text."""
    root = proj(project_path)
    pats = [g.strip() for g in glob.split(",") if g.strip()]
    rx = re.compile(pattern if regex else re.escape(pattern))
    hits: list[str] = []
    for p in root.rglob("*"):
        if not p.is_file() or not any(p.match(g) for g in pats):
            continue
        parts = p.relative_to(root).parts
        if ".godot" in parts or ".git" in parts or "builds" in parts:
            continue
        try:
            for no, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if rx.search(line):
                    hits.append(f"{to_res(root, p)}:{no}: {line.strip()[:160]}")
                    if len(hits) >= limit:
                        return ok(truncated=True, matches=hits)
        except OSError:
            continue
    return ok(truncated=False, count=len(hits), matches=hits)


@mcp.tool()
@safe
def godot_move_file(old_res_path: str, new_res_path: str, project_path: str = "") -> str:
    """Move/rename a project file and rewrite every res:// reference to it (scenes, scripts, project.godot),
    carrying the .import and .uid sidecars along."""
    root = proj(project_path)
    src, dst = fs(root, old_res_path), fs(root, new_res_path)
    if not src.exists():
        return fail(f"{old_res_path} not found")
    if dst.exists():
        return fail(f"{new_res_path} already exists")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    for suffix in (".import", ".uid"):
        side = Path(str(src) + suffix)
        if side.exists():
            shutil.move(str(side), str(dst) + suffix)
    old = old_res_path if old_res_path.startswith("res://") else "res://" + old_res_path.lstrip("/")
    new = new_res_path if new_res_path.startswith("res://") else "res://" + new_res_path.lstrip("/")
    changed = []
    for p in iter_project_files(root, (".tscn", ".tres", ".gd", ".cs", ".godot", ".cfg", ".import", ".gdshader", ".json"), skip_addons=False):
        try:
            txt = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if old in txt:
            p.write_text(txt.replace(old, new), encoding="utf-8", newline="\n")
            changed.append(to_res(root, p))
    return ok(moved=[old, new], references_updated=changed)


# =========================================================================== #
# scenes & resources
# =========================================================================== #
@mcp.tool()
@safe
def godot_create_scene(scene_path: str, spec: dict, project_path: str = "", overwrite: bool = False) -> str:
    """Create a .tscn from a spec (writes valid Godot 4 text format and validates it).

    spec = {root:{name,type,script?,properties?}, nodes:[{name,type,parent,script?,instance?,groups?,
    properties?}], sub_resources:[{id,type,properties}], connections:[{signal,from,to,method}]}.
    parent is '.' for direct children of the root, else the path from the root (e.g. 'Hurtbox').
    Property values: numbers/bools/lists, Godot literals ('Vector2(1, 2)', 'Color(1, 0, 0, 1)'),
    res:// paths (auto-registered as resources), '@id' for a sub_resource, plain text is auto-quoted.
    Use instance='res://scenes/x.tscn' (no type) to instance another scene."""
    root = proj(project_path)
    target = fs(root, scene_path)
    if target.exists() and not overwrite:
        return fail(f"{scene_path} exists (pass overwrite=true or use godot_scene_add_nodes)")
    text = gl.build_scene(spec)
    problems = gl.validate_scene_text(text, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")
    return ok(created=to_res(root, target), problems=problems, tree=gl.scene_tree_text(text))


@mcp.tool()
@safe
def godot_read_scene(scene_path: str, project_path: str = "", raw: bool = False) -> str:
    """Read a .tscn/.tres: node tree, scripts, instanced scenes, resources, connections (or raw text)."""
    root = proj(project_path)
    text = fs(root, scene_path).read_text(encoding="utf-8")
    if raw:
        return ok(text=text)
    parsed = gl.parse_scene(text)
    return ok(tree=gl.scene_tree_text(text), nodes=parsed["nodes"], ext_resources=parsed["ext_resources"],
              sub_resources=[{"id": s["id"], "type": s["type"]} for s in parsed["sub_resources"]],
              connections=parsed["connections"], problems=gl.validate_scene_text(text, root))


@mcp.tool()
@safe
def godot_scene_add_nodes(scene_path: str, spec: dict, project_path: str = "") -> str:
    """Add nodes/sub_resources/connections to an existing scene (parents must already exist or come first).
    spec = {nodes:[...], sub_resources:[...], connections:[...]} - same shape as godot_create_scene."""
    root = proj(project_path)
    target = fs(root, scene_path)
    new_text = gl.add_to_scene(target.read_text(encoding="utf-8"), spec)
    target.write_text(new_text, encoding="utf-8", newline="\n")
    return ok(scene=scene_path, problems=gl.validate_scene_text(new_text, root), tree=gl.scene_tree_text(new_text))


@mcp.tool()
@safe
def godot_scene_set_property(scene_path: str, node_path: str, prop: str, value: Any, project_path: str = "") -> str:
    """Set a property on a node inside a .tscn. node_path '.' = root, else 'Child/GrandChild'."""
    root = proj(project_path)
    target = fs(root, scene_path)
    new_text = gl.set_node_property(target.read_text(encoding="utf-8"), node_path, prop, value)
    target.write_text(new_text, encoding="utf-8", newline="\n")
    return ok(scene=scene_path, node=node_path, property=prop, problems=gl.validate_scene_text(new_text, root))


@mcp.tool()
@safe
def godot_scene_remove_node(scene_path: str, node_path: str, project_path: str = "") -> str:
    """Remove a node (and its children and their signal connections) from a .tscn."""
    root = proj(project_path)
    target = fs(root, scene_path)
    new_text = gl.remove_node(target.read_text(encoding="utf-8"), node_path)
    target.write_text(new_text, encoding="utf-8", newline="\n")
    return ok(scene=scene_path, removed=node_path, tree=gl.scene_tree_text(new_text))


@mcp.tool()
@safe
def godot_create_resource(res_path: str, resource_type: str, properties: Optional[dict] = None,
                          sub_resources: Optional[list] = None, script: str = "",
                          project_path: str = "", overwrite: bool = False) -> str:
    """Create a .tres resource (Theme, LabelSettings, Curve, custom Resource subclass via `script`, ...)."""
    root = proj(project_path)
    target = fs(root, res_path)
    if target.exists() and not overwrite:
        return fail(f"{res_path} exists")
    text = gl.build_resource(resource_type, properties or {}, sub_resources, script or None)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")
    return ok(created=to_res(root, target))


@mcp.tool()
@safe
def godot_validate_project(project_path: str = "", engine_check: bool = True, instantiate_scenes: bool = True) -> str:
    """Validate everything: scene structure (parents, ids, missing files), GDScript lint, and - if Godot
    is available - load every script/scene/resource with the real engine to surface parse errors."""
    root = proj(project_path)
    static: list[str] = []
    for p in iter_project_files(root, (".tscn", ".tres")):
        for prob in gl.validate_scene_text(p.read_text(encoding="utf-8"), root):
            static.append(f"{to_res(root, p)}: {prob}")
    lint_errors: list[str] = []
    for p in iter_project_files(root, (".gd",)):
        for issue in gl.lint_gdscript(p.read_text(encoding="utf-8")):
            if issue["severity"] in ("error", "warning"):
                lint_errors.append(f"{to_res(root, p)}:{issue['line']}: {issue['message']}")
    out: dict[str, Any] = {"project": str(root), "scene_problems": static, "lint": lint_errors}
    settings = gl.project_settings((root / "project.godot").read_text(encoding="utf-8"))
    main = settings.get("application", {}).get("run/main_scene", "").strip('"')
    if main and not fs(root, main).exists():
        static.append(f"project.godot: run/main_scene points to missing {main}")
    if engine_check and sc.find_godot():
        code = VALIDATE_ALL_SCRIPT.replace("INSTANTIATE", "true" if instantiate_scenes else "false")
        script = write_tmp_script(root, "validate_all.gd", code)
        res = engine(root, ["-s", to_res(root, script)], timeout=180)
        data, _ = result_from_stdout(res["stdout"])
        out["engine"] = {"loaded": data, "problems": res["problems"], "returncode": res["returncode"]}
    elif engine_check:
        out["engine"] = "skipped: Godot executable not found (set GODOT_PATH)"
    failed = bool(static or any("error" in l.lower() or "Godot 3" in l for l in lint_errors))
    if isinstance(out.get("engine"), dict):
        data = out["engine"].get("loaded") or {}
        failed = failed or bool(data.get("failed")) or bool(out["engine"]["problems"])
    out["healthy"] = not failed
    return ok(**out)


# =========================================================================== #
# engine runs
# =========================================================================== #
@mcp.tool()
@safe
def godot_run_script(code: str, project_path: str = "", timeout: int = 60) -> str:
    """Run GDScript headless inside the project (full engine API: ResourceSaver, DirAccess, ClassDB,
    PackedScene, ...). `code` is either a body (runs inside an async function of a SceneTree script, use
    print()) or a full script that `extends SceneTree`/MainLoop. Print '@@RESULT@@' + JSON.stringify(x)
    to return structured data. Call quit() yourself in full scripts."""
    root = proj(project_path)
    script = write_tmp_script(root, "run_script.gd", gl.wrap_script(code))
    res = engine(root, ["-s", to_res(root, script)], timeout=timeout)
    data, stdout = result_from_stdout(res["stdout"])
    return ok(returncode=res["returncode"], result=data, stdout=stdout, stderr=res["stderr"],
              problems=res["problems"], timed_out=res["timed_out"])


@mcp.tool()
@safe
def godot_import(project_path: str = "", timeout: int = 300) -> str:
    """Import/re-import all assets headless (`--import`). Run after adding images, audio, models or fonts."""
    root = proj(project_path)
    res = engine(root, ["--import", "--quit"], timeout=timeout)
    return ok(returncode=res["returncode"], problems=res["problems"], seconds=res["seconds"],
              output=(res["stdout"] + res["stderr"])[-2500:])


@mcp.tool()
@safe
def godot_run_project(project_path: str = "", scene: str = "", seconds: float = 5.0, headless: bool = True,
                      extra_args: Optional[list[str]] = None, fixed_fps: int = 60) -> str:
    """Run the game (or one scene) for N simulated seconds and return the log + parsed errors/warnings.
    Uses --fixed-fps so time is deterministic. Pass extra_args like ['--', '--playtest'] for user args."""
    root = proj(project_path)
    frames = max(1, int(seconds * fixed_fps))
    args = ["--fixed-fps", str(fixed_fps), "--quit-after", str(frames)]
    if scene:
        args.append(scene if scene.startswith("res://") else to_res(root, fs(root, scene)))
    args += list(extra_args or [])
    res = engine(root, args, timeout=int(seconds * 4) + 90, headless=headless)
    stdout = res["stdout"]
    errors = [p for p in res["problems"] if re.match(r"\s*(SCRIPT ERROR|ERROR|USER ERROR|Parse Error)", p, re.I)]
    return ok(clean=res["returncode"] == 0 and not errors, returncode=res["returncode"], frames=frames,
              errors=errors, warnings=[p for p in res["problems"] if p not in errors],
              stdout=stdout[-5000:], stderr=res["stderr"][-2500:], timed_out=res["timed_out"],
              command=res["command"])


@mcp.tool()
@safe
def godot_capture_frames(project_path: str = "", scene: str = "", frames: int = 120, fps: int = 30,
                         out_dir: str = "", sample: int = 8) -> str:
    """Render the game with Movie Maker (needs a GPU/display; not headless) into PNG frames and build a
    contact sheet of `sample` evenly spaced frames you can inspect visually. Great for art/VFX review."""
    root = proj(project_path)
    out = Path(out_dir) if out_dir else root / ".studio_tmp" / "capture"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True, exist_ok=True)
    args = ["--write-movie", str(out / "frame.png"), "--fixed-fps", str(fps), "--quit-after", str(frames)]
    if scene:
        args.append(scene)
    res = engine(root, args, timeout=max(120, frames * 2), headless=False)
    pngs = sorted(out.glob("frame*.png"))
    sheet = None
    if pngs:
        import studio_images as si
        step = max(1, len(pngs) // max(1, sample))
        picks = [str(p) for p in pngs[::step][:sample]]
        sheet = si.contact_sheet(picks, str(out / "contact_sheet.png"), columns=4, cell=320)
    return ok(frames_written=len(pngs), folder=str(out), contact_sheet=sheet, problems=res["problems"],
              hint=None if pngs else "No frames: Movie Maker needs a real display/GPU (try on your desktop or xvfb).")


@mcp.tool()
@safe
def godot_run_tests(project_path: str = "", framework: str = "gut", path: str = "res://tests", timeout: int = 300) -> str:
    """Run unit tests headless. framework: 'gut' (addons/gut) or 'gdunit4' (addons/gdUnit4)."""
    root = proj(project_path)
    if framework == "gut":
        if not (root / "addons" / "gut").exists():
            return fail("GUT not installed (addons/gut). Install from the AssetLib/GitHub (bitwes/Gut), enable it, retry.")
        res = engine(root, ["-s", "res://addons/gut/gut_cmdln.gd", f"-gdir={path}", "-gexit"], timeout=timeout)
    elif framework == "gdunit4":
        runner = root / "addons" / "gdUnit4" / "bin" / "GdUnitCmdTool.gd"
        if not runner.exists():
            return fail("gdUnit4 not installed (addons/gdUnit4).")
        res = engine(root, ["-s", "-d", "res://addons/gdUnit4/bin/GdUnitCmdTool.gd", "-a", path, "--ignoreHeadlessMode"], timeout=timeout)
    else:
        return fail("framework must be 'gut' or 'gdunit4'")
    out = res["stdout"] + "\n" + res["stderr"]
    return ok(passed=res["returncode"] == 0, returncode=res["returncode"], output=out[-6000:], problems=res["problems"])


@mcp.tool()
@safe
def godot_dotnet_build(project_path: str = "", configuration: str = "Debug") -> str:
    """Build the C# solution (`dotnet build`) - run before testing .NET-build projects."""
    root = proj(project_path)
    dotnet = shutil.which("dotnet")
    if not dotnet:
        return fail("dotnet SDK not found. Install the .NET SDK (8+; 9+ for Android).")
    res = sc.run([dotnet, "build", "-c", configuration, "--nologo", "-clp:ErrorsOnly;Summary"], timeout=300, cwd=str(root))
    return ok(success=res["returncode"] == 0, output=(res["stdout"] + res["stderr"])[-4000:])


# =========================================================================== #
# export
# =========================================================================== #
_PRESET_TEMPLATES = {
    "windows": ('Windows Desktop', 'builds/windows/{name}.exe', [
        'custom_template/debug=""', 'custom_template/release=""', "debug/export_console_wrapper=1",
        "binary_format/embed_pck=true", 'binary_format/architecture="x86_64"', "texture_format/s3tc_bptc=true",
        "texture_format/etc2_astc=false", "application/modify_resources=false"]),
    "linux": ('Linux', 'builds/linux/{name}.x86_64', [
        'custom_template/debug=""', 'custom_template/release=""', "binary_format/embed_pck=true",
        'binary_format/architecture="x86_64"', "texture_format/s3tc_bptc=true", "texture_format/etc2_astc=false"]),
    "web": ('Web', 'builds/web/index.html', [
        'custom_template/debug=""', 'custom_template/release=""', "variant/extensions_support=false",
        "variant/thread_support=false", "vram_texture_compression/for_desktop=true",
        "vram_texture_compression/for_mobile=false", "html/export_icon=true", "html/canvas_resize_policy=2",
        "html/focus_canvas_on_start=true", "html/experimental_virtual_keyboard=false"]),
    "macos": ('macOS', 'builds/macos/{name}.zip', [
        'custom_template/debug=""', 'custom_template/release=""', 'binary_format/architecture="universal"',
        'application/bundle_identifier="com.example.{ident}"', 'application/short_version="1.0.0"',
        'application/version="1.0.0"', "codesign/codesign=0", "notarization/notarization=0"]),
}


@mcp.tool()
@safe
def godot_create_export_presets(platforms: Optional[list[str]] = None, project_path: str = "", overwrite: bool = False) -> str:
    """Write export_presets.cfg with presets for windows/linux/web/macos (default: windows, linux, web).
    Android/iOS need keystores/signing and are best configured once in the editor. Requires matching
    export templates installed (Editor > Manage Export Templates)."""
    root = proj(project_path)
    cfg = root / "export_presets.cfg"
    if cfg.exists() and not overwrite:
        return fail("export_presets.cfg exists (pass overwrite=true)")
    settings = gl.project_settings((root / "project.godot").read_text(encoding="utf-8"))
    name = re.sub(r"[^A-Za-z0-9_\-]", "", settings.get("application", {}).get("config/name", '"game"').strip('"').replace(" ", "_")) or "game"
    parts: list[str] = []
    for idx, plat in enumerate(platforms or ["windows", "linux", "web"]):
        if plat not in _PRESET_TEMPLATES:
            return fail(f"unknown platform '{plat}'. Use: {', '.join(_PRESET_TEMPLATES)}")
        plat_name, path, options = _PRESET_TEMPLATES[plat]
        parts.append("\n".join([
            f"[preset.{idx}]", "", f'name="{plat_name}"', f'platform="{plat_name}"', "runnable=true",
            "advanced_options=false", "dedicated_server=false", 'custom_features=""', 'export_filter="all_resources"',
            'include_filter=""', 'exclude_filter=""', f'export_path="{path.format(name=name)}"', "patches=PackedStringArray()",
            'encryption_include_filters=""', 'encryption_exclude_filters=""', "seed=0", "encrypt_pck=false",
            "encrypt_directory=false", "script_export_mode=2", "",
            f"[preset.{idx}.options]", "", *[o.format(ident=name.lower(), name=name) for o in options], "",
        ]))
    cfg.write_text("\n".join(parts), encoding="utf-8", newline="\n")
    return ok(created="export_presets.cfg", presets=platforms or ["windows", "linux", "web"])


@mcp.tool()
@safe
def godot_list_export_presets(project_path: str = "") -> str:
    """List export presets defined in export_presets.cfg."""
    root = proj(project_path)
    cfg = root / "export_presets.cfg"
    if not cfg.exists():
        return ok(presets=[], hint="Use godot_create_export_presets or create presets in the editor.")
    presets = re.findall(r'^\[preset\.(\d+)\]\s*\n\s*\nname="([^"]+)"\s*\nplatform="([^"]+)"', cfg.read_text(encoding="utf-8"), re.M)
    paths = re.findall(r'export_path="([^"]*)"', cfg.read_text(encoding="utf-8"))
    return ok(presets=[{"index": int(i), "name": n, "platform": p, "export_path": paths[int(i)] if int(i) < len(paths) else ""}
                       for i, n, p in presets])


@mcp.tool()
@safe
def godot_export(preset: str, output: str = "", project_path: str = "", debug: bool = False,
                 pack_only: bool = False, timeout: int = 900) -> str:
    """Export with a named preset (`--export-release`/`--export-debug`/`--export-pack`). `output` defaults to the preset's path."""
    root = proj(project_path)
    cfg = root / "export_presets.cfg"
    if not cfg.exists():
        return fail("no export_presets.cfg - run godot_create_export_presets first")
    if not output:
        text = cfg.read_text(encoding="utf-8")
        m = re.search(rf'name="{re.escape(preset)}".*?export_path="([^"]*)"', text, re.S)
        output = m.group(1) if m else ""
    if not output:
        return fail("could not determine output path; pass output")
    out_path = (root / output) if not os.path.isabs(output) else Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    flag = "--export-pack" if pack_only else ("--export-debug" if debug else "--export-release")
    res = engine(root, [flag, preset, str(out_path)], timeout=timeout)
    exists = out_path.exists()
    return ok(success=res["returncode"] == 0 and exists, output=str(out_path), exists=exists,
              size_mb=round(out_path.stat().st_size / 1048576, 2) if exists else None,
              problems=res["problems"], log=(res["stdout"] + res["stderr"])[-2500:])


# =========================================================================== #
# live editor
# =========================================================================== #
@mcp.tool()
@safe
def godot_open_editor(project_path: str = "") -> str:
    """Launch the Godot editor on the project (detached). Then call godot_install_editor_bridge once."""
    root = proj(project_path)
    exe = sc.find_godot()
    if not exe:
        return fail("Godot not found - set GODOT_PATH")
    if sc.SYSTEM == "Windows" and "console" in exe.lower():
        alt = exe.replace("_console", "")
        exe = alt if os.path.isfile(alt) else exe
    pid = sc.spawn_detached([exe, "--editor", "--path", str(root)], cwd=str(root))
    return ok(pid=pid, hint="Wait ~10s for the editor, then use godot_editor_status.")


@mcp.tool()
@safe
def godot_install_editor_bridge(project_path: str = "") -> str:
    """Install + enable the Claude Bridge editor plugin (TCP 127.0.0.1:9877) so Claude can drive the open
    editor: scene tree, add/remove/edit nodes, run/stop, screenshots, execute GDScript in the editor."""
    root = proj(project_path)
    copied = gl.install_addon(root)
    return ok(installed=copied, note="Restart the editor (or Project > Reload Current Project) if it is already open.")


def editor_call(cmd: str, args: Optional[dict] = None, timeout: float = 30.0) -> dict:
    payload: dict[str, Any] = {"cmd": cmd, "args": args or {}}
    token = os.environ.get("GODOT_EDITOR_TOKEN", "").strip()
    if token:
        payload["token"] = token
    return sc.tcp_json_call("127.0.0.1", EDITOR_PORT, payload, timeout=timeout)


@mcp.tool()
@safe
def godot_editor_status() -> str:
    """Ping the live editor bridge: engine version, project name, open scenes, playing state."""
    try:
        return ok(**editor_call("ping", timeout=3))
    except Exception as exc:  # noqa: BLE001
        return fail(f"editor bridge unreachable ({type(exc).__name__}: {exc}). Open the editor with godot_open_editor, "
                    "run godot_install_editor_bridge, and make sure the plugin is enabled.")


@mcp.tool()
@safe
def godot_editor(command: str, args: Optional[dict] = None) -> str:
    """Send a command to the live editor. Commands: ping, open_scene{path}, save_scene, reload_scene{path},
    scene_tree{depth?}, get_selection, select_node{path}, add_node{parent,type,name,properties?,script?},
    remove_node{path}, rename_node{path,name}, reparent_node{path,new_parent}, set_property{path,property,value},
    get_property{path,property}, set_script{path,script}, instance_scene{parent,scene,name?}, run_scene
    {path?}, run_main, stop, is_playing, screenshot{target:'2d'|'3d'|'editor'|'game', path}, execute{code},
    filesystem_scan, reimport{paths}, set_project_setting{name,value}, get_open_scenes, new_scene{type,path}.
    `execute` code runs as the body of func run(editor, root) and may `return` a value."""
    return ok(**editor_call(command, args or {}, timeout=60))


@mcp.tool()
@safe
def godot_editor_screenshot(target: str = "editor", path: str = "") -> str:
    """Screenshot the live editor ('editor' whole UI, '2d' or '3d' viewport) to a PNG you can view."""
    out = path or str(sc.tmp_file(".png", "godot_shot_"))
    res = editor_call("screenshot", {"target": target, "path": out}, timeout=30)
    return ok(**res)


if __name__ == "__main__":
    mcp.run()
