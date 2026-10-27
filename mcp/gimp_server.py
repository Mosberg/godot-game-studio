#!/usr/bin/env python3
"""Godot Game Studio - GIMP MCP server (best effort, batch mode).

GIMP has no stable remote API, so this drives `gimp-console` in batch mode: Script-Fu on GIMP 2.10 and
Python-Fu (python-fu-eval) on GIMP 3. For most pixel-art and texture jobs the `assets` server (Pillow) is faster
and more reliable - use GIMP for XCF files, filters and plug-ins only GIMP has.
"""
from __future__ import annotations

import functools
import re
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import studio_common as sc  # noqa: E402
from studio_common import fail, ok  # noqa: E402

mcp = sc.make_server(
    "gimp",
    "Batch-drive GIMP (gimp-console). Tools: gimp_info, gimp_run_script (Script-Fu on 2.10, Python-Fu on 3.x), "
    "gimp_convert (xcf/psd/png/jpg/webp...), gimp_export_xcf_layers. Prefer the assets server for plain image work.",
)


def safe(fn):
    @functools.wraps(fn)
    def wrapper(*a, **k):
        try:
            return fn(*a, **k)
        except Exception as exc:  # noqa: BLE001
            return fail(f"{type(exc).__name__}: {exc}", trace=traceback.format_exc()[-1000:])
    return wrapper


def gimp_exe() -> str:
    exe = sc.find_gimp()
    if not exe:
        raise FileNotFoundError("GIMP not found. Install GIMP or set GIMP_PATH to gimp-console (e.g. "
                                r"C:\Program Files\GIMP 3\bin\gimp-console-3.0.exe).")
    return exe


def gimp_major(exe: str) -> int:
    res = sc.run([exe, "--version"], timeout=60)
    m = re.search(r"(\d+)\.(\d+)", res["stdout"] + res["stderr"])
    return int(m.group(1)) if m else 2


def run_batch(code: str, language: str, timeout: int) -> dict:
    exe = gimp_exe()
    major = gimp_major(exe)
    lang = language.lower()
    if lang in ("auto", ""):
        lang = "python" if major >= 3 else "scheme"
    if lang == "python":
        cmd = [exe, "-i", "--batch-interpreter=python-fu-eval", "-b", code, "-b", "Gimp.quit(0)" if major >= 3 else "pdb.gimp_quit(1)"]
    else:
        cmd = [exe, "-i", "-b", code, "-b", "(gimp-quit 0)"]
    res = sc.run(cmd, timeout=timeout)
    res["language"] = lang
    res["gimp_major"] = major
    return res


@mcp.tool()
@safe
def gimp_info() -> str:
    """GIMP executable and version; which batch language will be used (Script-Fu on 2.10, Python-Fu on 3.x)."""
    exe = sc.find_gimp()
    if not exe:
        return ok(installed=False, hint="Set GIMP_PATH to gimp-console. The assets server covers most image jobs without GIMP.")
    major = gimp_major(exe)
    return ok(installed=True, executable=exe, major=major, default_language="python" if major >= 3 else "scheme")


@mcp.tool()
@safe
def gimp_run_script(code: str, language: str = "auto", timeout: int = 180) -> str:
    """Run a batch script in GIMP. language: auto | scheme (Script-Fu) | python (Python-Fu, GIMP 3). The code runs in
    one -b expression; for Python wrap multiple statements with exec(\"...\"). Output and errors are returned."""
    res = run_batch(code, language, timeout)
    return ok(success=res["returncode"] == 0, language=res["language"], gimp_major=res["gimp_major"],
              stdout=sc.truncate(res["stdout"], 6000), stderr=sc.truncate(res["stderr"], 3000), timed_out=res["timed_out"])


def _scheme_str(s: str) -> str:
    return '"' + str(Path(s).resolve()).replace("\\", "/").replace('"', '\\"') + '"'


@mcp.tool()
@safe
def gimp_convert(input_path: str, output_path: str, flatten: bool = True, timeout: int = 180) -> str:
    """Open any GIMP-readable file (xcf, psd, png, jpg, webp, ...) and export it as another format (by extension).
    xcf/psd with layers are flattened by default. Useful for xcf -> png before importing into Godot."""
    inp, out = Path(input_path).resolve(), Path(output_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    exe = gimp_exe()
    major = gimp_major(exe)
    if major >= 3:
        py = (
            "import gi; gi.require_version('Gimp','3.0'); from gi.repository import Gimp, Gio; "
            f"img = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(r'{inp}')); "
            + ("img.flatten(); " if flatten else "")
            + f"Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, img, Gio.File.new_for_path(r'{out}'), None)"
        )
        res = run_batch(py, "python", timeout)
    else:
        scm = (
            f"(let* ((image (car (gimp-file-load RUN-NONINTERACTIVE {_scheme_str(str(inp))} {_scheme_str(str(inp))}))) "
            + ("(drawable (car (gimp-image-flatten image)))" if flatten else "(drawable (car (gimp-image-get-active-layer image)))")
            + f") (gimp-file-save RUN-NONINTERACTIVE image drawable {_scheme_str(str(out))} {_scheme_str(str(out))}))"
        )
        res = run_batch(scm, "scheme", timeout)
    if not out.exists():
        return fail("conversion did not produce a file", details=sc.truncate(res["stdout"] + "\n" + res["stderr"], 2500))
    return ok(file=str(out), bytes=out.stat().st_size)


@mcp.tool()
@safe
def gimp_export_xcf_layers(xcf_path: str, output_dir: str, timeout: int = 240) -> str:
    """Export every layer of an .xcf as its own PNG (GIMP 3 / Python-Fu). Handy for UI kits and layered sprites."""
    exe = gimp_exe()
    if gimp_major(exe) < 3:
        return fail("Layer export needs GIMP 3 (Python-Fu). On 2.10 use gimp_run_script with Script-Fu.")
    outdir = Path(output_dir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    py = (
        "import gi; gi.require_version('Gimp','3.0'); from gi.repository import Gimp, Gio; "
        f"img = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(r'{Path(xcf_path).resolve()}')); "
        "layers = img.get_layers(); "
        "[Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, img, Gio.File.new_for_path(r'" + str(outdir) + "/' + "
        "(l.get_name().replace(' ','_')) + '.png'), None) for l in layers]"
    )
    res = run_batch(py, "python", timeout)
    files = sorted(p.name for p in outdir.glob("*.png"))
    return ok(files=files, note="If only one flattened file appears, export per-layer with a custom script via gimp_run_script.",
              stderr=sc.truncate(res["stderr"], 1500)) if files else fail(
        "no layers exported", details=sc.truncate(res["stdout"] + res["stderr"], 2000))


if __name__ == "__main__":
    mcp.run()
