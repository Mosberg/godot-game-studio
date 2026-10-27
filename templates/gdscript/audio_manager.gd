extends Node
## Audio autoload ("Audio"): pooled one-shot SFX, crossfading music, bus volume helpers.
## Creates the "Music" and "SFX" buses at runtime if your project has no bus layout yet.
##   Audio.play_sfx(preload("res://assets/audio/sfx/jump.wav"))
##   Audio.play_music(preload("res://assets/audio/music/theme.ogg"), 1.5)

const SFX_POOL_SIZE: int = 12
const MUSIC_BUS: StringName = &"Music"
const SFX_BUS: StringName = &"SFX"

var _sfx_players: Array[AudioStreamPlayer] = []
var _music_players: Array[AudioStreamPlayer] = []
var _active_music: int = 0
var _music_tween: Tween = null


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_ensure_bus(MUSIC_BUS)
	_ensure_bus(SFX_BUS)
	for i in SFX_POOL_SIZE:
		var p: AudioStreamPlayer = AudioStreamPlayer.new()
		p.bus = SFX_BUS
		add_child(p)
		_sfx_players.append(p)
	for i in 2:
		var m: AudioStreamPlayer = AudioStreamPlayer.new()
		m.bus = MUSIC_BUS
		m.volume_db = -80.0
		add_child(m)
		_music_players.append(m)


func _ensure_bus(bus_name: StringName) -> void:
	if AudioServer.get_bus_index(bus_name) != -1:
		return
	AudioServer.add_bus()
	var idx: int = AudioServer.bus_count - 1
	AudioServer.set_bus_name(idx, bus_name)
	AudioServer.set_bus_send(idx, &"Master")


func play_sfx(stream: AudioStream, volume_db: float = 0.0, pitch_variation: float = 0.05) -> AudioStreamPlayer:
	if stream == null:
		return null
	for p in _sfx_players:
		if not p.playing:
			p.stream = stream
			p.volume_db = volume_db
			p.pitch_scale = 1.0 + randf_range(-pitch_variation, pitch_variation)
			p.play()
			return p
	return null # pool exhausted: drop the sound rather than cut another one off


func play_music(stream: AudioStream, fade_time: float = 1.0, volume_db: float = 0.0) -> void:
	var current: AudioStreamPlayer = _music_players[_active_music]
	if current.stream == stream and current.playing:
		return
	if _music_tween != null and _music_tween.is_valid():
		_music_tween.kill()
	var next_index: int = 1 - _active_music
	var incoming: AudioStreamPlayer = _music_players[next_index]
	incoming.stream = stream
	incoming.volume_db = -80.0
	if stream != null:
		incoming.play()
	_music_tween = create_tween().set_parallel(true)
	_music_tween.tween_property(incoming, "volume_db", volume_db, fade_time)
	_music_tween.tween_property(current, "volume_db", -80.0, fade_time)
	_music_tween.chain().tween_callback(current.stop)
	_active_music = next_index


func stop_music(fade_time: float = 1.0) -> void:
	play_music(null, fade_time)


## Linear volume 0.0 - 1.0 (what a settings slider should use).
func set_bus_volume(bus_name: StringName, linear: float) -> void:
	var idx: int = AudioServer.get_bus_index(bus_name)
	if idx == -1:
		return
	AudioServer.set_bus_volume_db(idx, linear_to_db(clampf(linear, 0.0, 1.0)))
	AudioServer.set_bus_mute(idx, linear <= 0.001)


func get_bus_volume(bus_name: StringName) -> float:
	var idx: int = AudioServer.get_bus_index(bus_name)
	return 1.0 if idx == -1 else db_to_linear(AudioServer.get_bus_volume_db(idx))
