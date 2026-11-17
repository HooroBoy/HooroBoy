#!/usr/bin/env python3
"""Build the two small assets the profile README needs.

Design rule: the README keeps GitHub's own layout (markdown headings, tables,
badges, image rows). Only the *theme* comes from https://horoboy.my.id —
cream paper, dark brown ink, hard borders, zero radius, pixel type.

That means almost no custom artwork: one slim banner, one skyline footer, and
the pixel-art thumbnails as plain webp files that markdown can lay out.

    python scripts/build_assets.py
"""
from __future__ import annotations

import os

from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from PIL import Image

# palette, mirrored from the portfolio's global.css
BG = "#d9c8ab"
TEXT = "#2c1e0c"
MUTED = "#5f4a33"
ACCENT = "#ff3e14"
ON_ACCENT = "#ffffff"
PAPER = "#ffffff"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = r"E:/!Importante/my-porto/src/assets"
OUT = os.path.join(ROOT, "assets")

FONT_TTF = os.path.join(OUT, "fonts", "Silkscreen-Regular.ttf")
BODY_TTF = os.path.join(OUT, "fonts", "VT323-Regular.ttf")


def fmt(v: float) -> str:
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "", "-") else s


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class PixelFont:
    """Vector outlines, so the SVGs need no font file and no network request."""

    def __init__(self, path: str):
        self.font = TTFont(path)
        self.upem = self.font["head"].unitsPerEm
        self.cmap = self.font.getBestCmap()
        self.glyphs = self.font.getGlyphSet()
        self.hmtx = self.font["hmtx"]
        self._cache: dict[str, tuple[str, int]] = {}

    def glyph(self, ch: str) -> tuple[str, int]:
        name = self.cmap.get(ord(ch)) or self.cmap.get(ord("?"))
        if name not in self._cache:
            pen = SVGPathPen(self.glyphs, ntos=fmt)
            self.glyphs[name].draw(pen)
            self._cache[name] = (pen.getCommands(), self.hmtx[name][0])
        return self._cache[name]

    def measure(self, text: str, size: float, tracking: float = 0.0) -> float:
        t = tracking * self.upem / size
        return sum(self.glyph(c)[1] + t for c in text) * size / self.upem

    def path(self, text: str, size: float, tracking: float = 0.0) -> str:
        scale = size / self.upem
        t = tracking * self.upem / size
        cursor, parts = 0.0, []
        for ch in text:
            d, adv = self.glyph(ch)
            if d:
                if cursor:
                    pen = SVGPathPen(self.glyphs, ntos=fmt)
                    tp = TransformPen(pen, (1, 0, 0, 1, cursor, 0))
                    self.glyphs[self.cmap.get(ord(ch)) or self.cmap[ord("?")]].draw(tp)
                    parts.append(pen.getCommands())
                else:
                    parts.append(d)
            cursor += adv + t
        if not parts:
            return ""
        return f'<g transform="scale({fmt(scale)} {fmt(-scale)})">' + "".join(
            f'<path d="{p}"/>' for p in parts) + "</g>"

    def wrap(self, text: str, size: float, max_w: float, tracking: float = 0.0) -> list[str]:
        words, lines, cur = text.split(), [], ""
        for w in words:
            trial = f"{cur} {w}".strip()
            if self.measure(trial, size, tracking) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines


F = PixelFont(FONT_TTF)
BODY = PixelFont(BODY_TTF)


def text(s, x, y, size, fill=TEXT, tracking=0.0, anchor="start", font=None) -> str:
    if not s:
        return ""
    fnt = font or F
    w = fnt.measure(s, size, tracking)
    dx = {"start": 0, "middle": -w / 2, "end": -w}[anchor]
    return (f'<g transform="translate({fmt(x + dx)} {fmt(y)})" fill="{fill}">'
            f"{fnt.path(s, size, tracking)}</g>")


def rect(x, y, w, h, fill, stroke=None, sw=0) -> str:
    a = f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" fill="{fill}"'
    if stroke:
        a += f' stroke="{stroke}" stroke-width="{fmt(sw)}"'
    return a + "/>"


def svg(w, h, body, title="") -> str:
    t = f"<title>{esc(title)}</title>" if title else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{fmt(w)}" height="{fmt(h)}" '
            f'viewBox="0 0 {fmt(w)} {fmt(h)}" role="img">{t}{body}</svg>')


