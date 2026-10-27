#!/usr/bin/env python3
"""SessionStart hook: tell Claude whether this directory is a Godot project and which tools are reachable."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp"))


def main() -> int:
    try:
        import studio_common as sc
    except Exception:  # noqa: BLE001
        return 0
    lines = []
    cwd = Path(os.getcwd())
    proj = next((p for p in [cwd, *cwd.parents] if (p / "project.godot").exists()), None)
    if proj:
        lines.append(f"Godot project detected at {proj}. Read its CLAUDE.md. Use godot_* tools (headless) and godot_validate_project after edits.")
    else:
        lines.append("No project.godot here. Use /new-game or godot_create_project to start a game.")
    tools = {"godot": sc.find_godot(), "blender": sc.find_blender(), "gimp": sc.find_gimp(), "ffmpeg": sc.find_ffmpeg()}
    lines.append("Studio tools: " + ", ".join(f"{k}={'yes' if v else 'no'}" for k, v in tools.items()) + ". Run /studio-doctor for details.")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": " ".join(lines)}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
