class_name Hitbox2D
extends Area2D
## Deals damage to any Hurtbox2D it overlaps. Put on the attacker (sword swing, bullet, spikes).
## Use collision layers: hitbox layer = "player_hitbox"/"enemy_hitbox", mask = the opposing hurtbox layer.

@export var damage: int = 10
@export var knockback: float = 120.0
## Who is responsible for the damage (defaults to the owner of the scene).
@export var source: Node


func _ready() -> void:
	if source == null:
		source = owner if owner != null else get_parent()
