class_name Projectile2D
extends Hitbox2D
## Straight-line projectile. Instantiate, set `direction`, add to the scene.
## Frees itself after `lifetime` seconds, on hitting the world, or after hitting a Hurtbox2D.
## Works with ObjectPool: implements on_acquire()/on_release().

@export var speed: float = 260.0
@export var lifetime: float = 2.0
@export var pierce: int = 0 ## extra hurtboxes it may pass through

var direction: Vector2 = Vector2.RIGHT
var _age: float = 0.0
var _pierce_left: int = 0


func _ready() -> void:
	super._ready()
	_pierce_left = pierce
	body_entered.connect(_on_body_entered)
	area_entered.connect(_on_area_entered)


func on_acquire() -> void:
	_age = 0.0
	_pierce_left = pierce


func on_release() -> void:
	set_deferred("monitoring", false)


func _physics_process(delta: float) -> void:
	position += direction * speed * delta
	rotation = direction.angle()
	_age += delta
	if _age >= lifetime:
		_finish()


func _on_body_entered(_body: Node2D) -> void:
	_finish() # hit the world (walls/ground are on the mask)


func _on_area_entered(area: Area2D) -> void:
	if area is Hurtbox2D:
		if _pierce_left > 0:
			_pierce_left -= 1
		else:
			_finish()


func _finish() -> void:
	queue_free()
