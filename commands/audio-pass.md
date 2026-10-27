---
description: Audio pass - generate SFX and music, wire an audio manager, buses and volume settings
argument-hint: [mood or style, e.g. "tense chiptune"]
---

Run an audio pass: $ARGUMENTS

As **audio-designer**: list needed sounds from the code (`godot_search` for actions: jump, hit, pickup, ui), generate them with `audio_sfx` (3 variations each), compose music with `audio_chiptune`, add/configure the `audio_manager` autoload and buses, hook calls into gameplay via the Events bus, verify import, and report levels.
