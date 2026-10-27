---
name: editor-bridge
description: Use the live Godot editor connection - install the Claude bridge plugin, open the editor, then manipulate scenes, nodes, properties and playtest while the editor is open, with screenshots. Also the Blender live bridge.
---

# Live editor bridge

**Godot**
1. `godot_install_editor_bridge` copies `addons/claude_bridge` into the project and enables it.
2. `godot_open_editor` launches the editor (project path); wait, then `godot_editor_status` (TCP 127.0.0.1:9877).
3. `godot_editor(command, args)`: open_scene, scene_tree, select_node, add_node, instance_scene, set_property, set_script, save_scene, run_scene, stop, screenshot, filesystem_scan, reimport, set_project_setting, execute (arbitrary GDScript; set `GODOT_EDITOR_ALLOW_EXECUTE=0` before launching the editor to disable).
4. `godot_editor_screenshot` -> view the PNG to verify layout/visuals.
5. Use headless tools when the editor is *not* running; the editor overwrites files it has open, so prefer bridge edits while it is.
- Security: localhost only; set `GODOT_EDITOR_TOKEN` to require a token. Never expose the port.

**Blender**: `blender_install_addon` once, then `blender_bridge_status`, `blender_bridge_execute`, `blender_bridge_screenshot`. Headless alternative: `blender_start_headless_bridge`.
