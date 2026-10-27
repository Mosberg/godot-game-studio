extends Node
## Scripted playtest bot (autoload as "PlaytestRunner"). Inactive unless launched with a user arg:
##   godot --path . --fixed-fps 60 --quit-after 3600 -- --playtest=res://tests/plans/jump.json
## (the godot_run_project tool: extra_args=["--", "--playtest=res://tests/plans/jump.json"])
##
## Plan format (JSON):
##   {"name": "can jump", "steps": [
##      {"wait": 0.5},
##      {"press": "move_right", "hold": 1.0},          // hold an action for N seconds
##      {"tap": "jump"},                                // press for one physics frame
##      {"click": [160, 90]},                           // left click at viewport position
##      {"assert": {"node": "/root/Main/Player", "prop": "position.x", "op": ">", "value": 50}},
##      {"dump": ["/root/Main/Player:position", "/root/Main/Player:velocity"]},
##      {"screenshot": "user://shots/after_jump.png"},  // needs a real renderer (not --headless)
##      {"log": "reached the ledge"}
##   ]}
## ops: ==, !=, >, <, >=, <=, approx.   Ends by printing @@PLAYTEST@@{json} and exiting with code 0/1.

var _results: Array = []
var _logs: Array = []
var _failed: int = 0
var _plan_name: String = "unnamed"


func _ready() -> void:
	var plan_path: String = ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--playtest"):
			plan_path = arg.get_slice("=", 1) if "=" in arg else ""
			if plan_path == "":
				plan_path = "res://tests/plans/default.json"
	if plan_path == "":
		queue_free()
		return
	process_mode = Node.PROCESS_MODE_ALWAYS
	_run.call_deferred(plan_path)


func _run(plan_path: String) -> void:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(plan_path))
	if not (parsed is Dictionary):
		_finish("could not read plan %s" % plan_path)
		return
	var plan: Dictionary = parsed
	_plan_name = str(plan.get("name", plan_path.get_file()))
	await get_tree().process_frame
	var index: int = 0
	for step in plan.get("steps", []):
		if step is Dictionary:
			await _do_step(step as Dictionary, index)
		index += 1
	_finish("")


func _do_step(step: Dictionary, index: int) -> void:
	if step.has("wait"):
		await get_tree().create_timer(float(step["wait"])).timeout
	elif step.has("press"):
		var action: String = str(step["press"])
		Input.action_press(action)
		await get_tree().create_timer(float(step.get("hold", 0.1))).timeout
		Input.action_release(action)
	elif step.has("tap"):
		var tap_action: String = str(step["tap"])
		Input.action_press(tap_action)
		await get_tree().physics_frame
		await get_tree().physics_frame
		Input.action_release(tap_action)
	elif step.has("click"):
		var pos: Array = step["click"]
		var event: InputEventMouseButton = InputEventMouseButton.new()
		event.button_index = MOUSE_BUTTON_LEFT
		event.position = Vector2(float(pos[0]), float(pos[1]))
		event.pressed = true
		Input.parse_input_event(event)
		await get_tree().process_frame
		var release: InputEventMouseButton = event.duplicate() as InputEventMouseButton
		release.pressed = false
		Input.parse_input_event(release)
	elif step.has("assert"):
		_check(step["assert"] as Dictionary, index)
	elif step.has("dump"):
		for path in step["dump"]:
			var node_path: String = str(path)
			var node: Node = get_node_or_null(NodePath(node_path.get_slice(":", 0)))
			var prop: String = node_path.substr(node_path.find(":") + 1) if ":" in node_path else ""
			_logs.append("%s = %s" % [node_path, str(node.get_indexed(NodePath(prop))) if node != null else "<missing node>"])
	elif step.has("screenshot"):
		await RenderingServer.frame_post_draw
		var image: Image = get_viewport().get_texture().get_image()
		if image != null and not image.is_empty():
			var out: String = str(step["screenshot"])
			DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out.get_base_dir()))
			image.save_png(out)
			_logs.append("screenshot -> %s" % ProjectSettings.globalize_path(out))
		else:
			_logs.append("screenshot skipped (no renderer; run without --headless)")
	elif step.has("log"):
		_logs.append(str(step["log"]))


func _check(spec: Dictionary, index: int) -> void:
	var node_path: String = str(spec.get("node", ""))
	var node: Node = get_node_or_null(NodePath(node_path))
	var label: String = "step %d: %s %s %s %s" % [index, node_path, spec.get("prop", ""), spec.get("op", "=="), str(spec.get("value"))]
	if node == null:
		_record(false, label + " (node not found)")
		return
	var prop: String = str(spec.get("prop", "")).replace(".", ":")
	var actual: Variant = node.get_indexed(NodePath(prop)) if prop != "" else node
	var expected: Variant = spec.get("value")
	var op: String = str(spec.get("op", "=="))
	var passed: bool = false
	match op:
		"==":
			passed = actual == expected
		"!=":
			passed = actual != expected
		">":
			passed = float(actual) > float(expected)
		"<":
			passed = float(actual) < float(expected)
		">=":
			passed = float(actual) >= float(expected)
		"<=":
			passed = float(actual) <= float(expected)
		"approx":
			passed = is_equal_approx(float(actual), float(expected))
	_record(passed, "%s (actual: %s)" % [label, str(actual)])


func _record(passed: bool, label: String) -> void:
	_results.append({"pass": passed, "check": label})
	if not passed:
		_failed += 1


func _finish(error: String) -> void:
	var report: Dictionary = {
		"plan": _plan_name, "passed": _failed == 0 and error == "", "failed": _failed,
		"error": error, "results": _results, "log": _logs,
	}
	print("@@PLAYTEST@@" + JSON.stringify(report))
	get_tree().quit(0 if report["passed"] else 1)
