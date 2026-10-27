"""Godot 4 file-format library: project.godot, .tscn/.tres writing, parsing, validation.

No Godot binary is needed for anything in this module, so it is fast and testable.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any, Optional

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = PLUGIN_ROOT / "templates"
ADDON_DIR = PLUGIN_ROOT / "godot_addon"

# --------------------------------------------------------------------------- #
# low level scanning
# --------------------------------------------------------------------------- #


def _scan(text: str, depth: int = 0, in_str: bool = False, esc: bool = False) -> tuple[int, bool, bool]:
    """Track bracket depth / string state across (possibly multi-line) Godot values."""
    for ch in text:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
    return depth, in_str, esc


_BARE = re.compile(r"^-?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?$|^(true|false|null)$|^-?inf$|^nan$")
_LITERAL_PREFIXES = (
    '"', "&\"", "^\"", "[", "{", "(", "Vector", "Color", "Rect", "Transform", "Basis", "Quaternion",
    "Plane", "AABB", "Projection", "Packed", "Array", "Dictionary", "Object(", "NodePath(",
    "ExtResource(", "SubResource(", "StringName(", "RID(", "Callable(", "Signal(", "Resource(",
)


def to_literal(value: Any) -> str:
    """Convert a Python value into Godot text-format syntax.

    * bool/int/float -> as is
    * list/tuple -> [a, b]
    * dict -> {"k": v}
    * str that already looks like a Godot literal (Vector2(1, 2), "text", 12, true, [..], ...)
      is kept verbatim; any other plain string is quoted."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(to_literal(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{to_literal(k)}: {to_literal(v)}" for k, v in value.items()) + "}"
    s = str(value)
    stripped = s.strip()
    if _BARE.match(stripped) or stripped.startswith(_LITERAL_PREFIXES):
        return stripped
    return json.dumps(s, ensure_ascii=False)


# --------------------------------------------------------------------------- #
# project.godot
# --------------------------------------------------------------------------- #
_SECTION_RE = re.compile(r"^\[([^\]]+)\]\s*$")
_ENTRY_RE = re.compile(r"^([A-Za-z0-9_./\-]+)=(.*)$")


def parse_project(text: str) -> list[tuple]:
    items: list[tuple] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _SECTION_RE.match(line)
        if m:
            items.append(("section", m.group(1), line))
            i += 1
            continue
        m = _ENTRY_RE.match(line)
        if m:
            entry = [line]
            depth, in_str, esc = _scan(m.group(2))
            while (depth > 0 or in_str) and i + 1 < len(lines):
                i += 1
                entry.append(lines[i])
                depth, in_str, esc = _scan(lines[i], depth, in_str, esc)
            items.append(("entry", m.group(1), entry))
            i += 1
            continue
        items.append(("raw", line))
        i += 1
    return items


def render_project(items: list[tuple]) -> str:
    out: list[str] = []
    for it in items:
        if it[0] == "section":
            out.append(it[2])
        elif it[0] == "entry":
            out.extend(it[2])
        else:
            out.append(it[1])
    return "\n".join(out).rstrip("\n") + "\n"


def project_settings(text: str) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {"": {}}
    section = ""
    for it in parse_project(text):
        if it[0] == "section":
            section = it[1]
            result.setdefault(section, {})
        elif it[0] == "entry":
            first = it[2][0]
            value = first.split("=", 1)[1]
            if len(it[2]) > 1:
                value = "\n".join([value] + it[2][1:])
            result.setdefault(section, {})[it[1]] = value
    return result


def split_setting_path(path: str) -> tuple[str, str]:
    path = path.strip().strip("/")
    if "/" not in path:
        return "", path
    section, key = path.split("/", 1)
    return section, key


def set_project_setting(text: str, section: str, key: str, raw_value: str) -> str:
    items = parse_project(text)
    new_entry = ("entry", key, f"{key}={raw_value}".split("\n"))
    # locate section bounds
    start = -1 if section == "" else None
    if section != "":
        for idx, it in enumerate(items):
            if it[0] == "section" and it[1] == section:
                start = idx
                break
    if start is None:  # section missing -> append
        if items and not (items[-1][0] == "raw" and items[-1][1].strip() == ""):
            items.append(("raw", ""))
        items.append(("section", section, f"[{section}]"))
        items.append(("raw", ""))
        items.append(new_entry)
        return render_project(items)
    end = len(items)
    for idx in range(start + 1, len(items)):
        if items[idx][0] == "section":
            end = idx
            break
    for idx in range(start + 1, end):
        if items[idx][0] == "entry" and items[idx][1] == key:
            items[idx] = new_entry
            return render_project(items)
    # insert after the last non-blank item of the section
    insert_at = start + 1
    for idx in range(start + 1, end):
        it = items[idx]
        if not (it[0] == "raw" and it[1].strip() == ""):
            insert_at = idx + 1
    if section != "" and insert_at == start + 1:
        items.insert(insert_at, ("raw", ""))
        insert_at += 1
    items.insert(insert_at, new_entry)
    if section == "" and end < len(items) and items[insert_at + 1][0] != "raw":
        items.insert(insert_at + 1, ("raw", ""))
    return render_project(items)


def remove_project_setting(text: str, section: str, key: str) -> tuple[str, bool]:
    items = parse_project(text)
    cur = ""
    for idx, it in enumerate(items):
        if it[0] == "section":
            cur = it[1]
        elif it[0] == "entry" and cur == section and it[1] == key:
            del items[idx]
            return render_project(items), True
    return text, False


# --------------------------------------------------------------------------- #
# input actions
# --------------------------------------------------------------------------- #
_SPECIAL_KEYS = {
    "escape": 4194305, "esc": 4194305, "tab": 4194306, "backspace": 4194308, "enter": 4194309,
    "return": 4194309, "kp_enter": 4194310, "insert": 4194311, "delete": 4194312, "home": 4194317,
    "end": 4194318, "left": 4194319, "up": 4194320, "right": 4194321, "down": 4194322,
    "pageup": 4194323, "pagedown": 4194324, "shift": 4194325, "ctrl": 4194326, "control": 4194326,
    "meta": 4194327, "alt": 4194328, "capslock": 4194329, "space": 32,
}
for _n in range(1, 13):
    _SPECIAL_KEYS[f"f{_n}"] = 4194331 + _n

