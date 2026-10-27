extends Node
## Global signal hub (autoload as "EventBus"). Decouples systems: emit from anywhere, connect from anywhere.
##   EventBus.score_changed.emit(100)
##   EventBus.score_changed.connect(_on_score_changed)

@warning_ignore("unused_signal")
signal game_started
@warning_ignore("unused_signal")
signal game_paused(is_paused: bool)
@warning_ignore("unused_signal")
signal game_over(won: bool)
@warning_ignore("unused_signal")
signal level_started(level_id: StringName)
@warning_ignore("unused_signal")
signal level_completed(level_id: StringName)
@warning_ignore("unused_signal")
signal score_changed(new_score: int)
@warning_ignore("unused_signal")
signal player_died
@warning_ignore("unused_signal")
signal player_health_changed(current: int, maximum: int)
@warning_ignore("unused_signal")
signal item_collected(item_id: StringName, amount: int)
@warning_ignore("unused_signal")
signal checkpoint_reached(position: Vector2)
@warning_ignore("unused_signal")
signal dialogue_requested(dialogue_id: StringName)
@warning_ignore("unused_signal")
signal screen_shake_requested(strength: float)
