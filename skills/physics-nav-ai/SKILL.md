---
name: physics-nav-ai
description: Godot physics, collision, raycasts, navigation and enemy AI - state machines, steering, pathfinding, line of sight, behaviour trees, spawners, difficulty scaling.
---

# Physics, navigation & AI

- **Bodies**: `CharacterBody` for controlled actors, `RigidBody` for props, `StaticBody/AnimatableBody` for level, `Area` for triggers/hitboxes. Use `PhysicsServer` layers consistently (see layer names).
- **Queries**: `RayCast2D/3D` nodes for fixed probes, `PhysicsDirectSpaceState2D.intersect_ray` for one-offs; shape casts for sweeps. Run in `_physics_process`.
- **Navigation**: `NavigationRegion2D/3D` + `NavigationAgent`: set `target_position`, read `get_next_path_position()`, move with `velocity`, enable avoidance for crowds; rebake after level changes.
- **AI architecture**: finite state machine (`state_machine` + `state` templates): Idle -> Patrol -> Chase -> Attack -> Stunned -> Dead. Add senses as components: vision cone (`Area` + raycast LOS), hearing radius, memory timer.
- **Steering**: seek/flee/arrive with `velocity.move_toward`; separation to avoid stacking.
- **Spawning**: spawner nodes with budgets (max alive), waves in `Resource` data, `object_pool` template for bullets.
- **Difficulty**: scale HP/speed/spawn rate by a single `difficulty` float; telegraph attacks (0.3-0.6 s) so deaths feel fair.
- **Debug**: `Debug > Visible Collision Shapes / Navigation`; print AI state names above heads in a debug build.
