"""Shared helpers for the Godot Game Studio MCP servers.

Standard library only (Pillow is imported lazily where needed) so every
server starts quickly and fails with a readable message when something is
missing.
"""
from __future__ import annotations

import glob
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Iterable, Optional

MAX_OUT = 16000
PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SYSTEM = platform.system()  # Windows / Darwin / Linux


def make_server(name: str, instructions: str = ""):
    """Create an MCP server on both the 1.x (FastMCP) and 2.x (MCPServer) SDKs."""
    try:
        from mcp.server.mcpserver import MCPServer  # mcp >= 2
        return MCPServer(name, instructions=instructions)
    except ImportError:
        pass
    try:
        from mcp.server.fastmcp import FastMCP  # mcp 1.x
        return FastMCP(name, instructions=instructions)
    except ImportError as exc:  # pragma: no cover
        sys.stderr.write(
            "The 'mcp' Python package is missing. Run: pip install -r requirements.txt\n"
        )
        raise SystemExit(1) from exc


# --------------------------------------------------------------------------- #
# generic helpers
# --------------------------------------------------------------------------- #
def truncate(text: str, limit: int = MAX_OUT) -> str:
    if text is None:
        return ""
    if len(text) <= limit:
        return text
    half = limit // 2
    return f"{text[:half]}\n...[truncated {len(text) - limit} chars]...\n{text[-half:]}"


def jdump(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False, default=str)


def ok(**kw: Any) -> str:
    return jdump({"ok": True, **kw})


def fail(message: str, **kw: Any) -> str:
    return jdump({"ok": False, "error": message, **kw})


def scratch_dir(name: str = "studio") -> Path:
    d = Path(tempfile.gettempdir()) / f"godot-game-studio-{name}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def tmp_file(suffix: str, prefix: str = "gs_") -> Path:
    return scratch_dir("tmp") / f"{prefix}{uuid.uuid4().hex[:10]}{suffix}"


def safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_\-]", "_", name).strip("_") or "unnamed"


# --------------------------------------------------------------------------- #
# executable discovery
# --------------------------------------------------------------------------- #
def _expand_globs(patterns: Iterable[str]) -> list[str]:
    out: list[str] = []
    for p in patterns:
        p = os.path.expandvars(os.path.expanduser(p))
        if any(ch in p for ch in "*?["):
            out.extend(sorted(glob.glob(p), reverse=True))
        else:
            out.append(p)
    return out


def find_executable(env_var: str, names: list[str], extra: Optional[list[str]] = None) -> Optional[str]:
    """Locate an executable: env var -> PATH -> well known install folders."""
    configured = os.environ.get(env_var, "").strip().strip('"')
    if configured:
        if os.path.isfile(configured):
            return configured
        found = shutil.which(configured)
        if found:
            return found
    for n in names:
        found = shutil.which(n)
        if found:
            return found
    for cand in _expand_globs(extra or []):
        if os.path.isfile(cand):
            return cand
    return None


GODOT_NAMES = ["godot", "godot4", "Godot", "godot-mono", "Godot_v4"]
GODOT_EXTRA = [
    # Windows
    r"%USERPROFILE%\Godot\Godot_v4*_win64_console.exe",
    r"%USERPROFILE%\Godot\Godot_v4*_win64.exe",
    r"%USERPROFILE%\Downloads\Godot_v4*\Godot_v4*_win64_console.exe",
    r"%USERPROFILE%\Downloads\Godot_v4*\Godot_v4*_win64.exe",
    r"%USERPROFILE%\Desktop\Godot_v4*\Godot_v4*_win64_console.exe",
    r"%LOCALAPPDATA%\Programs\Godot\Godot*.exe",
    r"C:\Godot\Godot_v4*_win64_console.exe",
    r"C:\Godot\Godot_v4*_win64.exe",
    r"C:\Program Files\Godot\Godot*.exe",
    r"C:\Program Files (x86)\Steam\steamapps\common\Godot Engine\godot.windows.editor.x86_64.exe",
    # macOS
    "/Applications/Godot.app/Contents/MacOS/Godot",
    "/Applications/Godot_mono.app/Contents/MacOS/Godot",
    # Linux
    "~/.local/bin/godot",
    "~/Applications/Godot*",
    "/usr/local/bin/godot",
    "/usr/bin/godot",
    "/usr/games/godot",
    "/snap/bin/godot",
]

BLENDER_NAMES = ["blender", "Blender"]
BLENDER_EXTRA = [
    r"C:\Program Files\Blender Foundation\Blender *\blender.exe",
    r"C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe",
    r"%LOCALAPPDATA%\Programs\Blender Foundation\Blender *\blender.exe",
    "/Applications/Blender.app/Contents/MacOS/Blender",
    "/usr/bin/blender",
    "/usr/local/bin/blender",
    "/snap/bin/blender",
    "~/blender*/blender",
]

GIMP_NAMES = ["gimp-console-3.0", "gimp-console-2.10", "gimp-console", "gimp-3.0", "gimp-2.10", "gimp"]
GIMP_EXTRA = [
    r"C:\Program Files\GIMP 3\bin\gimp-console-3*.exe",
    r"C:\Program Files\GIMP 2\bin\gimp-console-2.10.exe",
    r"%LOCALAPPDATA%\Programs\GIMP 3\bin\gimp-console-3*.exe",
    r"%LOCALAPPDATA%\Programs\GIMP 2\bin\gimp-console-2.10.exe",
    "/Applications/GIMP.app/Contents/MacOS/gimp-console",
    "/Applications/GIMP-2.10.app/Contents/MacOS/gimp-console",
    "/usr/bin/gimp-console",
]

