class_name ObjectPool
extends Node
## Reuses nodes instead of instantiating/freeing them (bullets, particles, floating text).
## Poolable nodes may implement `on_acquire()` / `on_release()` hooks.
##   var bullet: Node2D = pool.acquire(parent_node) as Node2D
##   pool.release(bullet)

@export var scene: PackedScene
@export var initial_size: int = 16
@export var grow_when_empty: bool = true

var _free: Array[Node] = []
var _all_count: int = 0


func _ready() -> void:
	for i in initial_size:
		_free.append(_create())


func _create() -> Node:
	var node: Node = scene.instantiate()
	_all_count += 1
	return node


func acquire(parent: Node = null) -> Node:
	var node: Node = null
	if not _free.is_empty():
		node = _free.pop_back()
	elif grow_when_empty:
		node = _create()
	if node == null:
		return null
	var target: Node = parent if parent != null else self
	if node.get_parent() != target:
		if node.get_parent() != null:
			node.get_parent().remove_child(node)
		target.add_child(node)
	node.process_mode = Node.PROCESS_MODE_INHERIT
	if node is CanvasItem:
		(node as CanvasItem).show()
	if node.has_method("on_acquire"):
		node.call("on_acquire")
	return node


func release(node: Node) -> void:
	if node == null or _free.has(node):
		return
	if node.has_method("on_release"):
		node.call("on_release")
	node.process_mode = Node.PROCESS_MODE_DISABLED
	if node is CanvasItem:
		(node as CanvasItem).hide()
	_free.append(node)


func free_count() -> int:
	return _free.size()
