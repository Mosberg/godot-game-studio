extends CanvasLayer
## Scene transitions autoload ("SceneManager"): fade out, threaded load, swap, fade in.
##   await SceneManager.change_scene("res://scenes/levels/level_02.tscn")
## Emits `scene_changed` after the new scene is in the tree.

signal transition_started(path: String)
signal scene_changed(path: String)

@export var fade_time: float = 0.3
@export var fade_color: Color = Color.BLACK

var _rect: ColorRect = ColorRect.new()
var _busy: bool = false


func _ready() -> void:
	layer = 100
	process_mode = Node.PROCESS_MODE_ALWAYS
	_rect.color = fade_color
	_rect.modulate.a = 0.0
	_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(_rect)


func change_scene(path: String, custom_fade: float = -1.0) -> void:
	if _busy:
		return
	_busy = true
	var duration: float = fade_time if custom_fade < 0.0 else custom_fade
	transition_started.emit(path)
	_rect.mouse_filter = Control.MOUSE_FILTER_STOP # block clicks mid-transition
	await _fade(1.0, duration)
	var err: Error = ResourceLoader.load_threaded_request(path)
	if err != OK:
		push_error("SceneManager: cannot load '%s' (%s)" % [path, error_string(err)])
		await _fade(0.0, duration)
		_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_busy = false
		return
	while ResourceLoader.load_threaded_get_status(path) == ResourceLoader.THREAD_LOAD_IN_PROGRESS:
		await get_tree().process_frame
	var packed: PackedScene = ResourceLoader.load_threaded_get(path) as PackedScene
	if packed == null:
		push_error("SceneManager: '%s' did not load as a PackedScene" % path)
	else:
		get_tree().paused = false
		get_tree().change_scene_to_packed(packed)
		await get_tree().process_frame
	await _fade(0.0, duration)
	_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_busy = false
	scene_changed.emit(path)


func reload_current(custom_fade: float = -1.0) -> void:
	var scene: Node = get_tree().current_scene
	if scene != null:
		await change_scene(scene.scene_file_path, custom_fade)


func _fade(target_alpha: float, duration: float) -> void:
	if duration <= 0.0:
		_rect.modulate.a = target_alpha
		return
	var tween: Tween = create_tween()
	tween.tween_property(_rect, "modulate:a", target_alpha, duration)
	await tween.finished
