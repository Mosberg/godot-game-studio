---
description: Create a new Godot game from an idea - scaffold, core mechanic, placeholder art, and a first playable run
argument-hint: <game idea, e.g. "2D pixel-art platformer about a robot gardener"> [--3d] [--csharp] [--dir PATH]
---

Act as the **game-director** agent. Build: $ARGUMENTS

1. Run `godot_info`; report engine/.NET availability briefly. Decide 2D/3D and GDScript/C# from the request (default GDScript; C# only if asked or `--csharp`).
2. Write a one-page `docs/GDD.md` (pitch, pillars, core loop, MUST/SHOULD/COULD) via the game-designer approach.
3. `godot_create_project` in the requested dir (default `./<slug>`), with pixel_art when the style calls for it. Add input actions, autoloads and the matching templates.
4. Build the smallest playable slice: player control, one hazard/enemy, one goal, HUD, game-over/restart. Use placeholder visuals (primitives) unless art tools are connected.
5. Validate and run (`godot_validate_project`, `godot_run_project`, `godot_capture_frames`) and look at the frames. Fix until clean.
6. Summarise: how to run it, what is placeholder, and the 3 best next steps.
