---
name: save-load-systems
description: Implement robust save/load in Godot - settings and game saves, JSON/ConfigFile/Resource formats, versioning and migration, autosave, slots, corruption safety and cloud-friendly layout.
---

# Save / load

- Paths: `user://` only. Settings -> `ConfigFile` (`user://settings.cfg`); game state -> JSON (`user://saves/slot_1.json`) or a `Resource` subclass saved with `ResourceSaver` (never load untrusted `.tres`/`.res` - they can embed scripts; prefer JSON for player-shareable saves).
- Template `save_manager`: slots, `save_game()`, `load_game()`, `has_save()`, atomic write (write temp -> rename), version field + `migrate(data)`.
- Persist via a `Persist` group: nodes implement `to_save() -> Dictionary` and `from_save(d)`; manager gathers/applies. Store scene path, player stats, flags, inventory ids (not node refs).
- Autosave on checkpoints/scene change; show a save icon; keep last 2 backups.
- Test round-trip in `godot_run_tests`: save -> mutate -> load -> assert equality; also load a v1 file with the v2 code.