_MOUSE = {"left": 1, "right": 2, "middle": 3, "wheel_up": 4, "wheel_down": 5, "back": 8, "forward": 9}

_KEY_EVENT = ('Object(InputEventKey,"resource_local_to_scene":false,"resource_name":"","device":-1,'
              '"window_id":0,"alt_pressed":false,"shift_pressed":false,"ctrl_pressed":false,'
              '"meta_pressed":false,"pressed":false,"keycode":0,"physical_keycode":{code},"key_label":0,'
              '"unicode":0,"location":0,"echo":false,"script":null)')
_MOUSE_EVENT = ('Object(InputEventMouseButton,"resource_local_to_scene":false,"resource_name":"",'
                '"device":-1,"window_id":0,"alt_pressed":false,"shift_pressed":false,"ctrl_pressed":false,'
                '"meta_pressed":false,"button_mask":{mask},"position":Vector2(0, 0),'
                '"global_position":Vector2(0, 0),"factor":1.0,"button_index":{idx},"canceled":false,'
                '"pressed":true,"double_click":false,"script":null)')
_JOY_BUTTON = ('Object(InputEventJoypadButton,"resource_local_to_scene":false,"resource_name":"",'
               '"device":-1,"button_index":{idx},"pressure":0.0,"pressed":true,"script":null)')
_JOY_AXIS = ('Object(InputEventJoypadMotion,"resource_local_to_scene":false,"resource_name":"",'
             '"device":-1,"axis":{axis},"axis_value":{value},"script":null)')


def input_event(token: str) -> str:
    """token examples: 'key:A', 'key:Space', 'mouse:left', 'joy_button:0', 'joy_axis:0:-1'."""
    kind, _, rest = token.strip().partition(":")
    kind = kind.lower()
    if kind == "key":
        name = rest.strip()
        low = name.lower()
        if low in _SPECIAL_KEYS:
            code = _SPECIAL_KEYS[low]
        elif len(name) == 1:
            code = ord(name.upper())
        else:
            raise ValueError(f"unknown key '{name}'")
        return _KEY_EVENT.format(code=code)
    if kind == "mouse":
        idx = _MOUSE[rest.strip().lower()]
        return _MOUSE_EVENT.format(idx=idx, mask=1 << (idx - 1) if idx < 4 else 0)
    if kind == "joy_button":
        return _JOY_BUTTON.format(idx=int(rest))
    if kind == "joy_axis":
        axis, _, value = rest.partition(":")
        return _JOY_AXIS.format(axis=int(axis), value=float(value or 1.0))
    raise ValueError(f"bad input token '{token}' (use key:, mouse:, joy_button:, joy_axis:)")


def input_action_value(tokens: list[str], deadzone: float = 0.2) -> str:
    events = ",\n".join(input_event(t) for t in tokens)
    return '{\n"deadzone": %s,\n"events": [%s\n]\n}' % (deadzone, events and "\n" + events if events else "")


# --------------------------------------------------------------------------- #
# tscn / tres blocks
# --------------------------------------------------------------------------- #
_ATTR_RE = re.compile(r'(\w+)=("(?:[^"\\]|\\.)*"|\[[^\]]*\]|\w+\("[^"]*"\)|[^\s\]]+)')
_PROP_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_/\.:]*) = (.*)$")

EXT_TYPES = {
    ".png": "Texture2D", ".jpg": "Texture2D", ".jpeg": "Texture2D", ".webp": "Texture2D",
    ".svg": "Texture2D", ".bmp": "Texture2D", ".tga": "Texture2D", ".exr": "Texture2D",
    ".hdr": "Texture2D", ".tscn": "PackedScene", ".scn": "PackedScene", ".glb": "PackedScene",
    ".gltf": "PackedScene", ".fbx": "PackedScene", ".obj": "ArrayMesh", ".gd": "Script",
    ".cs": "Script", ".tres": "Resource", ".res": "Resource", ".ogg": "AudioStream",
    ".wav": "AudioStream", ".mp3": "AudioStream", ".ttf": "FontFile", ".otf": "FontFile",
    ".woff2": "FontFile", ".shader": "Shader", ".gdshader": "Shader", ".ogv": "VideoStream",
}


def _unquote(s: str) -> str:
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            return s[1:-1]
    return s


def parse_blocks(text: str) -> list[dict]:
    blocks: list[dict] = []
    cur: Optional[dict] = None
    depth, in_str, esc = 0, False, False
    for line in text.splitlines():
        if depth == 0 and not in_str and line.startswith("[") and line.rstrip().endswith("]"):
            hm = re.match(r"^\[(\w+)(.*)\]\s*$", line)
            if hm:
                cur = {"kind": hm.group(1), "header": line.rstrip(),
                       "attrs": {k: _unquote(v) for k, v in _ATTR_RE.findall(hm.group(2))}, "body": []}
                blocks.append(cur)
                continue
        if cur is None:
            continue
        cur["body"].append(line)
        if depth or in_str or _PROP_RE.match(line):
            depth, in_str, esc = _scan(line, depth, in_str, esc)
        else:
            depth, in_str, esc = 0, False, False
    for b in blocks:
        while b["body"] and not b["body"][-1].strip():
            b["body"].pop()
    return blocks


def render_blocks(blocks: list[dict]) -> str:
    out: list[str] = []
    for i, b in enumerate(blocks):
        out.append(b["header"])
        out.extend(b["body"])
        nxt = blocks[i + 1]["kind"] if i + 1 < len(blocks) else None
        # Godot keeps consecutive ext_resource lines together, everything else is blank-line separated
        if not (b["kind"] == "ext_resource" and nxt == "ext_resource"):
            out.append("")
    return "\n".join(out).rstrip("\n") + "\n"


