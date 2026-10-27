---
name: csharp-godot
description: C# with Godot 4.x .NET - project setup, partial classes, exports, signals, async, interop with GDScript, building, debugging and platform limits.
---

# C# in Godot (.NET build)

- Needs the **.NET editor build** plus the .NET SDK (8+; Android needs 9+). Verify with `godot_info`. Create: `godot_create_project(dotnet=True)` (also writes a `.csproj` using `Godot.NET.Sdk`).
- Classes: `public partial class Enemy : CharacterBody2D`, filename = class name. After changes run `godot_dotnet_build`.
- Signals: `[Signal] public delegate void DiedEventHandler(int score);` -> `EmitSignal(SignalName.Died, 10);` connect `enemy.Died += OnDied;`.
- Exports: `[Export] public PackedScene BulletScene { get; set; }`, `[ExportGroup("Movement")]`.
- Input names as `StringName`; `Input.GetVector(...)`. Node lookup: `GetNode<Sprite2D>("%Sprite")` once in `_Ready`, cache.
- Threads/async: use `await ToSignal(...)`; never touch nodes from other threads (use `CallDeferred`).
- Mixing languages: C# can call GDScript via `node.Call("method")`; GDScript can call C# methods normally.
- Debug: `dotnet build` errors surface first; Godot reloads assemblies on focus; restart editor if types vanish.
- Limits: no web export; hot reload is limited; larger first-run build time.
