@tool
extends EditorPlugin
## Claude Bridge - newline-delimited JSON over TCP, bound to 127.0.0.1 only.
##   request : {"cmd": "scene_tree", "args": {...}, "token": "..."}
##   response: {"ok": true, "result": ...} or {"ok": false, "error": "..."}
##
## Environment (optional):
##   GODOT_EDITOR_PORT           listening port (default 9877)
##   GODOT_EDITOR_TOKEN          if set, every request must carry the same "token"
##   GODOT_EDITOR_ALLOW_EXECUTE  set to 0 to disable the arbitrary-code "execute" command

const DEFAULT_PORT := 9877

var _server: TCPServer = TCPServer.new()
var _clients: Array = []
var _buffers: Dictionary = {}
var _token: String = ""
var _allow_execute: bool = true


func _enter_tree() -> void:
	var port: int = DEFAULT_PORT
	if OS.has_environment("GODOT_EDITOR_PORT"):
		port = int(OS.get_environment("GODOT_EDITOR_PORT"))
	if OS.has_environment("GODOT_EDITOR_TOKEN"):
		_token = OS.get_environment("GODOT_EDITOR_TOKEN")
	if OS.has_environment("GODOT_EDITOR_ALLOW_EXECUTE"):
		_allow_execute = OS.get_environment("GODOT_EDITOR_ALLOW_EXECUTE") != "0"
	var err: int = _server.listen(port, "127.0.0.1")
	if err != OK:
		push_warning("Claude Bridge: cannot listen on port %d (%s)" % [port, error_string(err)])
	else:
		print("Claude Bridge listening on 127.0.0.1:%d" % port)
	set_process(true)


func _exit_tree() -> void:
	for c in _clients:
		var peer: StreamPeerTCP = c
		peer.disconnect_from_host()
	_clients.clear()
	_buffers.clear()
	_server.stop()


func _process(_delta: float) -> void:
	if not _server.is_listening():
		return
	while _server.is_connection_available():
		var new_peer: StreamPeerTCP = _server.take_connection()
		_clients.append(new_peer)
		_buffers[new_peer] = PackedByteArray()
	for c in _clients.duplicate():
		var peer: StreamPeerTCP = c
		peer.poll()
		if peer.get_status() != StreamPeerTCP.STATUS_CONNECTED:
			_clients.erase(peer)
			_buffers.erase(peer)
			continue
		var available: int = peer.get_available_bytes()
		if available > 0:
			var chunk: Array = peer.get_data(available)
			if chunk[0] == OK:
				var buf: PackedByteArray = _buffers[peer]
				buf.append_array(chunk[1])
				_buffers[peer] = buf
		_drain(peer)


func _drain(peer: StreamPeerTCP) -> void:
	var buf: PackedByteArray = _buffers.get(peer, PackedByteArray())
	var nl: int = buf.find(10)
	while nl >= 0:
		var line: String = buf.slice(0, nl).get_string_from_utf8()
		buf = buf.slice(nl + 1)
		_buffers[peer] = buf
		_send(peer, _handle_line(line))
		nl = buf.find(10)
	_buffers[peer] = buf


func _send(peer: StreamPeerTCP, response: Dictionary) -> void:
	var text: String = JSON.stringify(response) + "\n"
	peer.put_data(text.to_utf8_buffer())


func _ok(result: Variant = null) -> Dictionary:
	return {"ok": true, "result": _jsonable(result)}


func _err(message: String) -> Dictionary:
	return {"ok": false, "error": message}


func _handle_line(line: String) -> Dictionary:
	if line.strip_edges() == "":
		return _err("empty request")
	var parsed: Variant = JSON.parse_string(line)
	if not (parsed is Dictionary):
		return _err("request must be a JSON object")
	var req: Dictionary = parsed
	if _token != "" and str(req.get("token", "")) != _token:
		return _err("bad or missing token")
	var args: Dictionary = {}
	if req.get("args") is Dictionary:
		args = req["args"]
	return _dispatch(str(req.get("cmd", "")), args)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
