---
name: testing-and-debugging
description: Test and debug Godot projects headlessly - validation, parse checks, run logs, frame capture, GUT/gdUnit tests, scripted playtests, profiling, and a bug-report template.
---

# Testing & debugging

Order of operations: `godot_validate_project` -> `godot_check_script` (per file) -> `godot_run_project(seconds=...)` -> `godot_capture_frames` -> `godot_run_tests` -> scripted playtest.

- Reading errors: `Parser Error` (fix syntax/types first), `Invalid call. Nonexistent function` (wrong node type or null), `Node not found` (path/ready order), `Cannot find ... res://` (missing import: `godot_import`).
- Visual bugs: capture frames and *look*; use `--fixed-fps` so captures are deterministic.
- Unit tests: GUT (`addons/gut`) or gdUnit4; test pure logic and resources, keep scenes thin. Template: `tests/test_health_component.gd`.
- Playtest bots: `playtest_runner` template simulates inputs, asserts invariants, prints `@@RESULT@@` JSON for machine reading.
- Perf: `Performance.get_monitor(...)` printed over a headless run; check draw calls, physics frame time, orphan nodes.
- Bug template: Steps / Expected / Actual / Log excerpt / Root cause / Fix / Regression test.
