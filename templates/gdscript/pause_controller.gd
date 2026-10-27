extends Node
## Pause toggle. Add as a child of your level or a UI CanvasLayer.
## Uses the "pause" action when it exists, otherwise ui_cancel (Esc).
## Assign `pause_menu` (a Control) to show/hide it. Everything else stops while paused.

signal paused_changed(is_paused: bool)

@export var pause_menu: Control
@export var action_name: StringName = &"pause"


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS # keep receiving input while the tree is paused
	if pause_menu != null:
		pause_menu.process_mode = Node.PROCESS_MODE_ALWAYS
		pause_menu.hide()


func _unhandled_input(event: InputEvent) -> void:
	var action: StringName = action_name if InputMap.has_action(action_name) else &"ui_cancel"
	if event.is_action_pressed(action):
		set_paused(not get_tree().paused)
		get_viewport().set_input_as_handled()


func set_paused(value: bool) -> void:
	get_tree().paused = value
	if pause_menu != null:
		pause_menu.visible = value
	paused_changed.emit(value)
