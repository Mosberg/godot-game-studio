#!/usr/bin/env python3
"""Godot Game Studio - asset pipeline MCP server (pixel art / image processing + procedural audio).

Pure Pillow + numpy (no GIMP needed). Audio is synthesised procedurally to .wav, with optional ffmpeg
conversion to .ogg/.mp3 and loudness normalisation.
"""
from __future__ import annotations

import functools
import sys
import traceback
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import studio_common as sc  # noqa: E402
from studio_common import fail, ok  # noqa: E402

mcp = sc.make_server(
    "assets",
    "Image and audio pipeline for game assets. Image tools: asset_image_info, asset_pixelate, asset_palette_*, "
    "asset_remove_background, asset_outline, asset_seamless_tile, asset_normal_map, spritesheet pack/slice, asset_gif. "
    "Audio tools: audio_sfx, audio_melody, audio_chiptune, audio_convert, audio_info. All paths are absolute or "
    "relative to the working directory; outputs default next to the input.",
)


def safe(fn):
    @functools.wraps(fn)
    def wrapper(*a, **k):
        try:
            return fn(*a, **k)
        except Exception as exc:  # noqa: BLE001
            return fail(f"{type(exc).__name__}: {exc}", trace=traceback.format_exc()[-1000:])
    return wrapper


def _si():
    import studio_images as si
    return si


def _sa():
    import studio_audio as sa
    return sa


def _out(input_path: str, output_path: str, suffix: str) -> str:
    if output_path:
        return output_path
    p = Path(input_path)
    return str(p.with_name(f"{p.stem}_{suffix}.png"))


# =========================================================================== #
# images
# =========================================================================== #
@mcp.tool()
@safe
def asset_image_info(path: str) -> str:
    """Size, mode, transparency, unique colour count and a quick palette."""
    si = _si()
    data = si.info(path)
    data["palette"] = si.extract_palette(si.load_rgba(path), 12)
    return ok(**data)


@mcp.tool()
@safe
def asset_list_palettes() -> str:
    """Built-in palettes: pico8, gameboy, sweetie16, grayscale4, grayscale8, bw."""
    si = _si()
    return ok(palettes={k: v for k, v in si.PALETTES.items()}, custom="Pass 'ff0000,00ff00,...' anywhere a palette is accepted.")


@mcp.tool()
@safe
def asset_extract_palette(path: str, colors: int = 16) -> str:
    """Extract a palette (hex list) from an image; paste into asset_apply_palette or a GDScript constant."""
    si = _si()
    return ok(colors=si.extract_palette(si.load_rgba(path), colors))


@mcp.tool()
@safe
def asset_pixelate(path: str, width: int, output_path: str = "", height: int = 0, palette: str = "",
                   dither: bool = False, upscale: int = 1, remove_bg: bool = False) -> str:
    """Convert any image to crisp pixel art: downscale to `width` px (height keeps ratio unless set), optionally
    snap to a palette, remove background, and upscale with nearest-neighbour (upscale=4 for a preview)."""
    si = _si()
    img = si.load_rgba(path)
    if remove_bg:
        img = si.remove_background(img)
    img = si.pixelate(img, width, height or None)
    if palette:
        img = si.quantize_to_palette(img, si.resolve_palette(palette), dither=dither)
    if upscale > 1:
        img = si.scale_nearest(img, upscale)
    out = si.save(img, _out(path, output_path, "pixel"))
    return ok(file=out, size=[img.width, img.height])


@mcp.tool()
@safe
def asset_apply_palette(path: str, palette: str, output_path: str = "", dither: bool = False) -> str:
    """Recolour an image to a fixed palette (name or comma-separated hex list)."""
    si = _si()
    img = si.quantize_to_palette(si.load_rgba(path), si.resolve_palette(palette), dither=dither)
    return ok(file=si.save(img, _out(path, output_path, "pal")))


@mcp.tool()
@safe
def asset_scale(path: str, factor: int, output_path: str = "") -> str:
    """Integer nearest-neighbour upscale (keeps pixels sharp)."""
    si = _si()
    img = si.scale_nearest(si.load_rgba(path), factor)
    return ok(file=si.save(img, _out(path, output_path, f"x{factor}")), size=[img.width, img.height])


