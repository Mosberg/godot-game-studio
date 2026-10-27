"""Claude Bridge - drive a running Blender from Claude over a local socket.

Install as an add-on (the blender_install_addon MCP tool does this) or run headless:
    blender -b scene.blend --python claude_bridge.py -- --serve [--port 9876]

Protocol: newline-delimited JSON on 127.0.0.1.
    {"cmd": "execute", "args": {"code": "..."}, "token": "..."}  ->  {"ok": true, "result": ...}
Environment: BLENDER_BRIDGE_PORT (default 9876), BLENDER_BRIDGE_TOKEN (optional shared secret).
"""
bl_info = {
    "name": "Claude Bridge",
    "author": "Godot Game Studio",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > Claude",
    "description": "Local socket bridge so Claude can drive Blender live (127.0.0.1 only)",
    "category": "Interface",
}

import contextlib
import io
import json
import os
import queue
import socket
import sys
import threading
import time
import traceback

import bpy

HOST = "127.0.0.1"
DEFAULT_PORT = 9876

_requests: "queue.Queue" = queue.Queue()
_server_thread = None
_server_sock = None
_running = False
_port = DEFAULT_PORT


# --------------------------------------------------------------------------- #
# command handlers (run on Blender's main thread)
# --------------------------------------------------------------------------- #
def _jsonable(value, depth=0):
    if depth > 6:
        return str(value)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v, depth + 1) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v, depth + 1) for k, v in value.items()}
    if hasattr(value, "to_list"):
        try:
            return _jsonable(value.to_list(), depth + 1)
        except Exception:
            pass
    if hasattr(value, "__len__") and hasattr(value, "__getitem__") and not hasattr(value, "keys"):
        try:
            return [_jsonable(v, depth + 1) for v in value]
        except Exception:
            pass
    name = getattr(value, "name", None)
    return f"<{type(value).__name__} {name}>" if name else str(value)


def _cmd_ping(args):
    return {
        "blender": bpy.app.version_string,
        "file": bpy.data.filepath,
        "objects": len(bpy.data.objects),
        "background": bpy.app.background,
        "engine": bpy.context.scene.render.engine,
    }


def _cmd_scene_info(args):
    scene = bpy.context.scene
    objs = []
    for o in scene.objects:
        objs.append({
            "name": o.name, "type": o.type, "parent": o.parent.name if o.parent else None,
            "location": [round(v, 4) for v in o.location],
            "rotation_deg": [round(v * 57.29578, 2) for v in o.rotation_euler],
            "scale": [round(v, 4) for v in o.scale],
            "dimensions": [round(v, 4) for v in o.dimensions],
            "materials": [s.material.name for s in o.material_slots if s.material],
            "modifiers": [m.type for m in o.modifiers],
            "selected": o.select_get() if hasattr(o, "select_get") else False,
            "verts": len(o.data.vertices) if o.type == "MESH" else None,
        })
    return {
        "scene": scene.name, "frame": scene.frame_current,
        "frame_range": [scene.frame_start, scene.frame_end], "fps": scene.render.fps,
        "engine": scene.render.engine,
        "resolution": [scene.render.resolution_x, scene.render.resolution_y],
        "collections": [c.name for c in bpy.data.collections],
        "actions": [a.name for a in bpy.data.actions],
        "active": bpy.context.view_layer.objects.active.name if bpy.context.view_layer.objects.active else None,
        "objects": objs[:300],
    }


def _cmd_execute(args):
    code = args.get("code", "")
    namespace = {"bpy": bpy, "result": None, "__name__": "__claude__"}
    try:
        import bmesh
        import mathutils
        namespace.update(bmesh=bmesh, mathutils=mathutils, Vector=mathutils.Vector,
                         Matrix=mathutils.Matrix, Euler=mathutils.Euler)
    except Exception:
        pass
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exec(compile(code, "<claude>", "exec"), namespace)
    return {"result": _jsonable(namespace.get("result")), "stdout": buf.getvalue()[-6000:]}


def _find_view3d():
    wm = bpy.context.window_manager
    for window in wm.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                for region in area.regions:
                    if region.type == "WINDOW":
                        return window, area, region
    return None


