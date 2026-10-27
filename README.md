# Godot Game Studio — a Claude Code plugin

Build Godot 4 games with Claude: scaffold projects, write GDScript/C#, generate and edit scenes, run and
playtest headless, export — plus Blender, ComfyUI, GIMP/Pillow and procedural audio for assets.
Built against **Godot 4.7.2** (18 Aug 2026 patch release) and works with the **.NET** build too.

> **Status / honesty:** the pure-Python parts (project/scene/resource file handling, linting, image and audio
> pipelines, the ComfyUI client, server plumbing, hooks) were run and tested. The parts that need the real
> programs — Godot executions, the Godot editor bridge (GDScript), GDScript/C# templates, shaders, every
> Blender script and add-on, GIMP batch calls — were written carefully against the 4.x / Blender APIs but
> **could not be run in the build environment** (no Godot/Blender/GIMP installed there). Run `/studio-doctor`,
> then try `/new-game` on your machine and report anything that misbehaves; expect a few small fixes.

## What you get

| | |
|---|---|
| **MCP servers (5, 109 tools)** | `godot` (project/scene/script/run/test/export + live editor), `blender` (headless + live bridge), `comfyui`, `assets` (Pillow pixel-art + audio), `gimp` |
| **Agents (12)** | game-director, gdscript-engineer, csharp-engineer, scene-architect, technical-artist-2d, blender-3d-artist, comfyui-operator, audio-designer, qa-playtester, game-designer, build-release-engineer, shader-vfx-artist |
| **Skills (19)** | project setup, GDScript style, scenes/nodes, 2D platformer, 3D, UI/themes, shaders/VFX, physics/nav/AI, multiplayer, export/release, C#, Blender→Godot, ComfyUI art, pixel-art pipeline, audio, testing/debugging, GDD, save/load, editor bridge |
| **Commands (10)** | `/new-game` `/add-feature` `/make-sprite` `/make-3d-asset` `/playtest` `/export-game` `/studio-doctor` `/game-jam` `/art-pass` `/audio-pass` |
| **Hooks** | PostToolUse lint/validation of `.gd`/`.tscn`/`.tres` (errors go straight back to Claude); SessionStart status |
| **Templates** | 21 GDScript, 3 C#, 10 shaders, a GUT test — added with `godot_add_template` |

## Install

1. Requirements: **Python 3.10+**, then `pip install -r requirements.txt` (mcp, Pillow, numpy).
2. Add the plugin (from the folder that contains this directory):
   ```
   /plugin marketplace add ./godot-game-studio
   /plugin install godot-game-studio@godot-game-studio
   ```
   or run Claude Code with `claude --plugin-dir ./godot-game-studio` for a quick test.
3. **Windows:** `.mcp.json` launches servers with `python`. If your launcher is `py`, edit `.mcp.json`
   (`"command": "py"`). On macOS/Linux use `python3`.
4. Run `/studio-doctor` (or `python scripts/doctor.py`).

## Configure (environment variables, all optional)

| Variable | Purpose |
|---|---|
| `GODOT_PATH` | Godot executable. Auto-detected on PATH and common install dirs. Windows: prefer `Godot_v4.7.2-stable_win64_console.exe` so output is captured |
| `BLENDER_PATH` | `blender.exe` / `blender` |
| `COMFYUI_URL` | default `http://127.0.0.1:8188` |
| `COMFY_WORKFLOWS_DIR` | folder with API-format workflow JSON files |
| `GIMP_PATH` | `gimp-console-3.0.exe` / `gimp-console-2.10.exe` |
| `FFMPEG_PATH` | for audio conversion |
| `GAME_PROJECT_DIR` | default project; otherwise the current directory (searched upward for `project.godot`) |
| `GODOT_EDITOR_PORT` / `BLENDER_BRIDGE_PORT` | bridge ports (9877 / 9876) |
| `GODOT_EDITOR_TOKEN` / `BLENDER_BRIDGE_TOKEN` | shared secret required by the bridges |
| `GODOT_EDITOR_ALLOW_EXECUTE=0` | disables the editor bridge `execute` command (arbitrary GDScript; **on** by default — it is what makes full editor control possible) |

## Godot 4.7.2 notes

- **.NET:** use the "Godot .NET" editor build *and* the .NET SDK (8+; 9+ for Android). C# projects can't export to Web; Android/iOS export is experimental. Steam/itch/Epic Godot builds have no .NET. Godot 4.8 (beta) will need .NET 10; .NET 8/9 go out of support 10 Nov 2026.
- Export templates must match the editor version exactly.

## Typical sessions

```
/new-game 2D pixel-art platformer about a robot gardener
/make-sprite robot gardener, 32px, sweetie16
/make-3d-asset low-poly wooden chest
/audio-pass cheerful chiptune
/playtest
/export-game windows web
```

## Live bridges

- **Godot editor:** `godot_install_editor_bridge` → `godot_open_editor` → `godot_editor(...)`. The editor plugin listens on 127.0.0.1:9877 (newline-delimited JSON).
- **Blender:** `blender_install_addon` once (or `blender_start_headless_bridge`), then `blender_bridge_*` on 127.0.0.1:9876.

## Security notes

- Both bridges bind to **localhost only**; set the token variables to require a secret. Never port-forward them.
- `blender_run_python`, `blender_bridge_execute`, `godot_run_script` and `gimp_run_script` run code on your machine by design — review what Claude proposes if you work with untrusted prompts or files.
- File-writing Godot tools refuse paths that escape the project folder. Never open untrusted `.tres`/`.res` files in Godot (they can embed scripts).
- AI-generated art: check model/LoRA licences and store disclosure rules (e.g. Steam).

## Layout

```
.claude-plugin/  plugin.json marketplace.json     agents/  skills/  commands/  hooks/
.mcp.json        mcp/ (servers + libs)            godot_addon/ blender_addon/ blender_scripts/
templates/       scripts/doctor.py                requirements.txt
```

MIT licensed. Author: Rasmus Mosberg.
