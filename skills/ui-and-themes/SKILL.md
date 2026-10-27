---
name: ui-and-themes
description: Build Godot UI - main menu, HUD, pause, settings, dialogs, inventories - with Control nodes, containers, themes, anchors, focus/gamepad navigation and localisation.
---

# UI & themes

- Root every screen in a `Control` (Full Rect) -> `MarginContainer` -> `VBoxContainer/HBoxContainer/GridContainer`. Never place by pixel offsets; use `size_flags` and `custom_minimum_size`.
- One theme: `res://ui/theme.tres` (`godot_create_resource` Theme), set as project default `gui/theme/custom`. Define fonts, font sizes, StyleBoxFlat/Texture for Button, Panel, Label, ProgressBar. Pixel-art UI: 9-slice `StyleBoxTexture`, Nearest filter.
- **HUD**: `CanvasLayer` scene listening to `Events` signals (health_changed, score_changed) - no polling, no direct references to gameplay nodes.
- **Menus**: set `focus_mode`, `grab_focus()` on the first button, wire `ui_accept/ui_cancel`, ensure neighbours for gamepad. Pause menu: `process_mode = PROCESS_MODE_WHEN_PAUSED`, `get_tree().paused = true` (template `pause_controller`).
- **Settings**: master/music/sfx sliders -> AudioServer bus volume (`linear_to_db`), fullscreen, vsync, input rebinding; persist with `settings_manager` (ConfigFile).
- **Dialogue**: `dialogue_runner` template with `RichTextLabel.visible_ratio` typewriter, BBCode, choices as Buttons.
- Scale: project stretch mode `canvas_items`, aspect `expand`; test at 16:9, 16:10, 21:9, and 1280x720.
- Localisation: wrap text with `tr()`, CSV/PO translations in Project Settings.
