#!/usr/bin/env python3
"""PostToolUse hook: lint .gd / validate .tscn|.tres right after Claude writes them.

Reads the hook JSON from stdin. On errors prints them to stderr and exits 2, which feeds the message back to
Claude so it can fix the file immediately. Silent (exit 0) for other files and when everything is fine.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp"))


def find_project_root(path: Path):
    for parent in [path.parent, *path.parents]:
        if (parent / "project.godot").exists():
            return parent
    return None


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:  # noqa: BLE001
        return 0
    inp = data.get("tool_input") or {}
    file_path = inp.get("file_path") or inp.get("path")
    if not file_path:
        return 0
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix not in (".gd", ".tscn", ".tres") or not path.exists():
        return 0
    root = find_project_root(path)
    if root is None:
        return 0
    try:
        import godot_lib as gl
        text = path.read_text(encoding="utf-8")
        if suffix == ".gd":
            problems = gl.lint_gdscript(text)
        else:
            problems = gl.validate_scene_text(text, root)
    except Exception:  # noqa: BLE001 - never block work because the hook itself failed
        return 0
    lines = []
    for p in problems:
        if isinstance(p, dict):
            if p.get("severity", "error") != "error":
                continue
            lines.append(f"  line {p.get('line', '?')}: {p.get('message', p)}")
        else:
            lines.append(f"  {p}")
    if not lines:
        return 0
    print(f"Godot validation found problems in {path.name}:\n" + "\n".join(lines[:15]) +
          "\nFix these (use godot_check_script / godot_validate_project to re-verify).", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
