---
name: gdscript-style
description: GDScript 2.0 coding conventions, typing, signals, node lifecycle and common Godot 3-to-4 pitfalls. Use whenever writing or reviewing GDScript.
---

# GDScript style (Godot 4.x)

## Layout of a script
```gdscript
class_name Player
extends CharacterBody2D
## One-line doc comment.

signal died
signal health_changed(current: int, maximum: int)

enum State { IDLE, RUN, JUMP, FALL }

const SPEED := 220.0

@export var max_health: int = 5
@export_range(0.0, 1.0) var friction: float = 0.2

var _state: State = State.IDLE

@onready var sprite: AnimatedSprite2D = %Sprite
```
Order: class_name, extends, doc, signals, enums, consts, exports, vars, onready, `_init/_ready/_process`, public methods, private methods.

## Rules
- Type everything; use `:=` only when the type is obvious. Typed arrays/dictionaries (`Array[int]`, `Dictionary[String, int]` in 4.4+).
- `_physics_process` for movement, `_process` for visuals. `delta` always used for time-based motion.
- Input: actions only; `Input.get_vector("left","right","up","down")` for 2D movement.
- Signals up, calls down. Connect in code with `signal.connect(callable)`; use `CONNECT_ONE_SHOT` when apt.
- Free safely: `queue_free()`, check `is_instance_valid()`. Tween with `create_tween()`; kill old tweens before new.
- Await: `await get_tree().create_timer(0.5).timeout`; `await animation_player.animation_finished`.
- Use `StringName` literals (`&"jump"`) in hot paths. Use `Callable` and lambdas sparingly.
- Resources for data (`class_name WeaponData extends Resource`), `@export_group` for tidy inspectors.

## Godot 3 leftovers the linter catches
`yield`, `onready var`, `export var`, `tool`, `setget`, `connect("sig", self, "fn")`, `KinematicBody2D`, `move_and_slide(velocity)`, `OS.get_ticks_msec` -> use `Time.get_ticks_msec()`, `rand_range` -> `randf_range`, `instance()` -> `instantiate()`, `.empty()` -> `.is_empty()`.

Run `godot_lint` after edits and `godot_check_script` for the real parser.