def save(name, content) -> None:
    path = os.path.join(OUT, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if isinstance(content, bytes):
        with open(path, "wb") as fh:
            fh.write(content)
    else:
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
    print(f"  {name:34s} {os.path.getsize(path)/1024:6.1f} KB")


def cover(src, w, h, pixel_art=False) -> Image.Image:
    im = Image.open(src)
    if im.mode == "RGBA":
        bg = Image.new("RGB", im.size, PAPER)
        bg.paste(im, mask=im.split()[3])
        im = bg
    else:
        im = im.convert("RGB")
    scale = max(w / im.width, h / im.height)
    im = im.resize((max(w, round(im.width * scale)), max(h, round(im.height * scale))),
                   Image.NEAREST if pixel_art else Image.LANCZOS)
    left, top = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((left, top, left + w, top + h))


def data_uri(im: Image.Image, pixel_art=False) -> str:
    import base64
    import io
    buf = io.BytesIO()
    if pixel_art:
        im.convert("P", palette=Image.ADAPTIVE, colors=64).save(buf, "PNG", optimize=True)
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    im.save(buf, "JPEG", quality=88, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


# --------------------------------------------------------------------------
# banner: one slim strip, everything else in the README is plain markdown
# --------------------------------------------------------------------------
W, H = 880, 152


def build_banner() -> None:
    b = [rect(0, 0, W, H, BG), rect(0, 0, W, 3, TEXT), rect(0, H - 3, W, 3, TEXT)]

    x = 28
    b.append(rect(x, 34, 9, 9, ACCENT))
    b.append(text("GAME DEV · UNITY · C# · PIXEL ART · 3D", x + 20, 43, 12, MUTED, 1.1))
    b.append(text("GUNAWAN WIBISONO.", x, 92, 34, TEXT, 0.6))
    b.append(text("CODES, ARTS, & DESIGN.", x, 122, 15, MUTED, 1.0))

    pw, ph = 168, 112
    px, py = W - pw - 30, 22
    b.append(rect(px + 6, py + 6, pw, ph, TEXT))
    b.append(rect(px, py, pw, ph, ACCENT, TEXT, 3))
    uri = data_uri(cover(os.path.join(SRC, "portrait.webp"), pw * 2, ph * 2, pixel_art=True), True)
    b.append(f'<defs><clipPath id="p"><rect x="{px + 3}" y="{py + 3}" width="{pw - 6}" '
             f'height="{ph - 6}"/></clipPath></defs>')
    b.append(f'<image x="{px + 3}" y="{py + 3}" width="{pw - 6}" height="{ph - 6}" '
             f'preserveAspectRatio="none" href="{uri}" clip-path="url(#p)"/>')

    save("banner.svg", svg(W, H, "".join(b), "Gunawan Wibisono — game developer"))


def build_skyline() -> None:
    w, h = W, 44
    b = [rect(0, 0, w, h, BG), rect(0, 0, w, 3, TEXT)]
    seed, x = 1337, 0
    while x < w:
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        bw = 16 + (seed >> 16) % 30
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        bh = 10 + (seed >> 16) % 30
        b.append(rect(x, h - bh, bw - 3, bh, TEXT))
        wy = h - bh + 5
        while wy < h - 5:
            wx = x + 5
            while wx < x + bw - 9:
                if (wx * 7 + wy * 13) % 11 == 0:
                    b.append(rect(wx, wy, 4, 4, ACCENT))
                wx += 9
            wy += 9
        x += bw
    save("skyline.svg", svg(w, h, "".join(b), "Skyline"))


PIXELS = [
    ("2025-horoboy-32", "pixels/--Horoboy/2025-horoboy-32.png"),
    ("2025-horoboy-in-void", "pixels/--Horoboy/2025-horoboy-in-void.webp"),
    ("2025-kanachan", "pixels/2025-kanachan.webp"),
    ("2025-pixel-pp", "pixels/--Horoboy/2025-pixel-pp.png"),
    ("2025-robo-ghost-smile", "pixels/--Horoboy/2025-Robo-ghost-smile.png"),
    ("2026-dnd-cahaya-hati", "pixels/2026-DND-Cahaya-Hati.png"),
]


def build_pixels() -> None:
    import io
    for slug, src in PIXELS:
        im = cover(os.path.join(SRC, src), 360, 360, pixel_art=True)
        buf = io.BytesIO()
        im.save(buf, "WEBP", quality=92, method=6)
        save(f"pixels/{slug}.webp", buf.getvalue())


if __name__ == "__main__":
    print("assets:")
    build_banner()
    build_skyline()
    build_pixels()
