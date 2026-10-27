---
name: godot-scenes-and-nodes
description: How to design, generate and edit Godot scenes (.tscn), resources (.tres), node trees, instancing, groups, and collision layers using the plugin's scene tools instead of hand-editing text.
---

# Scenes & nodes

## Tools
`godot_create_scene`, `godot_read_scene`, `godot_scene_add_nodes`, `godot_scene_set_property`, `godot_scene_remove_node`, `godot_create_resource`, `godot_validate_project`.

## Spec for `godot_create_scene` / `godot_scene_add_nodes`
Flat node list; `parent` is `"."` for children of the root, otherwise the path from the root (`"Player/Hurtbox"`). Parents must come before their children.
```json
{"root": {"name": "Player", "type": "CharacterBody2D", "script": "res://scripts/player.gd"},
 "sub_resources": [{"id": "box", "type": "RectangleShape2D", "properties": {"size": "Vector2(14, 28)"}}],
 "nodes": [
   {"name": "Sprite", "type": "AnimatedSprite2D", "parent": "."},
   {"name": "Shape", "type": "CollisionShape2D", "parent": ".", "properties": {"shape": "@box"}},
   {"name": "Hurtbox", "instance": "res://scenes/actors/hurtbox.tscn", "parent": ".", "groups": ["player"]}],
 "connections": [{"signal": "died", "from": ".", "to": ".", "method": "_on_died"}]}
```
`godot_scene_add_nodes` takes the same shape without `root` (nodes/sub_resources/connections). Values: numbers/bools/lists, Godot literals (`"Vector2(1, 2)"`, `"Color(1, 0.5, 0, 1)"`, `"NodePath(\"../Foo\")"`), `res://` paths (auto-registered as ext_resources), `"@id"` for a sub-resource, plain text is auto-quoted. Use `instance` (and no `type`) to instance another scene.

## Patterns
- **Actor scene**: body + `CollisionShape` + `Sprite` + `Hurtbox(Area2D)` + `HealthComponent` + `StateMachine`.
- **Level scene**: `Node2D` root, `TileMapLayer`s (ground, decor), `Actors` (y-sort), `Spawns` (`Marker2D`), `Camera2D` with limits, `CanvasLayer` HUD instance.
- **Main**: tiny. Loads the first level through `SceneManager`.
- Use groups (`add_to_group("enemies")`), unique names (`%Label`), exported `NodePath`/typed node refs instead of long `get_node` paths.
- Collision: layer = what I am; mask = what I look for. Hitboxes/hurtboxes are `Area2D` on dedicated layers.
- Inspect any scene as a tree with `godot_read_scene` before editing; re-validate afterwards.
