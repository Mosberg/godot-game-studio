---
name: audio-for-games
description: Create and integrate game audio in Godot - procedural SFX/music generation, formats, buses, mixing levels, variation, loops, and audio manager patterns.
---

# Audio for games

- Generate: `audio_sfx` (variations!), `audio_melody`, `audio_chiptune`; convert/normalise with `audio_convert` (ffmpeg).
- Formats: short SFX `.wav`; music/ambience `.ogg`. Loop: enable import Loop, or `AudioStreamOggVorbis.loop`.
- Buses: Master -> Music, SFX, UI (+ Reverb/Low-pass on a "Muffle" bus for pause/underwater). Persist volumes via `settings_manager`.
- Levels: SFX peak ~ -6 dBFS, music ~ -14 LUFS, UI quieter. Pitch jitter +-5%, random pick from variations, limit concurrent copies (pool of 8-16 players).
- 3D: `AudioStreamPlayer3D` with attenuation; 2D: `AudioStreamPlayer2D` with max distance.
- Music: crossfade with two players; intensity layers by muting stems; stingers for events.
- Verify import in headless run; reimport after replacing files (`godot_import`).
