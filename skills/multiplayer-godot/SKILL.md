---
name: multiplayer-godot
description: Add multiplayer to a Godot 4 game - ENet/WebSocket/WebRTC peers, MultiplayerSpawner/Synchronizer, RPCs, authority, lobbies, lag handling, and testing with multiple instances.
---

# Multiplayer

- Pick topology: **listen-server** (host plays) via `ENetMultiplayerPeer` is the simplest; dedicated server = export with `--headless` feature; browsers need WebSocket/WebRTC.
- Setup: `peer.create_server(port, max_clients)` / `create_client(ip, port)`; `multiplayer.multiplayer_peer = peer`; listen to `peer_connected`, `peer_disconnected`, `connected_to_server`, `connection_failed`.
- **Authority**: server owns game state; each player node's `set_multiplayer_authority(peer_id)`; clients send *input*, server simulates and replicates.
- **Nodes**: `MultiplayerSpawner` (spawn_path + spawnable scenes), `MultiplayerSynchronizer` (replicate `position`, `velocity`, animation state with interpolation).
- **RPC**: `@rpc("any_peer","call_local","reliable") func fire(dir: Vector2)`; validate on the server (`multiplayer.get_remote_sender_id()`), never trust client positions blindly.
- **Smoothness**: interpolate remote entities, small client-side prediction for the local player, tick rate 20-30 Hz for state.
- **Test**: Debug > Run Multiple Instances (editor) or launch several `godot_run_project` processes (one as `--server`). Simulate latency with OS tools / `ENetConnection` timeouts.
- Security: rate-limit RPCs, validate ranges, keep secrets server-side. NAT traversal needs a relay/UPnP - say so to the user.
