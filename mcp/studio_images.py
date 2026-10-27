"""Pillow/numpy image helpers shared by the assets and ComfyUI servers."""
from __future__ import annotations

import json
import math
from collections import deque
from pathlib import Path
from typing import Optional, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# --------------------------------------------------------------------------- #
# palettes (hex strings)
# --------------------------------------------------------------------------- #
PALETTES: dict[str, list[str]] = {
    "pico8": ["000000", "1D2B53", "7E2553", "008751", "AB5236", "5F574F", "C2C3C7", "FFF1E8",
              "FF004D", "FFA300", "FFEC27", "00E436", "29ADFF", "83769C", "FF77A8", "FFCCAA"],
    "gameboy": ["0f380f", "306230", "8bac0f", "9bbc0f"],
    "sweetie16": ["1a1c2c", "5d275d", "b13e53", "ef7d57", "ffcd75", "a7f070", "38b764", "257179",
                  "29366f", "3b5dc9", "41a6f6", "73eff7", "f4f4f4", "94b0c2", "566c86", "333c57"],
    "grayscale4": ["000000", "555555", "aaaaaa", "ffffff"],
    "grayscale8": ["000000", "242424", "494949", "6d6d6d", "929292", "b6b6b6", "dbdbdb", "ffffff"],
    "bw": ["000000", "ffffff"],
}


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_to_hex(rgb: Sequence[int]) -> str:
    return "{:02x}{:02x}{:02x}".format(int(rgb[0]), int(rgb[1]), int(rgb[2]))


def resolve_palette(spec: str | Sequence[str]) -> list[tuple[int, int, int]]:
    """spec: builtin name, 'a1b2c3,ffffff,...' string, or a list of hex strings."""
    if isinstance(spec, str):
        key = spec.strip().lower()
        if key in PALETTES:
            return [hex_to_rgb(h) for h in PALETTES[key]]
        parts = [p for p in key.replace(";", ",").replace(" ", ",").split(",") if p]
        if not parts:
            raise ValueError("empty palette")
        return [hex_to_rgb(p) for p in parts]
    return [hex_to_rgb(p) for p in spec]


# --------------------------------------------------------------------------- #
# IO
# --------------------------------------------------------------------------- #
def load_rgba(path: str | Path) -> Image.Image:
    return Image.open(path).convert("RGBA")


def save(img: Image.Image, path: str | Path) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    img.save(p)
    return str(p)


def info(path: str | Path) -> dict:
    img = Image.open(path)
    rgba = img.convert("RGBA")
    arr = np.asarray(rgba)
    alpha = arr[..., 3]
    bbox = rgba.getbbox()
    colors = rgba.getcolors(maxcolors=1 << 16)
    return {
        "path": str(path),
        "format": img.format,
        "mode": img.mode,
        "size": list(img.size),
        "has_transparency": bool((alpha < 255).any()),
        "opaque_bbox": list(bbox) if bbox else None,
        "unique_colors": len(colors) if colors else ">65536",
        "power_of_two": all((d & (d - 1)) == 0 for d in img.size),
    }


# --------------------------------------------------------------------------- #
# palette / pixel-art operations
# --------------------------------------------------------------------------- #
_RESAMPLE = {
    "nearest": Image.NEAREST,
    "box": Image.BOX,
    "bilinear": Image.BILINEAR,
    "bicubic": Image.BICUBIC,
    "lanczos": Image.LANCZOS,
}