def block_properties(block: dict) -> dict[str, str]:
    props: dict[str, str] = {}
    key: Optional[str] = None
    parts: list[str] = []
    depth, in_str, esc = 0, False, False
    for line in block["body"]:
        if key is None:
            m = _PROP_RE.match(line)
            if not m:
                continue
            key, parts = m.group(1), [m.group(2)]
            depth, in_str, esc = _scan(m.group(2))
        else:
            parts.append(line)
            depth, in_str, esc = _scan(line, depth, in_str, esc)
        if depth <= 0 and not in_str:
            props[key] = "\n".join(parts)
            key = None
    return props


def node_path(block: dict) -> str:
    a = block["attrs"]
    parent = a.get("parent")
    if parent is None:
        return "."
    return a["name"] if parent == "." else f"{parent}/{a['name']}"


def _header(kind: str, attrs: list[tuple[str, str]]) -> str:
    inner = " ".join(f'{k}={v}' for k, v in attrs)
    return f"[{kind} {inner}]" if inner else f"[{kind}]"


def _q(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


class SceneBuilder:
    """Accumulates ext/sub resources while converting a JSON-ish spec to text blocks."""

    def __init__(self, existing: Optional[list[dict]] = None):
        self.ext: dict[str, dict] = {}      # path -> block
        self.ext_ids: set[str] = set()
        self.sub_ids: set[str] = set()
        self.new_ext: list[dict] = []
        self.new_sub: list[dict] = []
        for b in existing or []:
            if b["kind"] == "ext_resource":
                self.ext[b["attrs"].get("path", "")] = b
                self.ext_ids.add(b["attrs"].get("id", ""))
            elif b["kind"] == "sub_resource":
                self.sub_ids.add(b["attrs"].get("id", ""))
        self._counter = 0

    def _fresh_id(self, prefix: str, taken: set[str]) -> str:
        while True:
            self._counter += 1
            cand = f"{self._counter}_{prefix}"
            if cand not in taken:
                return cand

    def ext_resource(self, path: str, rtype: Optional[str] = None, explicit_id: Optional[str] = None) -> str:
        if path in self.ext:
            return self.ext[path]["attrs"]["id"]
        rtype = rtype or EXT_TYPES.get(Path(path).suffix.lower(), "Resource")
        rid = explicit_id or self._fresh_id(re.sub(r"\W", "", Path(path).stem)[:6] or "res", self.ext_ids)
        block = {"kind": "ext_resource",
                 "header": _header("ext_resource", [("type", _q(rtype)), ("path", _q(path)), ("id", _q(rid))]),
                 "attrs": {"type": rtype, "path": path, "id": rid}, "body": []}
        self.ext[path] = block
        self.ext_ids.add(rid)
        self.new_ext.append(block)
        return rid

    def value(self, v: Any) -> str:
        """Convert a property value, resolving res:// paths and @subresource shortcuts."""
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("res://") and not s.startswith('"'):
                return f'ExtResource("{self.ext_resource(s)}")'
            if s.startswith("@") and re.fullmatch(r"@[A-Za-z0-9_\-]+", s):
                return f'SubResource("{s[1:]}")'
        if isinstance(v, list):
            return "[" + ", ".join(self.value(x) for x in v) + "]"
        return to_literal(v)

    def props_lines(self, props: dict[str, Any]) -> list[str]:
        return [f"{k} = {self.value(val)}" for k, val in props.items()]

    def sub_resource(self, spec: dict) -> None:
        sid = spec.get("id") or self._fresh_id(spec["type"], self.sub_ids)
        self.sub_ids.add(sid)
        self.new_sub.append({
            "kind": "sub_resource",
            "header": _header("sub_resource", [("type", _q(spec["type"])), ("id", _q(sid))]),
            "attrs": {"type": spec["type"], "id": sid},
            "body": self.props_lines(spec.get("properties", {})),
        })

    def node(self, spec: dict, is_root: bool = False) -> dict:
        attrs: list[tuple[str, str]] = [("name", _q(spec["name"]))]
        if spec.get("type") and not spec.get("instance"):
            attrs.append(("type", _q(spec["type"])))
        if not is_root:
            attrs.append(("parent", _q(spec.get("parent", "."))))
        if spec.get("instance"):
            rid = self.ext_resource(spec["instance"], "PackedScene")
            attrs.append(("instance", f'ExtResource("{rid}")'))
        if spec.get("groups"):
            attrs.append(("groups", "[" + ", ".join(f'&{_q(g)}' for g in spec["groups"]) + "]"))
        props = dict(spec.get("properties", {}))
        body = []
        if spec.get("script"):
            rid = self.ext_resource(spec["script"], "Script")
            body.append(f'script = ExtResource("{rid}")')
        body.extend(self.props_lines(props))
        parsed_attrs = {"name": spec["name"], "type": spec.get("type", "")}
        if not is_root:
            parsed_attrs["parent"] = spec.get("parent", ".")
        return {"kind": "node", "header": _header("node", attrs), "attrs": parsed_attrs, "body": body}

    def connection(self, spec: dict) -> dict:
        attrs = [("signal", _q(spec["signal"])), ("from", _q(spec.get("from", "."))),
                 ("to", _q(spec.get("to", "."))), ("method", _q(spec["method"]))]
        if spec.get("flags"):
            attrs.append(("flags", str(int(spec["flags"]))))
        return {"kind": "connection", "header": _header("connection", attrs),
                "attrs": {k: _unquote(v) for k, v in attrs}, "body": []}


def _fix_load_steps(blocks: list[dict]) -> None:
    head = blocks[0]
    if "load_steps" not in head["header"]:
        return
    steps = 1 + sum(1 for b in blocks if b["kind"] in ("ext_resource", "sub_resource"))
    head["header"] = re.sub(r"load_steps=\d+", f"load_steps={steps}", head["header"])
    head["attrs"]["load_steps"] = str(steps)


def build_scene(spec: dict) -> str:
    """spec = {root: {name,type,script?,properties?}, nodes: [...], ext_resources: [...],
    sub_resources: [...], connections: [...]}"""
    sb = SceneBuilder()
    for er in spec.get("ext_resources", []):
        sb.ext_resource(er["path"], er.get("type"), er.get("id"))
    for sr in spec.get("sub_resources", []):
        sb.sub_resource(sr)
    root = sb.node(spec["root"], is_root=True)
    nodes = [sb.node(n) for n in spec.get("nodes", [])]
    conns = [sb.connection(c) for c in spec.get("connections", [])]
    blocks = [{"kind": "gd_scene", "header": "[gd_scene format=3]", "attrs": {}, "body": []}]
    blocks += sb.new_ext + sb.new_sub + [root] + nodes + conns
    blocks[0]["header"] = f"[gd_scene load_steps={1 + len(sb.new_ext) + len(sb.new_sub)} format=3]"
    return render_blocks(blocks)


def build_resource(rtype: str, properties: dict, sub_resources: Optional[list] = None,
                   script: Optional[str] = None) -> str:
    sb = SceneBuilder()
    for sr in sub_resources or []:
        sb.sub_resource(sr)
    body = []
    if script:
        body.append(f'script = ExtResource("{sb.ext_resource(script, "Script")}")')
    body += sb.props_lines(properties)
    steps = 1 + len(sb.new_ext) + len(sb.new_sub)
    head = {"kind": "gd_resource", "header": f'[gd_resource type={_q(rtype)} load_steps={steps} format=3]',
            "attrs": {}, "body": []}
    res = {"kind": "resource", "header": "[resource]", "attrs": {}, "body": body}
    return render_blocks([head] + sb.new_ext + sb.new_sub + [res])


def parse_scene(text: str) -> dict:
    blocks = parse_blocks(text)
    result: dict[str, Any] = {"ext_resources": [], "sub_resources": [], "nodes": [], "connections": []}
    for b in blocks:
        a = b["attrs"]
        if b["kind"] == "ext_resource":
            result["ext_resources"].append({"id": a.get("id"), "type": a.get("type"), "path": a.get("path")})
        elif b["kind"] == "sub_resource":
            result["sub_resources"].append({"id": a.get("id"), "type": a.get("type"),
                                            "properties": block_properties(b)})
        elif b["kind"] == "node":
            result["nodes"].append({"name": a.get("name"), "type": a.get("type"), "parent": a.get("parent"),
                                    "path": node_path(b), "instance": a.get("instance"),
                                    "groups": a.get("groups"), "properties": block_properties(b)})
        elif b["kind"] == "connection":
            result["connections"].append(dict(a))
    return result


def scene_tree_text(text: str) -> str:
    parsed = parse_scene(text)
    ext = {e["id"]: e for e in parsed["ext_resources"]}
    lines: list[str] = []
    for n in parsed["nodes"]:
        depth = 0 if n["parent"] is None else (1 if n["parent"] == "." else n["parent"].count("/") + 2)
        extra = []
        script = n["properties"].get("script")
        if script:
            m = re.search(r'ExtResource\("([^"]+)"\)', script)
            if m and m.group(1) in ext:
                extra.append(f"script={ext[m.group(1)]['path']}")
        if n["instance"]:
            m = re.search(r'ExtResource\("([^"]+)"\)', n["instance"])
            if m and m.group(1) in ext:
                extra.append(f"instance={ext[m.group(1)]['path']}")
        kind = n["type"] or "(instance)"
        lines.append("  " * depth + f"{n['name']} [{kind}]" + (" " + " ".join(extra) if extra else ""))
    return "\n".join(lines)


def add_to_scene(text: str, spec: dict) -> str:
    """spec keys: nodes, sub_resources, ext_resources, connections (same shape as build_scene)."""
    blocks = parse_blocks(text)
    if not blocks or blocks[0]["kind"] not in ("gd_scene", "gd_resource"):
        raise ValueError("not a Godot scene/resource file")
    sb = SceneBuilder(blocks)
    for er in spec.get("ext_resources", []):
        sb.ext_resource(er["path"], er.get("type"), er.get("id"))
    for sr in spec.get("sub_resources", []):
        sb.sub_resource(sr)
    new_nodes = [sb.node(n) for n in spec.get("nodes", [])]
    new_conns = [sb.connection(c) for c in spec.get("connections", [])]

    def last_index(kinds: tuple[str, ...]) -> int:
        idx = -1
        for i, b in enumerate(blocks):
            if b["kind"] in kinds:
                idx = i
        return idx

    # existing node paths: validate parents
    existing_paths = {node_path(b) for b in blocks if b["kind"] == "node"}
    for nb in new_nodes:
        parent = nb["attrs"].get("parent")
        if parent is not None and parent not in existing_paths:
            raise ValueError(f"parent '{parent}' does not exist in the scene (create parents first)")
        existing_paths.add(node_path(nb))
    ins = last_index(("gd_scene", "ext_resource"))
    blocks[ins + 1:ins + 1] = sb.new_ext
    ins = last_index(("gd_scene", "ext_resource", "sub_resource"))
    blocks[ins + 1:ins + 1] = sb.new_sub
    ins = last_index(("node",))
    if ins < 0:
        ins = last_index(("gd_scene", "ext_resource", "sub_resource"))
    blocks[ins + 1:ins + 1] = new_nodes
    ins = last_index(("connection", "node"))
    blocks[ins + 1:ins + 1] = new_conns
    _fix_load_steps(blocks)
    return render_blocks(blocks)


def set_node_property(text: str, path: str, prop: str, value: Any) -> str:
    blocks = parse_blocks(text)
    sb = SceneBuilder(blocks)
    target = None
    for b in blocks:
        if b["kind"] == "node" and node_path(b) == path:
            target = b
            break
    if target is None:
        raise ValueError(f"node '{path}' not found")
    line = f"{prop} = {sb.value(value)}"
    replaced = False
    i = 0
    body = target["body"]
    while i < len(body):
        m = _PROP_RE.match(body[i])
        if m and m.group(1) == prop:
            depth, in_str, esc = _scan(m.group(2))
            j = i
            while (depth > 0 or in_str) and j + 1 < len(body):
                j += 1
                depth, in_str, esc = _scan(body[j], depth, in_str, esc)
            body[i:j + 1] = [line]
            replaced = True
            break
        i += 1
    if not replaced:
        body.append(line)
    if sb.new_ext:
        idx = max((i for i, b in enumerate(blocks) if b["kind"] in ("gd_scene", "ext_resource")), default=0)
        blocks[idx + 1:idx + 1] = sb.new_ext
        _fix_load_steps(blocks)
    return render_blocks(blocks)


def remove_node(text: str, path: str) -> str:
    blocks = parse_blocks(text)
    if path == ".":
        raise ValueError("cannot remove the root node")
    doomed = {path}
    keep = []
    for b in blocks:
        if b["kind"] == "node":
            np_ = node_path(b)
            parent = b["attrs"].get("parent")
            if np_ == path or (parent is not None and (parent in doomed or any(parent.startswith(d + "/") for d in doomed))):
                doomed.add(np_)
                continue
        keep.append(b)
    keep = [b for b in keep if not (b["kind"] == "connection" and (
        b["attrs"].get("from") in doomed or b["attrs"].get("to") in doomed))]
    return render_blocks(keep)


# --------------------------------------------------------------------------- #
# validation
# --------------------------------------------------------------------------- #
def find_project_root(start: Path) -> Optional[Path]:
    p = start if start.is_dir() else start.parent
    for cand in [p, *p.parents]:
        if (cand / "project.godot").is_file():
            return cand
    return None


def res_to_fs(res_path: str, root: Path) -> Path:
    return root / res_path.replace("res://", "", 1)


def validate_scene_text(text: str, root: Optional[Path] = None) -> list[str]:
    problems: list[str] = []
    stripped = text.lstrip()
    if not (stripped.startswith("[gd_scene") or stripped.startswith("[gd_resource")):
        return ["file does not start with [gd_scene ...] or [gd_resource ...]"]
    blocks = parse_blocks(text)
    ext_ids: dict[str, str] = {}
    sub_ids: set[str] = set()
    for b in blocks:
        if b["kind"] == "ext_resource":
            rid = b["attrs"].get("id")
            if rid in ext_ids:
                problems.append(f"duplicate ext_resource id '{rid}'")
            ext_ids[rid] = b["attrs"].get("path", "")
            if root and ext_ids[rid].startswith("res://") and not res_to_fs(ext_ids[rid], root).exists():
                problems.append(f"ext_resource '{rid}' points to missing file {ext_ids[rid]}")
        elif b["kind"] == "sub_resource":
            sid = b["attrs"].get("id")
            if sid in sub_ids:
                problems.append(f"duplicate sub_resource id '{sid}'")
            sub_ids.add(sid)
    paths: set[str] = set()
    sibling: set[tuple[str, str]] = set()
    nodes = [b for b in blocks if b["kind"] == "node"]
    if stripped.startswith("[gd_scene"):
        if not nodes:
            problems.append("scene has no nodes")
        else:
            if "parent" in nodes[0]["attrs"]:
                problems.append("first node must be the root (no parent attribute)")
            roots = [n for n in nodes if "parent" not in n["attrs"]]
            if len(roots) > 1:
                problems.append(f"{len(roots)} root nodes found (only one allowed)")
    for b in blocks:
        if b["kind"] == "node":
            a = b["attrs"]
            parent = a.get("parent")
            p = node_path(b)
            if parent is not None and parent != "." and parent not in paths:
                problems.append(f"node '{p}': parent '{parent}' is declared later or missing (parents must come first)")
            key = (parent or "", a.get("name", ""))
            if key in sibling:
                problems.append(f"duplicate node name '{a.get('name')}' under '{parent}'")
            sibling.add(key)
            paths.add(p)
        elif b["kind"] == "connection":
            for end in ("from", "to"):
                v = b["attrs"].get(end)
                if v is not None and v != "." and v not in paths:
                    problems.append(f"connection {b['attrs'].get('signal')}: '{end}' node '{v}' not found")
    ref_re = re.compile(r'(ExtResource|SubResource)\("([^"]+)"\)')
    for b in blocks:
        text_blob = b["header"] + "\n" + "\n".join(b["body"])
        for kind, rid in ref_re.findall(text_blob):
            if kind == "ExtResource" and rid not in ext_ids:
                problems.append(f"{b['kind']} references missing ExtResource id '{rid}'")
            if kind == "SubResource" and rid not in sub_ids:
                problems.append(f"{b['kind']} references missing SubResource id '{rid}'")
    return problems


_GD3_PATTERNS = [
    (r"^\s*onready\s+var\b", "Godot 3 syntax 'onready var' -> use '@onready var'"),
    (r"^\s*export\s*(\(|var\b)", "Godot 3 syntax 'export' -> use '@export var'"),
    (r"^\s*tool\s*$", "Godot 3 'tool' -> use '@tool' on the first line"),
    (r"\byield\s*\(", "'yield' was removed -> use 'await'"),
    (r"\bsetget\b", "'setget' was removed -> use property setters: var x: int: set(v): ..."),
    (r"^\s*(remote|puppet|master|slave|sync|remotesync|mastersync|puppetsync)\s+(func|var)\b",
     "Godot 3 network keywords -> use @rpc"),
    (r"\b(KinematicBody2D|KinematicBody|Spatial|ViewportContainer|PoolStringArray|PoolByteArray|PoolIntArray|PoolRealArray|PoolVector2Array|PoolVector3Array|PoolColorArray)\b",
     "Godot 3 class name -> CharacterBody2D/CharacterBody3D/Node3D/SubViewportContainer/Packed*Array"),
    (r"\.instance\(\)", "'.instance()' -> '.instantiate()'"),
    (r"\bchange_scene\s*\(", "'change_scene()' -> change_scene_to_file()/change_scene_to_packed()"),
    (r"""\.connect\(\s*["'][^"']+["']\s*,\s*(self|[A-Za-z_]+)\s*,\s*["']""", "old connect('sig', obj, 'method') -> signal.connect(callable)"),
    (r"\b(rand_range|deg2rad|rad2deg|stepify|OS\.get_ticks_msec|OS\.get_ticks_usec)\b",
     "renamed API -> randf_range/deg_to_rad/rad_to_deg/snappedf/Time.get_ticks_msec"),
    (r"\.empty\(\)", "'.empty()' -> '.is_empty()'"),
    (r"\b(File|Directory)\.new\(\)", "File/Directory -> FileAccess/DirAccess static methods"),
    (r"\bmove_and_slide\([^)]", "move_and_slide() takes no arguments in Godot 4 (set 'velocity' first)"),
    (r"\bmove_and_slide_with_snap\b", "'move_and_slide_with_snap' was removed (use floor_snap_length)"),
    (r"\bTween\.new\(\)|\$Tween\b", "Godot 4 tweens: create_tween()"),
    (r"\bAnimationPlayer\.playback_speed\b", "use 'speed_scale' in Godot 4"),
    (r"""\bget_node\(\s*["']/root/""", "prefer an autoload name or %UniqueName over absolute /root paths"),
]

_BLOCK_KW = re.compile(r"^(static\s+func|func|if|elif|else|for|while|match|class|var\s+\w+.*:\s*$)\b")


def _strip_gd(line: str) -> str:
    """Remove strings and comments from a GDScript line (rough)."""
    out = []
    in_str = ""
    esc = False
    for ch in line:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == in_str:
                in_str = ""
            continue
        if ch in "\"'":
            in_str = ch
            continue
        if ch == "#":
            break
        out.append(ch)
    return "".join(out)


def _strip_comment(line: str) -> str:
    """Remove a trailing # comment but keep string contents."""
    in_str = ""
    esc = False
    for i, ch in enumerate(line):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == in_str:
                in_str = ""
            continue
        if ch in "\"'":
            in_str = ch
        elif ch == "#":
            return line[:i]
    return line


def lint_gdscript(text: str) -> list[dict]:
    """Fast structural checks. Not a replacement for `godot --check-only`."""
    issues: list[dict] = []
    lines = text.splitlines()
    uses_tab = uses_space = False
    depth = 0
    stmt_start = 0
    stmt_text = ""
    in_triple = False
    has_extends = False
    for no, raw in enumerate(lines, 1):
        if raw.count('"""') % 2 == 1:
            in_triple = not in_triple
            continue
        if in_triple:
            continue
        line = _strip_gd(raw)
        indent = raw[: len(raw) - len(raw.lstrip())]
        if line.strip():
            if "\t" in indent:
                uses_tab = True
            if " " in indent and depth == 0:
                uses_space = True
        if re.match(r"^\s*extends\b", raw) or re.match(r"^\s*class_name\b.*\bextends\b", raw):
            has_extends = True
        with_strings = _strip_comment(raw)
        for pat, msg in _GD3_PATTERNS:
            if re.search(pat, with_strings):
                issues.append({"line": no, "severity": "error" if "prefer" not in msg else "warning",
                               "message": msg})
        if depth == 0:
            stmt_start = no
            stmt_text = ""
        stmt_text += " " + line.strip()
        depth, _, _ = _scan(line, depth)
        if depth < 0:
            issues.append({"line": no, "severity": "error", "message": "unbalanced closing bracket"})
            depth = 0
        if depth == 0 and stmt_text.strip():
            s = stmt_text.strip()
            first = re.match(r"^(static\s+func|func|if|elif|else|for|while|match|class)\b", s)
            if first and ":" not in s:
                issues.append({"line": stmt_start, "severity": "error",
                               "message": f"'{first.group(1)}' statement is missing a trailing ':'"})
    if depth > 0:
        issues.append({"line": stmt_start, "severity": "error", "message": "unclosed bracket/parenthesis"})
    if uses_tab and uses_space:
        issues.append({"line": 1, "severity": "error",
                       "message": "mixed tab and space indentation (GDScript requires one style per file; use tabs)"})
    if text.strip() and not has_extends and not text.lstrip().startswith("@tool"):
        if not any(re.match(r"^\s*(class_name|extends)\b", l) for l in lines):
            issues.append({"line": 1, "severity": "info",
                           "message": "no 'extends' (script will extend RefCounted) - add one if this attaches to a node"})
    return issues


# --------------------------------------------------------------------------- #
# project scaffolding
# --------------------------------------------------------------------------- #
ICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">'
    '<rect width="128" height="128" rx="24" fill="#2b3a55"/>'
    '<circle cx="64" cy="64" r="34" fill="#f2b84b"/>'
    '<path d="M44 70 L64 36 L84 70 Z" fill="#2b3a55"/></svg>\n'
)

