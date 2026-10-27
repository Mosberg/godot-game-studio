extends Node
## Save/load autoload ("SaveManager"). JSON on disk, atomic writes, versioned, multiple slots.
##
## Any node that should be saved joins the "saveable" group and implements:
##   func save_data() -> Dictionary        # JSON-safe values only (use encode_vector2 for vectors)
##   func load_data(data: Dictionary) -> void
## and gets a stable key through `save_key` (property) or its node path.

signal saved(slot: int)
signal loaded(slot: int)
signal save_failed(slot: int, reason: String)

const SAVE_DIR: String = "user://saves"
const FORMAT_VERSION: int = 1
const GROUP: StringName = &"saveable"

var current_slot: int = 0


func slot_path(slot: int) -> String:
	return "%s/slot_%d.json" % [SAVE_DIR, slot]


func has_save(slot: int) -> bool:
	return FileAccess.file_exists(slot_path(slot))


func list_slots() -> Array[int]:
	var result: Array[int] = []
	var dir: DirAccess = DirAccess.open(SAVE_DIR)
	if dir == null:
		return result
	for file_name in dir.get_files():
		if file_name.begins_with("slot_") and file_name.ends_with(".json"):
			result.append(int(file_name.trim_prefix("slot_").trim_suffix(".json")))
	result.sort()
	return result


func delete_save(slot: int) -> void:
	if has_save(slot):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(slot_path(slot)))


## Save arbitrary data plus the state of every node in the "saveable" group.
func save_game(slot: int, extra: Dictionary = {}) -> Error:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(SAVE_DIR))
	var payload: Dictionary = {
		"version": FORMAT_VERSION,
		"timestamp": Time.get_unix_time_from_system(),
		"scene": get_tree().current_scene.scene_file_path if get_tree().current_scene != null else "",
		"extra": extra,
		"nodes": _collect_nodes(),
	}
	var tmp_path: String = slot_path(slot) + ".tmp"
	var file: FileAccess = FileAccess.open(tmp_path, FileAccess.WRITE)
	if file == null:
		var err: Error = FileAccess.get_open_error()
		save_failed.emit(slot, error_string(err))
		return err
	file.store_string(JSON.stringify(payload, "\t"))
	file.close()
	# Atomic replace so a crash mid-write never corrupts the previous save.
	if FileAccess.file_exists(slot_path(slot)):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(slot_path(slot)))
	var rename_err: Error = DirAccess.rename_absolute(
		ProjectSettings.globalize_path(tmp_path), ProjectSettings.globalize_path(slot_path(slot)))
	if rename_err != OK:
		save_failed.emit(slot, error_string(rename_err))
		return rename_err
	current_slot = slot
	saved.emit(slot)
	return OK


## Returns the payload ("extra", "scene", "nodes", ...) or an empty Dictionary on failure.
func read_save(slot: int) -> Dictionary:
	if not has_save(slot):
		return {}
	var file: FileAccess = FileAccess.open(slot_path(slot), FileAccess.READ)
	if file == null:
		return {}
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if not (parsed is Dictionary):
		push_warning("SaveManager: slot %d is corrupt" % slot)
		return {}
	var data: Dictionary = parsed
	return _migrate(data)


## Applies saved state to nodes currently in the tree. Load the right scene first.
func load_game(slot: int) -> Dictionary:
	var data: Dictionary = read_save(slot)
	if data.is_empty():
		return {}
	_apply_nodes(data.get("nodes", {}))
	current_slot = slot
	loaded.emit(slot)
	return data


func _migrate(data: Dictionary) -> Dictionary:
	var version: int = int(data.get("version", 0))
	# Add `if version < 2: ...` upgrade steps here when FORMAT_VERSION grows.
	if version > FORMAT_VERSION:
		push_warning("SaveManager: save was written by a newer game version")
	return data


func _key_for(node: Node) -> String:
	if "save_key" in node and str(node.get("save_key")) != "":
		return str(node.get("save_key"))
	return str(node.get_path())


func _collect_nodes() -> Dictionary:
	var result: Dictionary = {}
	for node in get_tree().get_nodes_in_group(GROUP):
		if node.has_method("save_data"):
			result[_key_for(node)] = node.call("save_data")
	return result


func _apply_nodes(states: Dictionary) -> void:
	for node in get_tree().get_nodes_in_group(GROUP):
		var key: String = _key_for(node)
		if states.has(key) and node.has_method("load_data"):
			node.call("load_data", states[key])


# JSON has no vector type: use these helpers inside save_data()/load_data().
static func encode_vector2(v: Vector2) -> Array:
	return [v.x, v.y]


static func decode_vector2(a: Variant, fallback: Vector2 = Vector2.ZERO) -> Vector2:
	if a is Array and (a as Array).size() >= 2:
		return Vector2(float(a[0]), float(a[1]))
	return fallback


static func encode_vector3(v: Vector3) -> Array:
	return [v.x, v.y, v.z]


static func decode_vector3(a: Variant, fallback: Vector3 = Vector3.ZERO) -> Vector3:
	if a is Array and (a as Array).size() >= 3:
		return Vector3(float(a[0]), float(a[1]), float(a[2]))
	return fallback
