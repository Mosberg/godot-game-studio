class_name Hurtbox2D
extends Area2D
## Receives damage from Hitbox2D areas and forwards it to a HealthComponent.

signal hit(hitbox: Hitbox2D)

@export var health: HealthComponent


func _ready() -> void:
	area_entered.connect(_on_area_entered)


func _on_area_entered(area: Area2D) -> void:
	if not (area is Hitbox2D):
		return
	var hitbox: Hitbox2D = area
	hit.emit(hitbox)
	if health != null:
		health.take_damage(hitbox.damage, hitbox.source)