def _cmd_screenshot(args):
    path = os.path.abspath(args.get("path") or os.path.join(bpy.app.tempdir, "claude_view.png"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    scene = bpy.context.scene
    old = (scene.render.filepath, scene.render.resolution_x, scene.render.resolution_y,
           scene.render.resolution_percentage, scene.render.image_settings.file_format)
    scene.render.filepath = path
    scene.render.resolution_x = int(args.get("width", 960))
    scene.render.resolution_y = int(args.get("height", 540))
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    mode = "viewport"
    try:
        found = None if bpy.app.background else _find_view3d()
        if found:
            window, area, region = found
            with bpy.context.temp_override(window=window, area=area, region=region):
                bpy.ops.render.opengl(write_still=True, view_context=True)
        else:
            mode = "workbench"
            prev_engine = scene.render.engine
            scene.render.engine = "BLENDER_WORKBENCH"
            try:
                bpy.ops.render.render(write_still=True)
            finally:
                scene.render.engine = prev_engine
    finally:
        (scene.render.filepath, scene.render.resolution_x, scene.render.resolution_y,
         scene.render.resolution_percentage, scene.render.image_settings.file_format) = old
    return {"path": path, "mode": mode}


def _pick_engine(name):
    items = [i.identifier for i in bpy.context.scene.render.bl_rna.properties["engine"].enum_items]
    name = (name or "").upper()
    if name in ("EEVEE", "BLENDER_EEVEE"):
        for cand in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
            if cand in items:
                return cand
    if name in items:
        return name
    if name == "WORKBENCH":
        return "BLENDER_WORKBENCH"
    return bpy.context.scene.render.engine


def _cmd_render(args):
    path = os.path.abspath(args["path"])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    scene = bpy.context.scene
    if args.get("engine"):
        scene.render.engine = _pick_engine(args["engine"])
    if scene.render.engine == "CYCLES" and args.get("samples"):
        scene.cycles.samples = int(args["samples"])
    if args.get("width"):
        scene.render.resolution_x = int(args["width"])
    if args.get("height"):
        scene.render.resolution_y = int(args["height"])
    scene.render.filepath = path
    scene.render.image_settings.file_format = "PNG"
    if args.get("transparent"):
        scene.render.film_transparent = True
        scene.render.image_settings.color_mode = "RGBA"
    if args.get("frame") is not None:
        scene.frame_set(int(args["frame"]))
    bpy.ops.render.render(write_still=True)
    return {"path": path, "engine": scene.render.engine}


def _cmd_export(args):
    path = os.path.abspath(args["path"])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sel = bool(args.get("selected_only", False))
    ext = os.path.splitext(path)[1].lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.export_scene.gltf(filepath=path, export_format="GLB" if ext == ".glb" else "GLTF_SEPARATE",
                                  use_selection=sel, export_apply=True, export_yup=True,
                                  export_animations=bool(args.get("animations", True)))
    elif ext == ".fbx":
        bpy.ops.export_scene.fbx(filepath=path, use_selection=sel, apply_scale_options="FBX_SCALE_ALL")
    elif ext == ".obj":
        if hasattr(bpy.ops.wm, "obj_export"):
            bpy.ops.wm.obj_export(filepath=path, export_selected_objects=sel)
        else:
            bpy.ops.export_scene.obj(filepath=path, use_selection=sel)
    else:
        raise ValueError("export extension must be .glb/.gltf/.fbx/.obj")
    return {"path": path, "bytes": os.path.getsize(path) if os.path.exists(path) else 0}


def _cmd_import(args):
    path = os.path.abspath(args["path"])
    ext = os.path.splitext(path)[1].lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    elif ext == ".obj":
        if hasattr(bpy.ops.wm, "obj_import"):
            bpy.ops.wm.obj_import(filepath=path)
        else:
            bpy.ops.import_scene.obj(filepath=path)
    else:
        raise ValueError("import extension must be .glb/.gltf/.fbx/.obj")
    return {"imported": path, "objects": len(bpy.data.objects)}


def _cmd_save(args):
    if args.get("path"):
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args["path"]))
    else:
        bpy.ops.wm.save_mainfile()
    return {"file": bpy.data.filepath}


def _cmd_open(args):
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(args["path"]))
    return {"file": bpy.data.filepath}


HANDLERS = {
    "ping": _cmd_ping, "scene_info": _cmd_scene_info, "execute": _cmd_execute,
    "screenshot": _cmd_screenshot, "render": _cmd_render, "export": _cmd_export,
    "import": _cmd_import, "save": _cmd_save, "open": _cmd_open,
}


