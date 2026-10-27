---
description: Run and QA the current Godot project - validation, headless run, frame capture, tests, bug report
argument-hint: [scene or focus area]
---

Act as **qa-playtester** on the current project. Focus: $ARGUMENTS

Run `godot_validate_project`, `godot_run_project`, `godot_capture_frames` (view them), `godot_run_tests` if tests exist, and a scripted playtest when the `playtest_runner` template is present. Produce a short bug list (steps / expected / actual / cause / fix) and fix what is safe to fix, re-running to prove it.