def quantize_to_palette(img: Image.Image, palette: list[tuple[int, int, int]],
                        dither: bool = False, alpha_threshold: int = 128) -> Image.Image:
    rgba = np.asarray(img.convert("RGBA")).astype(np.float32)
    h, w = rgba.shape[:2]
    rgb = rgba[..., :3].copy()
    alpha = rgba[..., 3]
    pal = np.array(palette, dtype=np.float32)

    def nearest(block: np.ndarray) -> np.ndarray:
        flat = block.reshape(-1, 3)
        d = ((flat[:, None, :] - pal[None, :, :]) ** 2).sum(axis=2)
        return d.argmin(axis=1)

    if not dither:
        idx = nearest(rgb).reshape(h, w)
        out_rgb = pal[idx]
    else:
        # Floyd-Steinberg
        work = rgb.copy()
        out_rgb = np.zeros_like(work)
        for y in range(h):
            for x in range(w):
                old = work[y, x]
                i = ((pal - old) ** 2).sum(axis=1).argmin()
                new = pal[i]
                out_rgb[y, x] = new
                err = old - new
                if x + 1 < w:
                    work[y, x + 1] += err * 7 / 16
                if y + 1 < h:
                    if x > 0:
                        work[y + 1, x - 1] += err * 3 / 16
                    work[y + 1, x] += err * 5 / 16
                    if x + 1 < w:
                        work[y + 1, x + 1] += err * 1 / 16
    out_alpha = np.where(alpha >= alpha_threshold, 255, 0).astype(np.uint8)
    out = np.dstack([out_rgb.astype(np.uint8), out_alpha])
    return Image.fromarray(out, "RGBA")


def pixelate(img: Image.Image, target_w: int, target_h: Optional[int] = None,
             resample: str = "box") -> Image.Image:
    if target_h is None:
        target_h = max(1, round(img.height * target_w / img.width))
    return img.resize((max(1, target_w), max(1, target_h)), _RESAMPLE.get(resample, Image.BOX))


def scale_nearest(img: Image.Image, factor: int) -> Image.Image:
    factor = max(1, int(factor))
    return img.resize((img.width * factor, img.height * factor), Image.NEAREST)


def extract_palette(img: Image.Image, colors: int = 16) -> list[str]:
    rgba = img.convert("RGBA")
    arr = np.asarray(rgba)
    mask = arr[..., 3] > 0
    if not mask.any():
        return []
    px = arr[mask][:, :3]
    side = int(math.ceil(math.sqrt(len(px))))
    pad = np.zeros((side * side, 3), dtype=np.uint8)
    pad[: len(px)] = px
    pad[len(px):] = px[-1]
    tmp = Image.fromarray(pad.reshape(side, side, 3), "RGB")
    q = tmp.quantize(colors=max(2, colors), method=Image.MEDIANCUT)
    pal = q.getpalette() or []
    used = sorted({int(v) for v in np.asarray(q).flatten()})
    return [rgb_to_hex(pal[i * 3: i * 3 + 3]) for i in used]


def remove_background(img: Image.Image, tolerance: int = 40, feather: int = 0,
                      method: str = "auto") -> Image.Image:
    """Make the background transparent.

    method: 'rembg' (AI, if installed), 'flood' (flood-fill from the borders using the
    border colour) or 'auto' (rembg when available, otherwise flood)."""
    rgba = img.convert("RGBA")
    if method in ("auto", "rembg"):
        try:
            from rembg import remove  # type: ignore
            return remove(rgba)
        except Exception:
            if method == "rembg":
                raise
    arr = np.asarray(rgba).astype(np.int32)
    h, w = arr.shape[:2]
    border = np.concatenate([arr[0, :, :3], arr[-1, :, :3], arr[:, 0, :3], arr[:, -1, :3]])
    bg = np.median(border, axis=0)
    dist = np.sqrt(((arr[..., :3] - bg) ** 2).sum(axis=2))
    candidate = dist <= tolerance
    visited = np.zeros((h, w), dtype=bool)
    q: deque[tuple[int, int]] = deque()
    for x in range(w):
        for y in (0, h - 1):
            if candidate[y, x] and not visited[y, x]:
                visited[y, x] = True
                q.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if candidate[y, x] and not visited[y, x]:
                visited[y, x] = True
                q.append((y, x))
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and candidate[ny, nx] and not visited[ny, nx]:
                visited[ny, nx] = True
                q.append((ny, nx))
    out = arr.copy().astype(np.uint8)
    out[visited, 3] = 0
    result = Image.fromarray(out, "RGBA")
    if feather > 0:
        from PIL import ImageFilter
        a = result.getchannel("A").filter(ImageFilter.GaussianBlur(feather))
        result.putalpha(a)
    return result