@mcp.tool()
@safe
def asset_remove_background(path: str, output_path: str = "", tolerance: int = 40, feather: int = 0,
                            method: str = "auto", trim: bool = True) -> str:
    """Make the background transparent. method: auto | flood (edge flood fill, great for flat colours) | rembg (AI,
    needs `pip install rembg`)."""
    si = _si()
    img = si.remove_background(si.load_rgba(path), tolerance=tolerance, feather=feather, method=method)
    if trim:
        img = si.trim(img)
    return ok(file=si.save(img, _out(path, output_path, "cut")), size=[img.width, img.height])


@mcp.tool()
@safe
def asset_outline(path: str, color: str = "000000", thickness: int = 1, output_path: str = "") -> str:
    """Add a clean outline around the opaque pixels (sprite readability)."""
    si = _si()
    img = si.outline(si.load_rgba(path), color, thickness)
    return ok(file=si.save(img, _out(path, output_path, "outlined")))


@mcp.tool()
@safe
def asset_trim(path: str, padding: int = 0, output_path: str = "") -> str:
    """Crop transparent borders."""
    si = _si()
    img = si.trim(si.load_rgba(path), padding)
    return ok(file=si.save(img, _out(path, output_path, "trim")), size=[img.width, img.height])


@mcp.tool()
@safe
def asset_seamless_tile(path: str, blend: float = 0.5, output_path: str = "", preview: bool = True) -> str:
    """Make a texture tile seamlessly (edge blending) and write a 3x3 preview to check the seams."""
    si = _si()
    img = si.make_seamless(si.load_rgba(path), blend)
    out = si.save(img, _out(path, output_path, "seamless"))
    result = {"file": out}
    if preview:
        result["preview"] = si.save(si.tile_preview(img, 3), Path(out).with_name(Path(out).stem + "_preview.png"))
    return ok(**result)


@mcp.tool()
@safe
def asset_normal_map(height_or_albedo: str, strength: float = 2.0, invert: bool = False, output_path: str = "") -> str:
    """Derive a normal map from a height map or (approximately) from an albedo texture. For Godot CanvasItem normal maps."""
    si = _si()
    img = si.normal_map_from_height(si.load_rgba(height_or_albedo), strength, invert)
    return ok(file=si.save(img, _out(height_or_albedo, output_path, "n")))


@mcp.tool()
@safe
def asset_gradient_ramp(colors: list[str], output_path: str, width: int = 256, height: int = 1) -> str:
    """Create a gradient strip (for GradientTexture alternatives, palette-swap shaders, toon ramps)."""
    si = _si()
    return ok(file=si.save(si.make_gradient_ramp(colors, width, height), output_path))


@mcp.tool()
@safe
def asset_pack_spritesheet(frames: list[str], output_path: str, columns: int = 0, padding: int = 0) -> str:
    """Pack frame images into one sheet (bottom-aligned, uniform cells) plus <name>.atlas.json with cell size and
    frame rects. In Godot set Sprite2D.hframes/vframes (padding 0) or build an AtlasTexture/SpriteFrames."""
    si = _si()
    sheet, atlas = si.pack_spritesheet(frames, columns=columns, padding=padding)
    out = si.save(sheet, output_path)
    atlas_path = si.write_json(Path(output_path).with_suffix(".atlas.json"), atlas)
    return ok(sheet=out, atlas=atlas_path, cell=atlas["cell"], columns=atlas["columns"], rows=atlas["rows"])


@mcp.tool()
@safe
def asset_slice_spritesheet(path: str, frame_width: int, frame_height: int, output_dir: str, prefix: str = "frame",
                            margin: int = 0, spacing: int = 0, skip_empty: bool = True) -> str:
    """Slice a grid sprite sheet into individual PNG frames."""
    si = _si()
    files = si.slice_spritesheet(path, frame_width, frame_height, output_dir, prefix, margin, spacing, skip_empty)
    return ok(count=len(files), files=files[:200])


@mcp.tool()
@safe
def asset_make_gif(frames: list[str], output_path: str, fps: int = 10, scale: int = 1) -> str:
    """Animated GIF from frames - a quick preview of an animation you can look at."""
    si = _si()
    return ok(file=si.make_gif(frames, output_path, fps, scale))


@mcp.tool()
@safe
def asset_contact_sheet(images: list[str], output_path: str, columns: int = 4, cell: int = 192, labels: bool = True) -> str:
    """One labelled overview image of many assets - review a whole batch at a glance."""
    si = _si()
    return ok(file=si.contact_sheet(images, output_path, columns, cell, labels))