func _scene_root() -> Node:
	return EditorInterface.get_edited_scene_root()


func _node(path: String) -> Node:
	var root: Node = _scene_root()
	if root == null:
		return null
	if path == "" or path == "." or path == str(root.name):
		return root
	return root.get_node_or_null(NodePath(path))


func _prop_type(obj: Object, prop: String) -> int:
	for p in obj.get_property_list():
		if p["name"] == prop:
			return int(p["type"])
	return TYPE_NIL


func _parse_value(v: Variant, want_type: int = TYPE_NIL) -> Variant:
	if v is String:
		var s: String = v
		var t: String = s.strip_edges()
		if t.begins_with("res://") or t.begins_with("uid://"):
			return load(t)
		if want_type == TYPE_COLOR:
			return Color.from_string(t, Color.WHITE)
		if want_type == TYPE_STRING or want_type == TYPE_STRING_NAME or want_type == TYPE_NODE_PATH:
			if want_type == TYPE_NODE_PATH:
				return NodePath(s)
			if want_type == TYPE_STRING_NAME:
				return StringName(s)
			return s
		if t == "true":
			return true
		if t == "false":
			return false
		if t == "null":
			return null
		for prefix in ["Vector", "Color(", "Rect", "Transform", "Basis", "Quaternion", "Plane", "AABB", "Packed", "NodePath(", "&\"", "Object(", "Array[", "Dictionary("]:
			if t.begins_with(prefix):
				return str_to_var(t)
		return s
	if v is Array:
		var a: Array = v
		match want_type:
			TYPE_VECTOR2:
				if a.size() >= 2:
					return Vector2(float(a[0]), float(a[1]))
			TYPE_VECTOR2I:
				if a.size() >= 2:
					return Vector2i(int(a[0]), int(a[1]))
			TYPE_VECTOR3:
				if a.size() >= 3:
					return Vector3(float(a[0]), float(a[1]), float(a[2]))
			TYPE_VECTOR3I:
				if a.size() >= 3:
					return Vector3i(int(a[0]), int(a[1]), int(a[2]))
			TYPE_COLOR:
				if a.size() >= 3:
					return Color(float(a[0]), float(a[1]), float(a[2]), float(a[3]) if a.size() > 3 else 1.0)
		return a
	return v


func _jsonable(v: Variant) -> Variant:
	match typeof(v):
		TYPE_NIL, TYPE_BOOL, TYPE_INT, TYPE_FLOAT, TYPE_STRING:
			return v
		TYPE_STRING_NAME, TYPE_NODE_PATH:
			return str(v)
		TYPE_ARRAY, TYPE_PACKED_STRING_ARRAY, TYPE_PACKED_INT32_ARRAY, TYPE_PACKED_FLOAT32_ARRAY:
			var out: Array = []
			for x in v:
				out.append(_jsonable(x))
			return out
		TYPE_DICTIONARY:
			var d: Dictionary = {}
			for k in v:
				d[str(k)] = _jsonable(v[k])
			return d
		TYPE_OBJECT:
			if v == null:
				return null
			if v is Node:
				return "Node:" + str(v.get_path())
			if v is Resource and v.resource_path != "":
				return v.resource_path
			return str(v)
		_:
			return var_to_str(v)


func _instantiate_type(type_name: String) -> Node:
	if ClassDB.class_exists(type_name) and ClassDB.can_instantiate(type_name):
		var obj: Variant = ClassDB.instantiate(type_name)
		if obj is Node:
			return obj
		return null
	for entry in ProjectSettings.get_global_class_list():
		if entry["class"] == type_name:
			var scr: Script = load(entry["path"])
			var inst: Variant = scr.new()
			if inst is Node:
				return inst
	return null