def trim(img: Image.Image, padding: int = 0) -> Image.Image:
    rgba = img.convert("RGBA")
    bbox = rgba.getchannel("A").getbbox()
    if not bbox:
        return rgba
    l, t, r, b = bbox
    l, t = max(0, l - padding), max(0, t - padding)
    r, b = min(rgba.width, r + padding), min(rgba.height, b + padding)
    return rgba.crop((l, t, r, b))


def outline(img: Image.Image, color: str = "000000", thickness: int = 1) -> Image.Image:
    rgba = img.convert("RGBA")
    pad = thickness
    canvas = Image.new("RGBA", (rgba.width + pad * 2, rgba.height + pad * 2), (0, 0, 0, 0))
    canvas.paste(rgba, (pad, pad))
    alpha = np.asarray(canvas.getchannel("A")) > 0
    grown = alpha.copy()
    for _ in range(thickness):
        g = grown.copy()
        g[1:, :] |= grown[:-1, :]
        g[:-1, :] |= grown[1:, :]
        g[:, 1:] |= grown[:, :-1]
        g[:, :-1] |= grown[:, 1:]
        grown = g
    edge = grown & ~alpha
    r, g_, b = hex_to_rgb(color)
    arr = np.asarray(canvas).copy()
    arr[edge] = (r, g_, b, 255)
    return Image.fromarray(arr, "RGBA")