GITIGNORE = """# Godot 4+
.godot/
*.translation
# Mono / .NET
.mono/
data_*/
mono_crash.*.json
bin/
obj/
*.sln.DotSettings.user
# Export
export_credentials.cfg
builds/
# OS / editor
.DS_Store
Thumbs.db
.vscode/
.idea/
# Studio scratch
.studio_tmp/
"""

GITATTRIBUTES = "* text=auto eol=lf\n*.png binary\n*.ogg binary\n*.wav binary\n*.glb binary\n"
EDITORCONFIG = "root = true\n\n[*]\ncharset = utf-8\nend_of_line = lf\ninsert_final_newline = true\n\n[*.{gd,gdshader,cs}]\nindent_style = tab\n"

DIRS = ["scenes", "scenes/levels", "scenes/ui", "scenes/actors", "scripts", "scripts/autoload",
        "scripts/components", "assets/sprites", "assets/tilesets", "assets/models", "assets/textures",
        "assets/audio/sfx", "assets/audio/music", "assets/fonts", "assets/ui", "assets/shaders",
        "resources", "tests"]


def project_godot_text(name: str, kind: str = "2d", renderer: str = "forward_plus",
                       dotnet: bool = False, width: int = 1280, height: int = 720,
                       pixel_art: bool = False, version: str = "4.7") -> str:
    feats = [version]
    method = {"forward_plus": ("forward_plus", "Forward Plus"),
              "mobile": ("mobile", "Mobile"),
              "compatibility": ("gl_compatibility", "GL Compatibility")}.get(renderer, ("forward_plus", "Forward Plus"))
    if dotnet:
        feats.append("C#")
    feats.append(method[1])
    feat_str = ", ".join(f'"{f}"' for f in feats)
    safe_name = name.replace('"', "'")
    lines = [
        "; Engine configuration file.",
        "; It's best edited using the editor UI and not directly,",
        "; since the parameters that go here are not all obvious.",
        ";",
        "; Format:",
        ";   [section] ; section goes between []",
        ";   param=value ; assign values to parameters",
        "",
        "config_version=5",
        "",
        "[application]",
        "",
        f'config/name="{safe_name}"',
        'run/main_scene="res://scenes/main.tscn"',
        f"config/features=PackedStringArray({feat_str})",
        'config/icon="res://icon.svg"',
        "",
    ]
    if dotnet:
        asm = re.sub(r"[^A-Za-z0-9_]", "", name) or "Game"
        lines += ["[dotnet]", "", f'project/assembly_name="{asm}"', ""]
    lines += ["[display]", ""]
    if pixel_art:
        vw, vh = max(64, width // 4), max(64, height // 4)
        lines += [f"window/size/viewport_width={vw}", f"window/size/viewport_height={vh}",
                  f"window/size/window_width_override={vw * 4}", f"window/size/window_height_override={vh * 4}",
                  'window/stretch/mode="viewport"', 'window/stretch/scale_mode="integer"']
    else:
        lines += [f"window/size/viewport_width={width}", f"window/size/viewport_height={height}",
                  'window/stretch/mode="canvas_items"']
    lines += ["", "[rendering]", "", f'renderer/rendering_method="{method[0]}"']
    if renderer == "compatibility":
        lines.append('renderer/rendering_method.mobile="gl_compatibility"')
    if pixel_art:
        lines += ["textures/canvas_textures/default_texture_filter=0", "2d/snap/snap_2d_transforms_to_pixel=true",
                  "2d/snap/snap_2d_vertices_to_pixel=true"]
    lines.append("")
    if kind == "2d":
        lines += ["[layer_names]", "", '2d_physics/layer_1="world"', '2d_physics/layer_2="player"',
                  '2d_physics/layer_3="enemy"', '2d_physics/layer_4="player_hitbox"',
                  '2d_physics/layer_5="enemy_hitbox"', '2d_physics/layer_6="pickup"', ""]
    else:
        lines += ["[layer_names]", "", '3d_physics/layer_1="world"', '3d_physics/layer_2="player"',
                  '3d_physics/layer_3="enemy"', '3d_physics/layer_4="player_hitbox"',
                  '3d_physics/layer_5="enemy_hitbox"', '3d_physics/layer_6="pickup"', ""]
    return "\n".join(lines)


MAIN_SCRIPT = """extends Node{dim}
## Entry point. Replace with your game bootstrap.

func _ready() -> void:
\tprint("{name} ready")
"""


def create_project(root: Path, name: str, kind: str = "2d", renderer: str = "forward_plus",
                   dotnet: bool = False, width: int = 1280, height: int = 720,
                   pixel_art: bool = False, version: str = "4.7") -> list[str]:
    created: list[str] = []
    root.mkdir(parents=True, exist_ok=True)
    for d in DIRS:
        (root / d).mkdir(parents=True, exist_ok=True)
        (root / d / ".gdignore").unlink(missing_ok=True)

    def write(rel: str, content: str) -> None:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            p.write_text(content, encoding="utf-8", newline="\n")
            created.append(rel)

    write("project.godot", project_godot_text(name, kind, renderer, dotnet, width, height, pixel_art, version))
    write("icon.svg", ICON_SVG)
    write(".gitignore", GITIGNORE)
    write(".gitattributes", GITATTRIBUTES)
    write(".editorconfig", EDITORCONFIG)
    dim = "2D" if kind == "2d" else "3D"
    write("scripts/main.gd", MAIN_SCRIPT.format(dim=dim, name=name))
    write("scenes/main.tscn", build_scene({
        "root": {"name": "Main", "type": f"Node{dim}", "script": "res://scripts/main.gd"},
    }))
    write("CLAUDE.md", project_claude_md(name, kind, dotnet, pixel_art))
    write("README.md", f"# {name}\n\nGodot {version} project generated by Godot Game Studio.\n")
    if dotnet:
        asm = re.sub(r"[^A-Za-z0-9_]", "", name) or "Game"
        write(f"{asm}.csproj",
              f'<Project Sdk="Godot.NET.Sdk/{version}.0">\n  <PropertyGroup>\n'
              f"    <TargetFramework>net8.0</TargetFramework>\n"
              f"    <EnableDynamicLoading>true</EnableDynamicLoading>\n"
              f"    <RootNamespace>{asm}</RootNamespace>\n  </PropertyGroup>\n</Project>\n")
    return created


def project_claude_md(name: str, kind: str, dotnet: bool, pixel_art: bool) -> str:
    lang = "C# (.NET build) plus GDScript for glue" if dotnet else "GDScript (typed)"
    art = "pixel art, nearest filtering, integer scaling" if pixel_art else ("2D" if kind == "2d" else "3D")
    return f"""# {name}

Godot 4.x project ({art}). Language: {lang}.

## Conventions
- Tabs for indentation. snake_case files/functions/vars, PascalCase classes/nodes, SIGNAL_NAMES in past tense.
- Always static-type GDScript (`var speed: float = 200.0`, `func f(x: int) -> void:`).
- One scene per actor in `scenes/actors/`, scripts in `scripts/`, reusable nodes in `scripts/components/`.
- Autoloads live in `scripts/autoload/` and are registered in project.godot (`godot_add_autoload`).
- Collision layers: 1 world, 2 player, 3 enemy, 4 player_hitbox, 5 enemy_hitbox, 6 pickup.
- Never hand-edit `.godot/`. Never commit it.

## Workflow with the Godot Game Studio plugin
- Create/modify scenes with the `godot_*` MCP tools (they write valid .tscn) and verify with `godot_validate_project`.
- After writing scripts run `godot_check_script`; before saying "done" run `godot_run_project` for a few seconds and read the errors.
- Art: `/make-sprite`, `/art-pass`. Audio: `/audio-pass`. 3D: `/make-3d-asset`.
"""


# --------------------------------------------------------------------------- #
# templates and addon
# --------------------------------------------------------------------------- #
def list_templates() -> list[str]:
    if not TEMPLATES_DIR.is_dir():
        return []
    return sorted(str(p.relative_to(TEMPLATES_DIR)).replace("\\", "/") for p in TEMPLATES_DIR.rglob("*") if p.is_file())


def install_addon(project_root: Path) -> list[str]:
    src = ADDON_DIR / "claude_bridge"
    dst = project_root / "addons" / "claude_bridge"
    dst.mkdir(parents=True, exist_ok=True)
    copied = []
    for f in src.iterdir():
        if f.is_file():
            shutil.copy2(f, dst / f.name)
            copied.append(f"addons/claude_bridge/{f.name}")
    cfg = project_root / "project.godot"
    text = cfg.read_text(encoding="utf-8")
    settings = project_settings(text)
    current = settings.get("editor_plugins", {}).get("enabled", "PackedStringArray()")
    plugin = "res://addons/claude_bridge/plugin.cfg"
    if plugin not in current:
        existing = re.findall(r'"([^"]+)"', current)
        existing.append(plugin)
        new_val = "PackedStringArray(" + ", ".join(f'"{e}"' for e in existing) + ")"
        text = set_project_setting(text, "editor_plugins", "enabled", new_val)
        cfg.write_text(text, encoding="utf-8", newline="\n")
        copied.append("project.godot (plugin enabled)")
    return copied


# --------------------------------------------------------------------------- #
# GDScript helper programs (run through `godot --headless -s`)
# --------------------------------------------------------------------------- #
def normalize_indent(code: str) -> str:
    lines = code.replace("\r\n", "\n").split("\n")
    if any(l.startswith("\t") for l in lines):
        return "\n".join(lines)
    units = [len(l) - len(l.lstrip(" ")) for l in lines if l.strip() and l.startswith(" ")]
    unit = min(units) if units else 4
    out = []
    for l in lines:
        n = len(l) - len(l.lstrip(" "))
        out.append("\t" * (n // unit) + " " * (n % unit) + l.lstrip(" ") if n else l)
    return "\n".join(out)


def wrap_script(code: str) -> str:
    """Turn a snippet into a runnable SceneTree script (or pass a full script through)."""
    code = normalize_indent(code)
    if re.search(r"^\s*extends\s+", code, re.M):
        return code if code.endswith("\n") else code + "\n"
    body = "\n".join(("\t" + l) if l.strip() else l for l in code.split("\n"))
    return ("extends SceneTree\n\n"
            "func _initialize() -> void:\n\tawait _studio_run()\n\tquit()\n\n"
            "func _studio_run() -> void:\n\tawait process_frame\n" + body + "\n")


CLASS_REF_SCRIPT = "\n".join([
    "extends SceneTree",
    "",
    "func _initialize() -> void:",
    '\tvar cname := "__CLASS__"',
    "\tif not ClassDB.class_exists(cname):",
    '\t\tprint("@@RESULT@@" + JSON.stringify({"error": "unknown class"}))',
    "\t\tquit()",
    "\t\treturn",
    "\tvar d := {",
    '\t\t"class": cname,',
    '\t\t"parent": ClassDB.get_parent_class(cname),',
    '\t\t"can_instantiate": ClassDB.can_instantiate(cname),',
    '\t\t"inheriters": ClassDB.get_inheriters_from_class(cname),',
    '\t\t"properties": ClassDB.class_get_property_list(cname, true),',
    '\t\t"methods": ClassDB.class_get_method_list(cname, true),',
    '\t\t"signals": ClassDB.class_get_signal_list(cname, true),',
    '\t\t"constants": ClassDB.class_get_integer_constant_list(cname, true),',
    "\t}",
    '\tprint("@@RESULT@@" + JSON.stringify(d))',
    "\tquit()",
    "",
])

CLASS_LIST_SCRIPT = "\n".join([
    "extends SceneTree",
    "",
    "func _initialize() -> void:",
    "\tvar names := ClassDB.get_class_list()",
    '\tprint("@@RESULT@@" + JSON.stringify(Array(names)))',
    "\tquit()",
    "",
])


def summarize_class(data: dict, detail: bool = False) -> dict:
    if "error" in data:
        return data
    type_names = {0: "Variant", 1: "bool", 2: "int", 3: "float", 4: "String", 5: "Vector2", 6: "Vector2i",
                  7: "Rect2", 8: "Rect2i", 9: "Vector3", 10: "Vector3i", 11: "Transform2D", 12: "Vector4",
                  13: "Vector4i", 14: "Plane", 15: "Quaternion", 16: "AABB", 17: "Basis", 18: "Transform3D",
                  19: "Projection", 20: "Color", 21: "StringName", 22: "NodePath", 23: "RID", 24: "Object",
                  25: "Callable", 26: "Signal", 27: "Dictionary", 28: "Array", 29: "PackedByteArray",
                  30: "PackedInt32Array", 31: "PackedInt64Array", 32: "PackedFloat32Array",
                  33: "PackedFloat64Array", 34: "PackedStringArray", 35: "PackedVector2Array",
                  36: "PackedVector3Array", 37: "PackedColorArray", 38: "PackedVector4Array"}

    def tname(t: Any) -> str:
        return type_names.get(t, str(t)) if isinstance(t, int) else str(t)

    props = [f"{p['name']}: {p.get('class_name') or tname(p.get('type'))}" for p in data.get("properties", [])
             if p.get("usage", 0) & 4 or detail]
    methods = []
    for m in data.get("methods", []):
        if m["name"].startswith("_") and not detail:
            continue
        args = ", ".join(f"{a['name']}: {a.get('class_name') or tname(a.get('type'))}" for a in m.get("args", []))
        ret = m.get("return", {})
        if not ret or (ret.get("type", 0) == 0 and not (ret.get("usage", 0) & 131072)):
            rt = "void"
        else:
            rt = ret.get("class_name") or tname(ret.get("type", 0))
        methods.append(f"{m['name']}({args}) -> {rt}")
    sigs = []
    for s in data.get("signals", []):
        args = ", ".join(f"{a['name']}: {a.get('class_name') or tname(a.get('type'))}" for a in s.get("args", []))
        sigs.append(f"{s['name']}({args})")
    return {"class": data["class"], "parent": data["parent"], "can_instantiate": data["can_instantiate"],
            "direct_subclasses": data["inheriters"], "properties": props, "methods": methods,
            "signals": sigs, "constants": data.get("constants", [])}
