class_name StateMachine
extends Node
## Node-based finite state machine. Children must extend State. State keys are the lower-case node names,
## so a child called "Idle" is addressed as &"idle".

signal state_changed(from_state: StringName, to_state: StringName)

@export var initial_state: State
## Defaults to the parent node when left empty.
@export var actor: Node

var current_state: State = null
var current_name: StringName = &""
var states: Dictionary = {}


func _ready() -> void:
	if actor == null:
		actor = get_parent()
	for child in get_children():
		if child is State:
			var state: State = child
			states[StringName(String(state.name).to_lower())] = state
			state.actor = actor
			state.transition_requested.connect(_on_transition_requested)
	if initial_state != null:
		current_state = initial_state
		current_name = StringName(String(initial_state.name).to_lower())
		current_state.enter(&"")


func _process(delta: float) -> void:
	if current_state != null:
		current_state.update(delta)


func _physics_process(delta: float) -> void:
	if current_state != null:
		current_state.physics_update(delta)


func _unhandled_input(event: InputEvent) -> void:
	if current_state != null:
		current_state.handle_input(event)


func transition_to(target: StringName) -> void:
	if not states.has(target):
		push_warning("StateMachine: unknown state '%s' (have: %s)" % [target, ", ".join(states.keys())])
		return
	var previous: StringName = current_name
	if current_state != null:
		current_state.exit(target)
	current_state = states[target]
	current_name = target
	current_state.enter(previous)
	state_changed.emit(previous, target)


func _on_transition_requested(target: StringName) -> void:
	transition_to(target)
