---
description: Add a gameplay feature to the current Godot project (inventory, dash, dialogue, save system, enemy type...)
argument-hint: <feature description>
---

Add this feature to the current project: $ARGUMENTS

1. Read the project (`godot_project_info`, `godot_search`, `CLAUDE.md`, the relevant scenes) and match its conventions.
2. State a 3-line plan (files touched, signals/data added). Use an existing template (`godot_list_templates`) if one fits.
3. Implement with the scene and script tools; keep components small and signal-driven.
4. Validate (`godot_validate_project`), add a test when logic is non-trivial (`godot_run_tests`), run headless and capture frames.
5. Report what changed and how to try it in the game.