# =========================================================================== #
# audio
# =========================================================================== #
@mcp.tool()
@safe
def audio_list_presets() -> str:
    """List SFX recipes and chiptune moods."""
    sa = _sa()
    return ok(sfx=sorted(sa.SFX_RECIPES), moods=sorted(sa.MOODS),
              melody_syntax="'C4:1 E4:1 G4:2 R:1' (note:beats, R = rest)")


@mcp.tool()
@safe
def audio_sfx(kind: str, output_path: str, volume: float = 0.5, pitch: float = 1.0, seed: int = -1,
              bitcrush: int = 0, variations: int = 1) -> str:
    """Synthesise a retro sound effect to .wav (jump, coin, hit, explosion, laser, powerup, ...). `variations` > 1
    writes name_1..N with different seeds - great for footsteps/hits so the audio doesn't repeat."""
    sa = _sa()
    out = Path(output_path)
    files = []
    for i in range(max(1, variations)):
        s = None if seed < 0 else seed + i
        samples = sa.render_sfx(kind, volume, pitch, s, bitcrush)
        target = out if variations == 1 else out.with_name(f"{out.stem}_{i + 1}{out.suffix or '.wav'}")
        files.append(sa.write_wav(target if target.suffix else target.with_suffix(".wav"), samples))
    return ok(files=files)


@mcp.tool()
@safe
def audio_melody(notes: str, output_path: str, bpm: float = 120, wave: str = "square", volume: float = 0.4,
                 duty: float = 0.5) -> str:
    """Render a note string to .wav. wave: square | triangle | saw | sine | noise. Example: 'C4:1 E4:1 G4:2 R:1'."""
    sa = _sa()
    samples = sa.render_melody(notes, bpm, wave, volume, duty)
    return ok(file=sa.write_wav(output_path, samples), seconds=round(len(samples) / sa.SR, 2))


@mcp.tool()
@safe
def audio_chiptune(output_path: str, mood: str = "happy", bars: int = 8, bpm: int = 0, key: str = "C",
                   seed: int = 1, drums: bool = True) -> str:
    """Generate a loopable chiptune track (lead + bass + arpeggio + drums) to .wav. Seamless loop: set the
    AudioStreamWAV loop mode in Godot (or convert to .ogg and enable Loop in the import dock)."""
    sa = _sa()
    samples = sa.generate_chiptune(mood, bars, bpm or None, key, seed, drums)
    return ok(file=sa.write_wav(output_path, samples), seconds=round(len(samples) / sa.SR, 2), mood=mood)


@mcp.tool()
@safe
def audio_info(path: str) -> str:
    """Duration, sample rate, channels, peak level of a .wav."""
    return ok(**_sa().wav_info(path))


@mcp.tool()
@safe
def audio_convert(input_path: str, output_path: str, normalize: bool = False, trim_silence: bool = False,
                  bitrate: str = "128k", mono: bool = False) -> str:
    """Convert/clean audio with ffmpeg (wav/ogg/mp3/flac). normalize applies loudnorm (-16 LUFS); trim_silence strips
    leading/trailing silence. Prefer .ogg for music and .wav for short SFX in Godot."""
    ff = sc.find_ffmpeg()
    if not ff:
        return fail("ffmpeg not found. Install it (winget install ffmpeg) or set FFMPEG_PATH.")
    cmd = [ff, "-y", "-i", str(Path(input_path).resolve())]
    filters = []
    if trim_silence:
        filters.append("silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
                       "silenceremove=start_periods=1:start_threshold=-50dB,areverse")
    if normalize:
        filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
    if filters:
        cmd += ["-af", ",".join(filters)]
    if mono:
        cmd += ["-ac", "1"]
    if Path(output_path).suffix.lower() in (".mp3", ".ogg"):
        cmd += ["-b:a", bitrate]
    cmd.append(str(Path(output_path).resolve()))
    Path(output_path).resolve().parent.mkdir(parents=True, exist_ok=True)
    res = sc.run(cmd, timeout=300)
    if res["returncode"] != 0:
        return fail("ffmpeg failed", details=res["stderr"][-1200:])
    return ok(file=output_path)


@mcp.tool()
@safe
def assets_doctor() -> str:
    """Report which optional components are available (Pillow, numpy, rembg, ffmpeg)."""
    status = {}
    for mod in ("PIL", "numpy", "rembg"):
        try:
            __import__(mod)
            status[mod] = True
        except ImportError:
            status[mod] = False
    status["ffmpeg"] = sc.find_ffmpeg()
    return ok(**status)


if __name__ == "__main__":
    mcp.run()
