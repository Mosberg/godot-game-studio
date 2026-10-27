class_name State
extends Node
## Base class for a state in StateMachine. Add State children (named e.g. "Idle", "Run") under a
## StateMachine node. Request changes with: transition_requested.emit(&"run")

signal transition_requested(target_state: StringName)

## The node this state machine controls (set by StateMachine).
var actor: Node = null


func enter(_previous_state: StringName) -> void:
	pass


func exit(_next_state: StringName) -> void:
	pass


func update(_delta: float) -> void:
	pass


func physics_update(_delta: float) -> void:
	pass


func handle_input(_event: InputEvent) -> void:
	pass
