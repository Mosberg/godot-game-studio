class_name DialogueRunner
extends Node
## Data-driven dialogue (no UI). Feed it a JSON file or array; connect a UI to the signals.
## JSON format - an array of nodes:
##   [{"id": "start", "speaker": "Elder", "text": "Hello!", "next": "ask"},
##    {"id": "ask", "speaker": "Elder", "text": "Help us?",
##     "choices": [{"text": "Yes", "next": "yes"}, {"text": "No", "next": ""}]},
##    {"id": "yes", "speaker": "Elder", "text": "Thank you.", "event": "quest_accepted"}]
## An empty or missing "next" ends the dialogue. "event" is emitted as `event_triggered`.

signal line_shown(speaker: String, text: String, choices: Array)
signal event_triggered(event_name: String)
signal dialogue_started
signal dialogue_finished

var _nodes: Dictionary = {}
var _current: Dictionary = {}
var active: bool = false


func start_from_file(path: String, start_id: String = "") -> bool:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not (parsed is Array):
		push_error("DialogueRunner: '%s' is not a JSON array" % path)
		return false
	return start(parsed, start_id)


func start(nodes: Array, start_id: String = "") -> bool:
	_nodes.clear()
	for entry in nodes:
		if entry is Dictionary and entry.has("id"):
			_nodes[str(entry["id"])] = entry
	if _nodes.is_empty():
		return false
	var first: String = start_id if start_id != "" else str((nodes[0] as Dictionary)["id"])
	active = true
	dialogue_started.emit()
	_show(first)
	return true


## Call when the player presses "continue" on a line without choices.
func advance() -> void:
	if not active or _current.is_empty():
		return
	if (_current.get("choices", []) as Array).size() > 0:
		return # must call choose()
	_goto(str(_current.get("next", "")))


func choose(index: int) -> void:
	var choices: Array = _current.get("choices", [])
	if not active or index < 0 or index >= choices.size():
		return
	var choice: Dictionary = choices[index]
	if choice.has("event"):
		event_triggered.emit(str(choice["event"]))
	_goto(str(choice.get("next", "")))


func _goto(id: String) -> void:
	if id == "" or not _nodes.has(id):
		_finish()
	else:
		_show(id)


func _show(id: String) -> void:
	_current = _nodes[id]
	if _current.has("event"):
		event_triggered.emit(str(_current["event"]))
	line_shown.emit(str(_current.get("speaker", "")), str(_current.get("text", "")), _current.get("choices", []))
	if not _current.has("next") and not _current.has("choices"):
		# last line: stays visible until advance() is called, then finishes
		_current["next"] = ""


func _finish() -> void:
	active = false
	_current = {}
	dialogue_finished.emit()