func _set_owner_recursive(n: Node, root: Node) -> void:
	for c in n.get_children():
		if c.scene_file_path == "":
			c.owner = root
			_set_owner_recursive(c, root)


func _dump(n: Node, root: Node, depth: int, max_depth: int) -> Dictionary:
	var d: Dictionary = {"name": str(n.name), "type": n.get_class(), "path": str(root.get_path_to(n))}
	var s: Variant = n.get_script()
	if s != null and s is Script:
		d["script"] = (s as Script).resource_path
	if n != root and n.scene_file_path != "":
		d["scene"] = n.scene_file_path
	if depth < max_depth:
		var kids: Array = []
		for c in n.get_children():
			kids.append(_dump(c, root, depth + 1, max_depth))
		if kids.size() > 0:
			d["children"] = kids
	return d


func _normalize_indent(code: String) -> String:
	var out: PackedStringArray = PackedStringArray()
	for line in code.replace("\r\n", "\n").split("\n"):
		var spaces: int = 0
		while spaces < line.length() and line[spaces] == " ":
			spaces += 1
		if spaces > 0:
			out.append("\t".repeat(spaces / 4) + " ".repeat(spaces % 4) + line.substr(spaces))
		else:
			out.append(line)
	return "\n".join(out)


func _abs_path(p: String) -> String:
	if p.begins_with("res://") or p.begins_with("user://"):
		return ProjectSettings.globalize_path(p)
	return p


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
func _dispatch(cmd: String, a: Dictionary) -> Dictionary:
	match cmd:
		"ping":
			var root: Node = _scene_root()
			return _ok({
				"version": Engine.get_version_info(),
				"project": ProjectSettings.get_setting("application/config/name"),
				"scene": root.scene_file_path if root != null else "",
				"scene_root": str(root.name) if root != null else "",
				"playing": EditorInterface.is_playing_scene(),
				"open_scenes": Array(EditorInterface.get_open_scenes()),
			})
		"get_open_scenes":
			return _ok(Array(EditorInterface.get_open_scenes()))
		"open_scene":
			var path: String = str(a.get("path", ""))
			if not FileAccess.file_exists(path):
				return _err("scene not found: " + path)
			EditorInterface.open_scene_from_path(path)
			return _ok(path)
		"reload_scene":
			EditorInterface.reload_scene_from_path(str(a.get("path", "")))
			return _ok(true)
		"new_scene":
			return _cmd_new_scene(a)
		"save_scene":
			var e: int = EditorInterface.save_scene()
			return _ok(true) if e == OK else _err("save failed: " + error_string(e))
		"scene_tree":
			var root_n: Node = _scene_root()
			if root_n == null:
				return _err("no scene is open")
			return _ok(_dump(root_n, root_n, 0, int(a.get("depth", 12))))
		"get_selection":
			var paths: Array = []
			var scene_root: Node = _scene_root()
			for n in EditorInterface.get_selection().get_selected_nodes():
				paths.append(str(scene_root.get_path_to(n)) if scene_root != null else str(n.name))
			return _ok(paths)
		"select_node":
			var n2: Node = _node(str(a.get("path", ".")))
			if n2 == null:
				return _err("node not found")
			var sel: EditorSelection = EditorInterface.get_selection()
			sel.clear()
			sel.add_node(n2)
			EditorInterface.edit_node(n2)
			return _ok(true)
		"add_node":
			return _cmd_add_node(a)
		"instance_scene":
			return _cmd_instance_scene(a)
		"remove_node":
			var victim: Node = _node(str(a.get("path", "")))
			if victim == null or victim == _scene_root():
				return _err("node not found or is the scene root")
			victim.get_parent().remove_child(victim)
			victim.queue_free()
			_mark_dirty()
			return _ok(true)
		"rename_node":
			var rn: Node = _node(str(a.get("path", "")))
			if rn == null:
				return _err("node not found")
			rn.name = str(a.get("name", rn.name))
			_mark_dirty()
			return _ok(str(rn.name))
		"reparent_node":
			var mv: Node = _node(str(a.get("path", "")))
			var np: Node = _node(str(a.get("new_parent", ".")))
			if mv == null or np == null or mv == _scene_root():
				return _err("node or new parent not found")
			mv.reparent(np, true)
			mv.owner = _scene_root()
			_set_owner_recursive(mv, _scene_root())
			_mark_dirty()
			return _ok(str(_scene_root().get_path_to(mv)))
		"set_property":
			return _cmd_set_property(a)
		"get_property":
			var gn: Node = _node(str(a.get("path", ".")))
			if gn == null:
				return _err("node not found")
			return _ok(gn.get_indexed(NodePath(str(a.get("property", "")))))
		"set_script":
			var sn: Node = _node(str(a.get("path", ".")))
			if sn == null:
				return _err("node not found")
			var scr: Variant = load(str(a.get("script", "")))
			if scr == null:
				return _err("script not found")
			sn.set_script(scr)
			_mark_dirty()
			return _ok(true)
		"run_scene":
			if str(a.get("path", "")) != "":
				EditorInterface.play_custom_scene(str(a["path"]))
			else:
				EditorInterface.play_current_scene()
			return _ok(true)
		"run_main":
			EditorInterface.play_main_scene()
			return _ok(true)
		"stop":
			EditorInterface.stop_playing_scene()
			return _ok(true)
		"is_playing":
			return _ok(EditorInterface.is_playing_scene())
		"screenshot":
			return _cmd_screenshot(a)
		"execute":
			return _cmd_execute(a)
		"filesystem_scan":
			EditorInterface.get_resource_filesystem().scan()
			return _ok(true)
		"reimport":
			var files: PackedStringArray = PackedStringArray()
			for p in a.get("paths", []):
				files.append(str(p))
			EditorInterface.get_resource_filesystem().reimport_files(files)
			return _ok(files.size())
		"set_project_setting":
			ProjectSettings.set_setting(str(a.get("name", "")), _parse_value(a.get("value")))
			var se: int = ProjectSettings.save()
			return _ok(true) if se == OK else _err("save failed: " + error_string(se))
		_:
			return _err("unknown command '%s'" % cmd)


