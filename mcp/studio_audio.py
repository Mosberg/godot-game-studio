"""Procedural audio for game prototyping: sfxr-style effects and tiny chiptune loops.

Pure numpy + wave module (no ffmpeg needed). Output is 16-bit mono PCM WAV.
"""
from __future__ import annotations

import wave
from pathlib import Path
from typing import Optional

import numpy as np

SR = 44100
NOTE_INDEX = {"C": 0, "C#": 1, "DB": 1, "D": 2, "D#": 3, "EB": 3, "E": 4, "F": 5, "F#": 6, "GB": 6,
              "G": 7, "G#": 8, "AB": 8, "A": 9, "A#": 10, "BB": 10, "B": 11}


def note_to_freq(name: str) -> float:
    n = name.strip().upper()
    if n in ("R", "REST", "-"):
        return 0.0
    i = 1
    if len(n) > 1 and n[1] in "#B" and len(n) > 2:
        i = 2
    base, octave = n[:i], int(n[i:])
    semitone = NOTE_INDEX[base] + (octave + 1) * 12
    return 440.0 * 2 ** ((semitone - 69) / 12)


def _wave(kind: str, phase: np.ndarray, duty: float = 0.5, rng: Optional[np.random.Generator] = None) -> np.ndarray:
    frac = phase % 1.0
    if kind == "sine":
        return np.sin(2 * np.pi * phase)
    if kind == "square":
        return np.where(frac < duty, 1.0, -1.0)
    if kind == "saw":
        return 2.0 * frac - 1.0
    if kind == "triangle":
        return 4.0 * np.abs(frac - 0.5) - 1.0
    if kind == "noise":
        gen = rng or np.random.default_rng()
        return gen.uniform(-1, 1, size=phase.shape)
    raise ValueError(f"unknown waveform {kind}")


def synth(wave_kind: str = "square", f_start: float = 440, f_end: Optional[float] = None,
          duration: float = 0.3, attack: float = 0.005, decay_power: float = 2.0,
          volume: float = 0.5, duty: float = 0.5, vibrato_hz: float = 0.0,
          vibrato_depth: float = 0.0, lowpass: float = 0.0, bitcrush: int = 0,
          seed: Optional[int] = None) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = max(1, int(duration * SR))
    t = np.linspace(0, 1, n, endpoint=False)
    f_end = f_start if f_end is None else f_end
    freq = f_start * (f_end / max(f_start, 1e-6)) ** t if f_start > 0 and f_end > 0 else np.full(n, f_start)
    if vibrato_hz > 0:
        freq = freq * (1 + vibrato_depth * np.sin(2 * np.pi * vibrato_hz * t * duration))
    phase = np.cumsum(freq) / SR
    sig = _wave(wave_kind, phase, duty, rng)
    env = (1 - t) ** decay_power
    a = max(1, int(attack * SR))
    env[:a] *= np.linspace(0, 1, min(a, n))
    sig = sig * env
    if lowpass > 0:  # simple one-pole filter, lowpass in 0..1 (higher = darker)
        alpha = min(0.999, lowpass)
        out = np.empty_like(sig)
        acc = 0.0
        for i, v in enumerate(sig):
            acc = acc * alpha + v * (1 - alpha)
            out[i] = acc
        sig = out
    if bitcrush and bitcrush > 1:
        steps = 2 ** bitcrush
        sig = np.round(sig * steps) / steps
    return sig * volume


