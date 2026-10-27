extends GutTest
## Example GUT test. Install GUT (addons/gut), enable it, then run with godot_run_tests.

var health: HealthComponent


func before_each() -> void:
	health = HealthComponent.new()
	health.max_health = 50
	add_child_autofree(health)


func test_starts_full() -> void:
	assert_eq(health.current_health, 50)


func test_damage_reduces_health() -> void:
	health.take_damage(20)
	assert_eq(health.current_health, 30)


func test_health_never_below_zero_and_emits_died_once() -> void:
	watch_signals(health)
	health.take_damage(500)
	health.take_damage(10)
	assert_eq(health.current_health, 0)
	assert_signal_emit_count(health, "died", 1)


func test_heal_is_capped_at_max() -> void:
	health.take_damage(10)
	health.heal(999)
	assert_eq(health.current_health, 50)


func test_invulnerability_blocks_second_hit() -> void:
	health.invulnerable_time = 5.0
	health.take_damage(10)
	health.take_damage(10)
	assert_eq(health.current_health, 40)