FFMPEG_NAMES = ["ffmpeg"]
FFMPEG_EXTRA = [
    r"C:\ffmpeg\bin\ffmpeg.exe",
    r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    r"%LOCALAPPDATA%\Microsoft\WinGet\Links\ffmpeg.exe",
    "/opt/homebrew/bin/ffmpeg",
    "/usr/local/bin/ffmpeg",
    "/usr/bin/ffmpeg",
]


def find_godot() -> Optional[str]:
    return find_executable("GODOT_PATH", GODOT_NAMES, GODOT_EXTRA)


def find_blender() -> Optional[str]:
    return find_executable("BLENDER_PATH", BLENDER_NAMES, BLENDER_EXTRA)


def find_gimp() -> Optional[str]:
    return find_executable("GIMP_PATH", GIMP_NAMES, GIMP_EXTRA)


def find_ffmpeg() -> Optional[str]:
    return find_executable("FFMPEG_PATH", FFMPEG_NAMES, FFMPEG_EXTRA)


# --------------------------------------------------------------------------- #
# subprocess
# --------------------------------------------------------------------------- #
def run(cmd: list[str], timeout: int = 120, cwd: Optional[str] = None,
        env: Optional[dict] = None, stdin: Optional[str] = None) -> dict:
    """Run a command, always returning a dict (never raising)."""
    start = time.time()
    merged = os.environ.copy()
    if env:
        merged.update(env)
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd,
            env=merged, input=stdin, encoding="utf-8", errors="replace",
        )
        return {
            "returncode": proc.returncode,
            "stdout": truncate(proc.stdout),
            "stderr": truncate(proc.stderr),
            "seconds": round(time.time() - start, 2),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        def _s(v: Any) -> str:
            if v is None:
                return ""
            return v.decode("utf-8", "replace") if isinstance(v, bytes) else str(v)
        return {
            "returncode": None,
            "stdout": truncate(_s(exc.stdout)),
            "stderr": truncate(_s(exc.stderr)),
            "seconds": round(time.time() - start, 2),
            "timed_out": True,
        }
    except FileNotFoundError as exc:
        return {"returncode": None, "stdout": "", "stderr": str(exc), "seconds": 0, "timed_out": False}
    except OSError as exc:
        return {"returncode": None, "stdout": "", "stderr": f"OS error: {exc}", "seconds": 0, "timed_out": False}


def spawn_detached(cmd: list[str], cwd: Optional[str] = None, log: Optional[Path] = None) -> int:
    kwargs: dict[str, Any] = {"cwd": cwd, "stdin": subprocess.DEVNULL}
    out = open(log, "ab") if log else subprocess.DEVNULL
    kwargs["stdout"] = out
    kwargs["stderr"] = subprocess.STDOUT
    if SYSTEM == "Windows":
        kwargs["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(cmd, **kwargs)
    return proc.pid


# --------------------------------------------------------------------------- #
# HTTP (stdlib)
# --------------------------------------------------------------------------- #
def http_request(method: str, url: str, payload: Any = None, timeout: int = 30,
                 headers: Optional[dict] = None, raw_body: Optional[bytes] = None) -> tuple[int, bytes]:
    data = raw_body
    hdrs = dict(headers or {})
    if payload is not None and raw_body is None:
        data = json.dumps(payload).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def http_json(method: str, url: str, payload: Any = None, timeout: int = 30) -> Any:
    status, body = http_request(method, url, payload, timeout)
    text = body.decode("utf-8", "replace")
    try:
        parsed = json.loads(text) if text.strip() else {}
    except json.JSONDecodeError:
        parsed = {"raw": text}
    if status >= 400:
        raise RuntimeError(f"HTTP {status} from {url}: {truncate(text, 2000)}")
    return parsed


def multipart_body(fields: dict, files: dict) -> tuple[bytes, str]:
    boundary = "----studio" + uuid.uuid4().hex
    parts: list[bytes] = []
    for k, v in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    for k, (filename, content, ctype) in files.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"; filename="{filename}"\r\n'
            f"Content-Type: {ctype}\r\n\r\n".encode() + content + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


# --------------------------------------------------------------------------- #
# newline-delimited JSON over TCP (Godot editor bridge / Blender bridge)
# --------------------------------------------------------------------------- #
def tcp_json_call(host: str, port: int, payload: dict, timeout: float = 30.0) -> dict:
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
        buf = b""
        while b"\n" not in buf:
            chunk = sock.recv(65536)
            if not chunk:
                break
            buf += chunk
    line = buf.split(b"\n", 1)[0].decode("utf-8", "replace")
    if not line.strip():
        raise RuntimeError("empty response from bridge")
    return json.loads(line)


# --------------------------------------------------------------------------- #
# paths
# --------------------------------------------------------------------------- #
def resolve_dir(path: str, create: bool = False) -> Path:
    p = Path(os.path.expandvars(os.path.expanduser(path))).resolve()
    if create:
        p.mkdir(parents=True, exist_ok=True)
    return p


def default_project_dir() -> Optional[str]:
    env = os.environ.get("GAME_PROJECT_DIR", "").strip()
    return env or None


def python_exe() -> str:
    return sys.executable or "python"