def _run_request(req):
    token = os.environ.get("BLENDER_BRIDGE_TOKEN", "")
    if token and req.get("token") != token:
        return {"ok": False, "error": "bad or missing token"}
    cmd = req.get("cmd", "")
    handler = HANDLERS.get(cmd)
    if handler is None:
        return {"ok": False, "error": f"unknown command '{cmd}'. Available: {sorted(HANDLERS)}"}
    try:
        return {"ok": True, "result": _jsonable(handler(req.get("args") or {}))}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "trace": traceback.format_exc()[-1500:]}


def _process_queue():
    """Runs on the main thread (timer or manual loop)."""
    deadline = time.time() + 0.2
    while time.time() < deadline:
        try:
            req, done, holder = _requests.get_nowait()
        except queue.Empty:
            break
        holder["response"] = _run_request(req)
        done.set()
    return 0.05 if _running else None


# --------------------------------------------------------------------------- #
# socket server (background thread)
# --------------------------------------------------------------------------- #
def _client_loop(conn):
    conn.settimeout(300)
    buf = b""
    try:
        while _running:
            chunk = conn.recv(65536)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if not line.strip():
                    continue
                try:
                    req = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError:
                    resp = {"ok": False, "error": "invalid JSON"}
                else:
                    done, holder = threading.Event(), {}
                    _requests.put((req, done, holder))
                    if done.wait(timeout=float(req.get("timeout", 280))):
                        resp = holder["response"]
                    else:
                        resp = {"ok": False, "error": "timed out waiting for Blender's main thread"}
                conn.sendall((json.dumps(resp, default=str) + "\n").encode("utf-8"))
    except (OSError, socket.timeout):
        pass
    finally:
        conn.close()


def _accept_loop():
    global _server_sock
    while _running:
        try:
            conn, _addr = _server_sock.accept()
        except OSError:
            break
        threading.Thread(target=_client_loop, args=(conn,), daemon=True).start()


def start_server(port=None):
    global _server_thread, _server_sock, _running, _port
    if _running:
        return _port
    _port = int(port or os.environ.get("BLENDER_BRIDGE_PORT") or DEFAULT_PORT)
    _server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    _server_sock.bind((HOST, _port))
    _server_sock.listen(5)
    _running = True
    _server_thread = threading.Thread(target=_accept_loop, daemon=True)
    _server_thread.start()
    if not bpy.app.background:
        bpy.app.timers.register(_process_queue, first_interval=0.1, persistent=True)
    print(f"[Claude Bridge] listening on {HOST}:{_port}")
    return _port


def stop_server():
    global _running, _server_sock
    _running = False
    if _server_sock:
        try:
            _server_sock.close()
        except OSError:
            pass
        _server_sock = None
    print("[Claude Bridge] stopped")


def serve_forever(port=None):
    """Headless mode: there is no UI event loop, so pump the queue ourselves."""
    start_server(port)
    try:
        while _running:
            _process_queue()
            time.sleep(0.02)
    except KeyboardInterrupt:
        stop_server()


# --------------------------------------------------------------------------- #
# UI
# --------------------------------------------------------------------------- #
class CLAUDE_OT_toggle_server(bpy.types.Operator):
    bl_idname = "claude.toggle_server"
    bl_label = "Toggle Claude Bridge"

    def execute(self, context):
        if _running:
            stop_server()
        else:
            start_server()
        return {"FINISHED"}


class CLAUDE_PT_panel(bpy.types.Panel):
    bl_label = "Claude Bridge"
    bl_idname = "CLAUDE_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Claude"

    def draw(self, context):
        layout = self.layout
        layout.label(text=f"{'Listening' if _running else 'Stopped'} on {HOST}:{_port}")
        layout.operator("claude.toggle_server", text="Stop" if _running else "Start")


_classes = (CLAUDE_OT_toggle_server, CLAUDE_PT_panel)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.app.timers.register(lambda: (start_server(), None)[1], first_interval=0.5)


def unregister():
    stop_server()
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--serve" in argv:
        port = None
        if "--port" in argv:
            port = int(argv[argv.index("--port") + 1])
        serve_forever(port)
    else:
        register()