def make_seamless(img: Image.Image, blend: float = 0.5) -> Image.Image:
    """Cross-fade a shifted copy so the result tiles without visible seams."""
    rgb = np.asarray(img.convert("RGBA")).astype(np.float32)
    h, w = rgb.shape[:2]
    shifted = np.roll(np.roll(rgb, h // 2, axis=0), w // 2, axis=1)
    ys = np.linspace(-1, 1, h)[:, None]
    xs = np.linspace(-1, 1, w)[None, :]
    d = np.maximum(np.abs(ys), np.abs(xs))
    t = np.clip((1.0 - d) / max(blend, 1e-3), 0, 1)
    t = t * t * (3 - 2 * t)
    out = rgb * t[..., None] + shifted * (1 - t[..., None])
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")


def tile_preview(img: Image.Image, n: int = 3) -> Image.Image:
    canvas = Image.new("RGBA", (img.width * n, img.height * n))
    for y in range(n):
        for x in range(n):
            canvas.paste(img, (x * img.width, y * img.height))
    return canvas


def normal_map_from_height(img: Image.Image, strength: float = 2.0, invert: bool = False) -> Image.Image:
    gray = np.asarray(img.convert("L")).astype(np.float32) / 255.0
    if invert:
        gray = 1.0 - gray
    gx = (np.roll(gray, -1, axis=1) - np.roll(gray, 1, axis=1)) * 0.5
    gy = (np.roll(gray, -1, axis=0) - np.roll(gray, 1, axis=0)) * 0.5
    nx, ny = -gx * strength, gy * strength  # +Y green = up (OpenGL / Godot convention)
    nz = np.ones_like(nx)
    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny, nz = nx / length, ny / length, nz / length
    out = np.dstack([(nx * 0.5 + 0.5) * 255, (ny * 0.5 + 0.5) * 255, (nz * 0.5 + 0.5) * 255])
    return Image.fromarray(out.astype(np.uint8), "RGB").convert("RGBA")


def make_gradient_ramp(colors: list[str], width: int = 256, height: int = 1) -> Image.Image:
    stops = [hex_to_rgb(c) for c in colors]
    if len(stops) < 2:
        raise ValueError("need at least two colours")
    arr = np.zeros((height, width, 4), dtype=np.uint8)
    for x in range(width):
        t = x / (width - 1) * (len(stops) - 1)
        i = min(int(t), len(stops) - 2)
        f = t - i
        c = [round(stops[i][k] * (1 - f) + stops[i + 1][k] * f) for k in range(3)]
        arr[:, x] = (*c, 255)
    return Image.fromarray(arr, "RGBA")


# --------------------------------------------------------------------------- #
# spritesheets
# --------------------------------------------------------------------------- #
def pack_spritesheet(paths: list[str], columns: int = 0, padding: int = 0,
                     uniform: bool = True) -> tuple[Image.Image, dict]:
    images = [load_rgba(p) for p in paths]
    if not images:
        raise ValueError("no images")
    cell_w = max(i.width for i in images)
    cell_h = max(i.height for i in images)
    cols = columns if columns > 0 else math.ceil(math.sqrt(len(images)))
    rows = math.ceil(len(images) / cols)
    sheet = Image.new("RGBA", (cols * (cell_w + padding) + padding, rows * (cell_h + padding) + padding), (0, 0, 0, 0))
    frames = []
    for n, (p, im) in enumerate(zip(paths, images)):
        cx, cy = n % cols, n // cols
        x = padding + cx * (cell_w + padding)
        y = padding + cy * (cell_h + padding)
        ox = (cell_w - im.width) // 2 if uniform else 0
        oy = cell_h - im.height if uniform else 0  # bottom-align so feet stay put
        sheet.paste(im, (x + ox, y + oy))
        frames.append({"name": Path(p).stem, "x": x, "y": y, "w": cell_w, "h": cell_h, "index": n})
    atlas = {"image_size": [sheet.width, sheet.height], "cell": [cell_w, cell_h],
             "columns": cols, "rows": rows, "padding": padding, "frames": frames}
    return sheet, atlas


def slice_spritesheet(path: str, frame_w: int, frame_h: int, out_dir: str, prefix: str = "frame",
                      margin: int = 0, spacing: int = 0, skip_empty: bool = True) -> list[str]:
    sheet = load_rgba(path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    cols = (sheet.width - margin + spacing) // (frame_w + spacing)
    rows = (sheet.height - margin + spacing) // (frame_h + spacing)
    written = []
    n = 0
    for r in range(rows):
        for c in range(cols):
            x = margin + c * (frame_w + spacing)
            y = margin + r * (frame_h + spacing)
            tile = sheet.crop((x, y, x + frame_w, y + frame_h))
            if skip_empty and tile.getchannel("A").getbbox() is None:
                continue
            fp = out / f"{prefix}_{n:03d}.png"
            tile.save(fp)
            written.append(str(fp))
            n += 1
    return written


def make_gif(paths: list[str], out_path: str, fps: int = 10, scale: int = 1, loop: int = 0) -> str:
    frames = [load_rgba(p) for p in paths]
    if scale > 1:
        frames = [scale_nearest(f, scale) for f in frames]
    # GIF transparency: composite on magenta key so previews are readable
    prepared = []
    for f in frames:
        bg = Image.new("RGBA", f.size, (40, 40, 48, 255))
        bg.alpha_composite(f)
        prepared.append(bg.convert("P", palette=Image.ADAPTIVE))
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    prepared[0].save(out_path, save_all=True, append_images=prepared[1:],
                     duration=int(1000 / max(1, fps)), loop=loop, disposal=2)
    return out_path


def contact_sheet(paths: list[str], out_path: str, columns: int = 4, cell: int = 192,
                  labels: bool = True) -> str:
    cols = max(1, columns)
    rows = math.ceil(len(paths) / cols)
    label_h = 16 if labels else 0
    sheet = Image.new("RGBA", (cols * cell, rows * (cell + label_h)), (32, 32, 40, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for n, p in enumerate(paths):
        try:
            im = load_rgba(p)
        except Exception:
            continue
        scale = min(cell / im.width, cell / im.height)
        if scale >= 1:
            scale = max(1, int(scale))
            im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
        else:
            im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.LANCZOS)
        cx, cy = (n % cols) * cell, (n // cols) * (cell + label_h)
        sheet.alpha_composite(im, (cx + (cell - im.width) // 2, cy + (cell - im.height) // 2))
        if labels:
            draw.text((cx + 3, cy + cell + 2), Path(p).stem[:28], fill=(220, 220, 220, 255), font=font)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    return out_path


def write_json(path: str | Path, data: dict) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return str(p)