func _mark_dirty() -> void:
	if EditorInterface.has_method("mark_scene_as_unsaved"):
		EditorInterface.call("mark_scene_as_unsaved")


func _cmd_new_scene(a: Dictionary) -> Dictionary:
	var path: String = str(a.get("path", ""))
	var type_name: String = str(a.get("type", "Node2D"))
	if path == "":
		return _err("path required")
	var root_node: Node = _instantiate_type(type_name)
	if root_node == null:
		return _err("cannot instantiate " + type_name)
	root_node.name = str(a.get("name", path.get_file().get_basename().to_pascal_case()))
	var packed: PackedScene = PackedScene.new()
	packed.pack(root_node)
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(path.get_base_dir()))
	var e: int = ResourceSaver.save(packed, path)
	root_node.free()
	if e != OK:
		return _err("save failed: " + error_string(e))
	EditorInterface.get_resource_filesystem().scan()
	EditorInterface.open_scene_from_path(path)
	return _ok(path)


func _cmd_add_node(a: Dictionary) -> Dictionary:
	var root: Node = _scene_root()
	if root == null:
		return _err("no scene is open")
	var parent: Node = _node(str(a.get("parent", ".")))
	if parent == null:
		return _err("parent not found: " + str(a.get("parent", ".")))
	var type_name: String = str(a.get("type", "Node"))
	var node: Node = _instantiate_type(type_name)
	if node == null:
		return _err("cannot instantiate node type '%s'" % type_name)
	node.name = str(a.get("name", type_name))
	parent.add_child(node, true)
	node.owner = root
	if str(a.get("script", "")) != "":
		var scr: Variant = load(str(a["script"]))
		if scr != null:
			node.set_script(scr)
	var props: Dictionary = {}
	if a.get("properties") is Dictionary:
		props = a["properties"]
	var failed: Array = []
	for key in props:
		var prop: String = str(key)
		var typ: int = _prop_type(node, prop)
		node.set_indexed(NodePath(prop), _parse_value(props[key], typ))
		if typ == TYPE_NIL and not (prop in node) and not prop.contains(":"):
			failed.append(prop)
	_mark_dirty()
	return _ok({"path": str(root.get_path_to(node)), "name": str(node.name), "unknown_properties": failed})


