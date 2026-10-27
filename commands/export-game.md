---
description: Export the Godot project for one or more platforms and package it for release
argument-hint: <windows|linux|macos|web|android ...> [--debug]
---

Act as **build-release-engineer**. Export for: $ARGUMENTS

Check templates match the editor, create/list presets, export each platform into `builds/<platform>/`, smoke-test what can be run here, and zip per platform. Report file sizes, anything skipped (and why, e.g. web export for C# projects), and next steps for itch.io/Steam.