SFX_RECIPES: dict[str, dict] = {
    "jump":      dict(wave_kind="square", f_start=300, f_end=720, duration=0.22, duty=0.35, decay_power=1.5),
    "double_jump": dict(wave_kind="square", f_start=420, f_end=950, duration=0.2, duty=0.3, decay_power=1.4),
    "coin":      dict(multi=[("square", 988, 988, 0.07), ("square", 1319, 1319, 0.28)], decay_power=1.6),
    "pickup":    dict(multi=[("triangle", 660, 660, 0.06), ("triangle", 880, 880, 0.1), ("triangle", 1100, 1100, 0.18)]),
    "powerup":   dict(multi=[("square", f, f, 0.07) for f in (392, 494, 587, 784, 988, 1175)], decay_power=1.2),
    "hit":       dict(wave_kind="noise", f_start=1, duration=0.14, decay_power=3, lowpass=0.45),
    "hurt":      dict(wave_kind="saw", f_start=420, f_end=110, duration=0.3, decay_power=1.8),
    "explosion": dict(wave_kind="noise", f_start=1, duration=0.9, decay_power=2.2, lowpass=0.93),
    "laser":     dict(wave_kind="saw", f_start=1500, f_end=180, duration=0.25, decay_power=1.5),
    "shoot":     dict(wave_kind="square", f_start=900, f_end=120, duration=0.16, duty=0.25, decay_power=2),
    "blip":      dict(wave_kind="square", f_start=700, f_end=700, duration=0.06, duty=0.5, decay_power=1.2),
    "click":     dict(wave_kind="square", f_start=1800, f_end=900, duration=0.03, decay_power=2),
    "select":    dict(multi=[("square", 523, 523, 0.05), ("square", 784, 784, 0.1)]),
    "back":      dict(multi=[("square", 784, 784, 0.05), ("square", 523, 523, 0.1)]),
    "error":     dict(wave_kind="square", f_start=200, f_end=140, duration=0.3, duty=0.5, decay_power=1.0, vibrato_hz=30, vibrato_depth=0.1),
    "death":     dict(wave_kind="saw", f_start=500, f_end=40, duration=1.0, decay_power=1.4, vibrato_hz=8, vibrato_depth=0.05),
    "footstep":  dict(wave_kind="noise", f_start=1, duration=0.07, decay_power=3, lowpass=0.8),
    "whoosh":    dict(wave_kind="noise", f_start=1, duration=0.4, decay_power=1.0, lowpass=0.85, attack=0.15),
    "splash":    dict(wave_kind="noise", f_start=1, duration=0.6, decay_power=1.6, lowpass=0.7, attack=0.02),
    "win":       dict(multi=[("square", f, f, 0.12) for f in (523, 659, 784, 1047, 784, 1047)], decay_power=1.0),
    "lose":      dict(multi=[("triangle", f, f, 0.18) for f in (392, 349, 330, 262)], decay_power=1.0),
}


def render_sfx(kind: str, volume: float = 0.5, pitch: float = 1.0, seed: Optional[int] = None,
               bitcrush: int = 0) -> np.ndarray:
    if kind not in SFX_RECIPES:
        raise ValueError(f"unknown sfx '{kind}'. Available: {', '.join(sorted(SFX_RECIPES))}")
    r = dict(SFX_RECIPES[kind])
    if "multi" in r:
        parts = []
        dp = r.get("decay_power", 1.5)
        for wk, fs, fe, dur in r["multi"]:
            parts.append(synth(wk, fs * pitch, fe * pitch, dur, decay_power=dp, volume=volume, bitcrush=bitcrush, seed=seed))
        return np.concatenate(parts)
    r["f_start"] = r["f_start"] * (pitch if r["f_start"] > 1 else 1)
    if r.get("f_end"):
        r["f_end"] = r["f_end"] * pitch
    r["volume"] = volume
    r["bitcrush"] = bitcrush
    r["seed"] = seed
    return synth(**r)


def write_wav(path: str | Path, samples: np.ndarray, sr: int = SR, normalize: bool = True) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = np.asarray(samples, dtype=np.float64)
    peak = float(np.abs(data).max()) if data.size else 0.0
    if normalize and peak > 0.95:
        data = data / peak * 0.95  # only scale down when it would clip
    data = np.clip(data, -1, 1)
    pcm = (data * 32767).astype("<i2")
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return str(p)


def wav_info(path: str | Path) -> dict:
    with wave.open(str(path), "rb") as w:
        frames = w.getnframes()
        return {"channels": w.getnchannels(), "sample_rate": w.getframerate(),
                "sample_width_bytes": w.getsampwidth(), "frames": frames,
                "duration_s": round(frames / w.getframerate(), 3)}


# --------------------------------------------------------------------------- #
# melody + chiptune
# --------------------------------------------------------------------------- #
def render_melody(notes: str, bpm: float = 120, wave_kind: str = "square", volume: float = 0.4,
                  duty: float = 0.5, decay_power: float = 1.0) -> np.ndarray:
    """notes: 'C4:1 E4:1 G4:2 R:1' -> name:beats (default 1 beat)."""
    beat = 60.0 / bpm
    parts = []
    for tok in notes.split():
        name, _, beats = tok.partition(":")
        dur = float(beats) * beat if beats else beat
        f = note_to_freq(name)
        if f <= 0:
            parts.append(np.zeros(int(dur * SR)))
        else:
            parts.append(synth(wave_kind, f, f, dur, attack=0.004, decay_power=decay_power,
                               volume=volume, duty=duty))
    return np.concatenate(parts) if parts else np.zeros(1)


SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "pentatonic": [0, 2, 4, 7, 9],
    "minor_pentatonic": [0, 3, 5, 7, 10],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
}

MOODS = {
    # scale, chord roots as scale degrees (0-based), tempo hint
    "happy":   dict(scale="major", prog=[0, 4, 5, 3], bpm=132),
    "calm":    dict(scale="pentatonic", prog=[0, 3, 4, 3], bpm=88),
    "sad":     dict(scale="minor", prog=[5, 3, 0, 4], bpm=76),
    "tense":   dict(scale="phrygian", prog=[0, 1, 0, 5], bpm=124),
    "epic":    dict(scale="minor", prog=[0, 5, 6, 0], bpm=140),
    "mystery": dict(scale="dorian", prog=[0, 3, 0, 6], bpm=96),
}


def generate_chiptune(mood: str = "happy", bars: int = 8, bpm: Optional[int] = None,
                      key: str = "C", seed: int = 1, drums: bool = True) -> np.ndarray:
    cfg = MOODS.get(mood, MOODS["happy"])
    rng = np.random.default_rng(seed)
    bpm = bpm or cfg["bpm"]
    scale = SCALES[cfg["scale"]]
    root_midi = 12 * 4 + NOTE_INDEX[key.upper()]  # octave 4
    beat = 60.0 / bpm
    step = beat / 2  # eighth notes
    steps_per_bar = 8
    total_steps = bars * steps_per_bar
    total = int(total_steps * step * SR) + SR // 2
    lead = np.zeros(total)
    bass = np.zeros(total)
    perc = np.zeros(total)

    def degree_to_freq(deg: int, octave_shift: int = 0) -> float:
        octave, idx = divmod(deg, len(scale))
        midi = root_midi + scale[idx] + 12 * (octave + octave_shift)
        return 440.0 * 2 ** ((midi - 69) / 12)

    def add(buf: np.ndarray, start_step: int, sig: np.ndarray) -> None:
        s = int(start_step * step * SR)
        e = min(len(buf), s + len(sig))
        buf[s:e] += sig[: e - s]

    deg = 4
    for bar in range(bars):
        chord = cfg["prog"][bar % len(cfg["prog"])]
        for s in range(steps_per_bar):
            idx = bar * steps_per_bar + s
            if s % 2 == 0:  # bass on beats
                add(bass, idx, synth("triangle", degree_to_freq(chord, -2), None, step * 1.8,
                                     decay_power=0.8, volume=0.55))
            if rng.random() < 0.75:
                move = int(rng.choice([-2, -1, -1, 0, 1, 1, 2]))
                target = chord + 7 * 0 + int(rng.choice([0, 2, 4]))
                deg = int(np.clip(deg + move + np.sign(target - deg) * (rng.random() < 0.3), chord - 2, chord + 9))
                length = step * float(rng.choice([1.0, 1.0, 2.0]))
                add(lead, idx, synth("square", degree_to_freq(deg, 1), None, length, duty=0.25,
                                     decay_power=1.1, volume=0.28))
            if drums:
                if s in (0, 4):
                    add(perc, idx, synth("sine", 150, 45, step * 1.4, decay_power=2.0, volume=0.7))
                if s in (2, 6):
                    add(perc, idx, synth("noise", 1, None, step * 0.9, decay_power=3.0, volume=0.25,
                                         lowpass=0.35, seed=int(rng.integers(1_000_000))))
                if s % 2 == 1:
                    add(perc, idx, synth("noise", 1, None, step * 0.25, decay_power=4.0, volume=0.1,
                                         seed=int(rng.integers(1_000_000))))
    mix = lead + bass + perc
    loop_len = int(total_steps * step * SR)
    tail = mix[loop_len:]
    mix = mix[:loop_len]
    mix[: len(tail)] += tail[: len(mix)]  # wrap the release tail for a seamless loop
    return mix


def peak_normalize(samples: np.ndarray, peak: float = 0.9) -> np.ndarray:
    m = np.abs(samples).max()
    return samples if m == 0 else samples / m * peak