func _cmd_instance_scene(a: Dictionary) -> Dictionary:
	var root: Node = _scene_root()
	if root == null:
		return _err("no scene is open")
	var parent: Node = _node(str(a.get("parent", ".")))
	if parent == null:
		return _err("parent not found")
	var packed: Variant = load(str(a.get("scene", "")))
	if not (packed is PackedScene):
		return _err("not a PackedScene: " + str(a.get("scene", "")))
	var inst: Node = (packed as PackedScene).instantiate()
	if str(a.get("name", "")) != "":
		inst.name = str(a["name"])
	parent.add_child(inst, true)
	inst.owner = root
	_mark_dirty()
	return _ok({"path": str(root.get_path_to(inst))})


func _cmd_set_property(a: Dictionary) -> Dictionary:
	var node: Node = _node(str(a.get("path", ".")))
	if node == null:
		return _err("node not found: " + str(a.get("path", ".")))
	var prop: String = str(a.get("property", ""))
	if prop == "":
		return _err("property required")
	var base: String = prop.split(":")[0]
	var typ: int = _prop_type(node, base)
	if typ == TYPE_NIL and not (base in node):
		return _err("node '%s' (%s) has no property '%s'" % [str(node.name), node.get_class(), base])
	node.set_indexed(NodePath(prop), _parse_value(a.get("value"), typ if not prop.contains(":") else TYPE_NIL))
	_mark_dirty()
	return _ok(node.get_indexed(NodePath(prop)))


func _cmd_screenshot(a: Dictionary) -> Dictionary:
	var target: String = str(a.get("target", "editor"))
	var path: String = _abs_path(str(a.get("path", "user://claude_shot.png")))
	var img: Image = null
	match target:
		"2d":
			img = EditorInterface.get_editor_viewport_2d().get_texture().get_image()
		"3d":
			img = EditorInterface.get_editor_viewport_3d(0).get_texture().get_image()
		"screen", "game":
			if DisplayServer.has_method("screen_get_image"):
				img = DisplayServer.call("screen_get_image", DisplayServer.window_get_current_screen())
		_:
			img = EditorInterface.get_base_control().get_viewport().get_texture().get_image()
	if img == null:
		return _err("could not capture '%s' (viewport unavailable)" % target)
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var e: int = img.save_png(path)
	if e != OK:
		return _err("save_png failed: " + error_string(e))
	return _ok({"path": path, "width": img.get_width(), "height": img.get_height()})


func _cmd_execute(a: Dictionary) -> Dictionary:
	if not _allow_execute:
		return _err("execute is disabled (GODOT_EDITOR_ALLOW_EXECUTE=0)")
	var code: String = _normalize_indent(str(a.get("code", "")))
	var src: String = "@tool\nextends RefCounted\n\nfunc run(editor, root):\n"
	for line in code.split("\n"):
		src += "\t" + line + "\n"
	src += "\treturn null\n"
	var scr: GDScript = GDScript.new()
	scr.source_code = src
	var e: int = scr.reload()
	if e != OK:
		return _err("compile error (%s). The code runs as the body of func run(editor, root)." % error_string(e))
	var obj: Object = scr.new()
	var result: Variant = obj.call("run", EditorInterface, _scene_root())
	return _ok(result)
