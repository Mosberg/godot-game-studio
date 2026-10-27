extends Node
## Settings autoload ("Settings"): volumes, fullscreen, vsync and key rebinding persisted in
## user://settings.cfg and re-applied on startup. Works with the Audio autoload template.

signal settings_changed

const PATH: String = "user://settings.cfg"

var master_volume: float = 1.0
var music_volume: float = 0.8
var sfx_volume: float = 1.0
var fullscreen: bool = false
var vsync: bool = true

var _config: ConfigFile = ConfigFile.new()


func _ready() -> void:
	load_settings()
	apply()


func load_settings() -> void:
	if _config.load(PATH) != OK:
		return
	master_volume = _config.get_value("audio", "master", master_volume)
	music_volume = _config.get_value("audio", "music", music_volume)
	sfx_volume = _config.get_value("audio", "sfx", sfx_volume)
	fullscreen = _config.get_value("video", "fullscreen", fullscreen)
	vsync = _config.get_value("video", "vsync", vsync)
	_load_bindings()


func save_settings() -> void:
	_config.set_value("audio", "master", master_volume)
	_config.set_value("audio", "music", music_volume)
	_config.set_value("audio", "sfx", sfx_volume)
	_config.set_value("video", "fullscreen", fullscreen)
	_config.set_value("video", "vsync", vsync)
	_config.save(PATH)


func apply() -> void:
	_set_bus(&"Master", master_volume)
	_set_bus(&"Music", music_volume)
	_set_bus(&"SFX", sfx_volume)
	DisplayServer.window_set_mode(
		DisplayServer.WINDOW_MODE_FULLSCREEN if fullscreen else DisplayServer.WINDOW_MODE_WINDOWED)
	DisplayServer.window_set_vsync_mode(
		DisplayServer.VSYNC_ENABLED if vsync else DisplayServer.VSYNC_DISABLED)
	settings_changed.emit()


func _set_bus(bus_name: StringName, linear: float) -> void:
	var idx: int = AudioServer.get_bus_index(bus_name)
	if idx == -1:
		return
	AudioServer.set_bus_volume_db(idx, linear_to_db(clampf(linear, 0.0, 1.0)))
	AudioServer.set_bus_mute(idx, linear <= 0.001)


## Replace the first key/button event of an action and persist it.
func rebind_action(action: StringName, event: InputEvent) -> void:
	if not InputMap.has_action(action):
		return
	InputMap.action_erase_events(action)
	InputMap.action_add_event(action, event)
	_config.set_value("bindings", String(action), event)
	save_settings()


func reset_bindings() -> void:
	InputMap.load_from_project_settings()
	if _config.has_section("bindings"):
		_config.erase_section("bindings")
	save_settings()


func _load_bindings() -> void:
	if not _config.has_section("bindings"):
		return
	for action_name in _config.get_section_keys("bindings"):
		var value: Variant = _config.get_value("bindings", action_name)
		if value is InputEvent and InputMap.has_action(action_name):
			InputMap.action_erase_events(action_name)
			InputMap.action_add_event(action_name, value)
