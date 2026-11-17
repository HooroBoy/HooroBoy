#!/usr/bin/env python3
"""Generate the HooroBoy GitHub profile README + its SVG assets.

The look is a 1:1 copy of https://horoboy.my.id : cream paper, hard 3px
borders, solid offset shadows, zero radius, Silkscreen pixel font.

Everything is generated from this one file so the palette / copy can be
edited in one place. Run from the repo root:

    python scripts/build_readme.py
"""
from __future__ import annotations

import base64
import io
import json
import urllib.error
import urllib.request
import math
import os
import re
import textwrap

from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from PIL import Image

# --------------------------------------------------------------------------
# palette (mirrors src/styles/global.css :root on the portfolio)
# --------------------------------------------------------------------------
BG = "#d9c8ab"
TEXT = "#2c1e0c"
MUTED = "#5f4a33"
ACCENT = "#ff3e14"
ON_ACCENT = "#ffffff"
PAPER = "#ffffff"
BAND_BG = "#2c1e0c"
BAND_CARD = "#3b2a16"
BAND_TEXT = "#e6d7bd"
BAND_MUTED = "#b39d7d"
BAND_LINE = "#d9c8ab"
BAND_SHADOW = "#0d0803"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = r"E:/!Importante/my-porto/src/assets"
OUT = os.path.join(ROOT, "assets")
FONT_TTF = os.path.join(OUT, "fonts", "Silkscreen-Regular.ttf")
BODY_TTF = os.path.join(OUT, "fonts", "VT323-Regular.ttf")

W = 880  # GitHub README content column

# --------------------------------------------------------------------------
# pixel font -> vector paths
# --------------------------------------------------------------------------


def fmt(v: float) -> str:
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "", "-") else s


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class PixelFont:
    def __init__(self, path: str):
        self.font = TTFont(path)
        self.upem = self.font["head"].unitsPerEm
        self.cmap = self.font.getBestCmap()
        self.glyphs = self.font.getGlyphSet()
        self.hmtx = self.font["hmtx"]
        self._cache: dict[str, str] = {}

    def glyph(self, ch: str) -> tuple[str, int]:
        """Path data (font units, origin at glyph origin) + advance."""
        name = self.cmap.get(ord(ch)) or self.cmap.get(ord("?"))
        if name in self._cache:
            return self._cache[name], self.hmtx[name][0]
        pen = SVGPathPen(self.glyphs, ntos=fmt)
        self.glyphs[name].draw(pen)
        d = pen.getCommands()
        self._cache[name] = d
        return d, self.hmtx[name][0]

    def measure(self, text: str, size: float, tracking: float = 0.0) -> float:
        """Rendered width in px. `tracking` is in px."""
        t = tracking * self.upem / size
        return sum(self.glyph(c)[1] + t for c in text) * size / self.upem

    def path(self, text: str, size: float, tracking: float = 0.0) -> str:
        """Single <path d> for `text`, in px units, baseline at y=0."""
        scale = size / self.upem
        t = tracking * self.upem / size
        cursor = 0.0
        parts = []
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
            f'<path d="{p}"/>' for p in parts
        ) + "</g>"

    def wrap(self, text: str, size: float, max_w: float, tracking: float = 0.0) -> list[str]:
        words = text.split()
        lines: list[str] = []
        cur = ""
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


F = PixelFont(FONT_TTF)   # Silkscreen — headings, labels, buttons, tags
BODY = PixelFont(BODY_TTF)  # VT323 — running copy (has real lowercase)


def text(
    s: str,
    x: float,
    y: float,
    size: float,
    fill: str = TEXT,
    tracking: float = 0.0,
    anchor: str = "start",
    weight_extra: int = 0,
    font: "PixelFont | None" = None,
) -> str:
    """<text> replacement: vector path, baseline at (x, y)."""
    if not s:
        return ""
    fnt = font or F
    w = fnt.measure(s, size, tracking)
    dx = {"start": 0, "middle": -w / 2, "end": -w}[anchor]
    body = fnt.path(s, size, tracking)
    if weight_extra:  # fake bold: stamp the same glyphs a hair to the right
        extra = "".join(
            f'<g transform="translate({fmt(dx + i * 0.9)} 0)">{body}</g>' for i in range(1, weight_extra + 1)
        )
    else:
        extra = ""
    return f'<g transform="translate({fmt(x + dx)} {fmt(y)})" fill="{fill}">{body}{extra}</g>'


def rect(x, y, w, h, fill, stroke=None, sw=0, dash=None) -> str:
    a = f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" fill="{fill}"'
    if stroke:
        a += f' stroke="{stroke}" stroke-width="{fmt(sw)}"'
        if dash:
            a += f' stroke-dasharray="{dash}"'
    return a + "/>"


def card(x, y, w, h, fill=PAPER, border=TEXT, shadow=TEXT, bw=3, off=5) -> str:
    """Hard-bordered box with a solid offset shadow (no radius, ever)."""
    out = []
    if shadow:
        out.append(rect(x + off, y + off, w, h, shadow))
    out.append(rect(x, y, w, h, fill, border, bw))
    return "".join(out)


def badge(x, y, label, size=12, fg=ON_ACCENT, bg=ACCENT, border=TEXT, shadow=TEXT, pad=9) -> tuple[str, float]:
    """Accent sticker. Returns (svg, width)."""
    tw = F.measure(label, size, 1.2)
    w = tw + pad * 2
    h = size + 14
    out = [rect(x + 2, y + 2, w, h, shadow), rect(x, y, w, h, bg, border, 2)]
    out.append(text(label, x + pad, y + h / 2 + size * 0.36, size, fg, 1.2))
    return "".join(out), w


def pill(x, y, label, size=11, fg=MUTED, border=MUTED, bg="none", pad=6) -> tuple[str, float]:
    tw = F.measure(label, size, 0.8)
    w = tw + pad * 2
    h = size + 10
    out = [rect(x, y, w, h, bg, border, 2), text(label, x + pad, y + h / 2 + size * 0.36, size, fg, 0.8)]
    return "".join(out), w


def svg(w: float, h: float, body: str, title: str = "") -> str:
    t = f"<title>{esc(title)}</title>" if title else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{fmt(w)}" height="{fmt(h)}" '
        f'viewBox="0 0 {fmt(w)} {fmt(h)}" role="img">{t}{body}</svg>'
    )


def save(name: str, content: str) -> str:
    path = os.path.join(OUT, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content + "\n")
    print(f"  {name:32s} {len(content)/1024:6.1f} KB")
    return path


# --------------------------------------------------------------------------
# images -> data URIs
# --------------------------------------------------------------------------


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def cover(src: str, w: int, h: int, pixel_art: bool = False, quality: int = 86) -> str:
    """Crop-to-fill `src` into w x h, return a data: URI."""
    im = Image.open(src)
    if im.mode == "RGBA":
        bgc = Image.new("RGB", im.size, PAPER)
        bgc.paste(im, mask=im.split()[3])
        im = bgc
    else:
        im = im.convert("RGB")
    tw, th = w, h
    scale = max(tw / im.width, th / im.height)
    nw, nh = max(tw, math.ceil(im.width * scale)), max(th, math.ceil(im.height * scale))
    resample = Image.NEAREST if pixel_art else Image.LANCZOS
    im = im.resize((nw, nh), resample)
    left = (nw - tw) // 2
    top = (nh - th) // 2
    im = im.crop((left, top, left + tw, top + th))
    buf = io.BytesIO()
    if pixel_art:
        im.convert("P", palette=Image.ADAPTIVE, colors=64).save(buf, "PNG", optimize=True)
        return "data:image/png;base64," + _b64(buf.getvalue())
    im.save(buf, "JPEG", quality=quality, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + _b64(buf.getvalue())


def image(uri: str, x, y, w, h, clip: bool = True) -> str:
    idr = f"c{abs(hash(uri)) % 10**9}"
    cp = f' clip-path="url(#{idr})"' if clip else ""
    defs = (
        f'<defs><clipPath id="{idr}"><rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}"/>'
        f"</clipPath></defs>"
        if clip
        else ""
    )
    return (
        defs
        + f'<image x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" '
        f'preserveAspectRatio="none" href="{uri}"{cp}/>'
    )


# --------------------------------------------------------------------------
# content (copied from the portfolio data files)
# --------------------------------------------------------------------------
EYEBROW = ["GAME DEV", "UNITY", "C#", "PIXEL ART", "3D"]
MARQUEE = ["Unity", "C#", "Game Design", "Pixel Art", "3D Modeling", "Aseprite",
           "Blender", "Level Design", "Prototyping", "UI/UX"]

GAMES = [
    dict(title="Mechquarium", slug="mechquarium", year="2026", status="WIP",
         desc="Recreating Insaniquarium from scratch",
         tech=["Unity", "C#", "Aseprite"], thumb="projects/mechquarium.webp"),
    dict(title="Minimate", slug="minimate", year="2025", status="WIP",
         desc="Chess puzzle games with unique twist and turn",
         tech=["Unity", "C#", "Aseprite"], thumb="projects/minimate.webp"),
    dict(title="barongsway", slug="barongsway", year="2026", status="COMPLETE",
         desc="Multiplayer platforming games",
         tech=["Unity", "C#", "Aseprite"], thumb="projects/barongways.webp"),
    dict(title="Triblock Dash", slug="triblock-dash", year="2025", status="COMPLETE",
         desc="Runner arcade game with fast pace gameplay",
         tech=["Unity", "C#", "Aseprite"], thumb="projects/triblockdash.webp"),
    dict(title="Magicaffeine", slug="magicaffeine", year="2025", status="COMPLETE",
         desc="Cozy games about serving coffee",
         tech=["Unity", "C#", "Aseprite"], thumb="projects/magicaffeine.webp"),
]

PIXELS = [
    ("2025-horoboy-32", "Horoboy 32", "2025", "pixels/--Horoboy/2025-horoboy-32.png"),
    ("2025-horoboy-in-void", "Horoboy in Void", "2025", "pixels/--Horoboy/2025-horoboy-in-void.webp"),
    ("2025-kanachan", "Kanachan", "2025", "pixels/2025-kanachan.webp"),
    ("2025-pixel-pp", "Pixel Pp", "2025", "pixels/--Horoboy/2025-pixel-pp.png"),
    ("2025-Robo-ghost-smile", "Robo Ghost Smile", "2025", "pixels/--Horoboy/2025-Robo-ghost-smile.png"),
    ("2026-DND-Cahaya-Hati", "DND Cahaya Hati", "2026", "pixels/2026-DND-Cahaya-Hati.png"),
]

SITE = "https://horoboy.my.id"

# --------------------------------------------------------------------------
# sections
# --------------------------------------------------------------------------


def build_hero() -> None:
    w, h = W, 372
    b = [rect(0, 0, w, h, "none")]
    b.append(card(4, 4, w - 14, h - 14, BG, TEXT, TEXT, 3, 6))

    x = 36
    y = 58
    # eyebrow: accent square + items joined by dots
    b.append(rect(x, y - 9, 9, 9, ACCENT))
    b.append(text(" · ".join(EYEBROW), x + 20, y, 12, MUTED, 1.1))

    # headline
    ty = 128
    b.append(text("CODES, ARTS,", x, ty, 46, TEXT, 0.6))
    mark = "& DESIGN."
    mw = F.measure(mark, 46, 0.6)
    b.append(rect(x - 6, ty + 22, mw + 14, 58, ACCENT))
    b.append(text(mark, x, ty + 66, 46, ON_ACCENT, 0.6))
    # blinking cursor
    cx = x + mw + 12
    b.append(
        f'<rect x="{fmt(cx)}" y="{fmt(ty + 24)}" width="16" height="44" fill="{TEXT}">'
        '<animate attributeName="opacity" values="1;1;0;0" dur="1.1s" repeatCount="indefinite" '
        'calcMode="discrete"/></rect>'
    )

    # lede
    lede = ("Hello, My name is Gunawan Wibisono. This is my personal website, where I share "
            "my projects, pixel arts, and more..")
    ly = ty + 116
    for line in BODY.wrap(lede, 17, 356):
        b.append(text(line, x, ly, 17, TEXT, font=BODY))
        ly += 21
    b.append(text("LETS GET STARTED.", x, ly + 14, 12, MUTED, 1.1))

    # portrait + TODO sticker
    pw, ph = 400, 300
    px, py = w - pw - 62, 40
    b.append(rect(px + 7, py + 7, pw, ph, TEXT))
    b.append(rect(px, py, pw, ph, ACCENT, TEXT, 3))
    b.append(image(cover(os.path.join(SRC, "portrait.webp"), pw * 2, ph * 2, pixel_art=True), px + 3, py + 3, pw - 6, ph - 6))

    note = "TODO"
    nw = 190
    nx, ny = px - 26, py + ph - 66
    b.append(card(nx, ny, nw, 58, PAPER, TEXT, TEXT, 3, 5))
    b.append(text(note, nx + 14, ny + 24, 14, ACCENT, 1.2))
    b.append(text("WORKING ON A", nx + 14, ny + 40, 10, MUTED, 0.9))
    b.append(text("GAME PROJECT", nx + 14, ny + 52, 10, MUTED, 0.9))

    save("hero.svg", svg(w, h, "".join(b), "Horoboy — CODES, ARTS, & DESIGN."))


def build_marquee() -> None:
    h = 40
    label = "".join(f'{t}  ·  ' for t in MARQUEE)
    tw = F.measure(label, 13, 1.6)
    body = [rect(0, 0, W, h, ACCENT)]
    # two identical tracks so the loop is seamless
    for k in range(2):
        x = k * tw
        while x < W + tw:
            body.append(text(label, x, 26, 13, ON_ACCENT, 1.6))
            x += tw
    dur = round(tw / 46, 2)
    anim = (
        f'<g><animateTransform attributeName="transform" type="translate" '
        f'from="0 0" to="{fmt(-tw)} 0" dur="{dur}s" repeatCount="indefinite"/>'
        + "".join(str(p) for p in body[1:])
        + "</g>"
    )
    body = [
        rect(0, 0, W, h, ACCENT),
        rect(0, 0, W, 3, TEXT),
        rect(0, h - 3, W, 3, TEXT),
        anim,
    ]
    save("marquee.svg", svg(W, h, "".join(body), "Skills"))


def build_heading(name: str, label: str, title: str, sub: str = "") -> None:
    h = 108 if sub else 86
    b = []
    bd, bw = badge(4, 6, label, 12)
    b.append(bd)
    b.append(text(title, 4, 74, 32, TEXT, 0.8))
    if sub:
        b.append(text(sub, 4, 100, 12, MUTED))
    save(name, svg(W, h, "".join(b), title))


CARD_W = 276
GAP = 7  # baked-in whitespace so inline <img>s keep their distance


def game_card_height(cw: int, desc_lines: int) -> int:
    """Body height that always fits status + title + desc + tags."""
    media_h = round(cw * 9 / 16)
    body = 16 + 20 + 14 + 26 + desc_lines * 18 + 14 + 22 + 16
    return media_h + body + 3


def build_game_card(g: dict, ch: int | None = None) -> str:
    cw = CARD_W
    media_h = round(cw * 9 / 16)
    desc_lines = BODY.wrap(g["desc"], 15, cw - 28)[:2]
    if ch is None:
        ch = game_card_height(cw, len(desc_lines))
    b = []
    b.append(card(GAP, GAP, cw, ch, PAPER, TEXT, TEXT, 3, 5))
    b.append(image(cover(os.path.join(SRC, g["thumb"]), cw * 2, media_h * 2), GAP + 3, GAP + 3, cw - 6, media_h - 3))
    b.append(rect(GAP + 3, GAP + media_h - 3, cw - 6, 3, TEXT))

    # year sticker, sitting on the thumbnail
    yw = F.measure(g["year"], 11, 0.9) + 18
    bx = GAP + cw - yw - 11
    b.append(rect(bx, GAP + 11, yw, 23, PAPER, TEXT, 2))
    b.append(text(g["year"], bx + 9, GAP + 28, 11, TEXT, 0.9))

    y = GAP + media_h + 16
    pw, _ = pill(GAP + 13, y, g["status"], 10, ACCENT, ACCENT)
    b.append(pw)
    b.append(text(g["title"], GAP + 13, y + 20 + 14 + 20, 22, TEXT, 0.4))

    dy = y + 20 + 14 + 20 + 20
    for line in desc_lines:
        b.append(text(line, GAP + 13, dy, 15, MUTED, font=BODY))
        dy += 18

    tx = GAP + 13
    ty = GAP + ch - 38
    for t in g["tech"]:
        s2, tw = pill(tx, ty, t, 10, MUTED, MUTED)
        b.append(s2)
        tx += tw + 6
    return svg(CARD_W + GAP * 2, ch + GAP * 2, "".join(b), g["title"])


def build_pixel_card(title: str, year: str, path: str) -> str:
    cw = CARD_W
    ch = cw + 44
    b = [card(GAP, GAP, cw, ch, PAPER, TEXT, TEXT, 3, 5)]
    b.append(image(cover(os.path.join(SRC, path), cw * 2, cw * 2, pixel_art=True), GAP + 3, GAP + 3, cw - 6, cw - 6))
    b.append(rect(GAP + 3, GAP + cw - 3, cw - 6, 3, TEXT))
    b.append(text(title, GAP + 12, GAP + cw + 26, 14, TEXT, 0.5))
    b.append(text(year, GAP + cw - 12, GAP + cw + 26, 11, MUTED, 0.8, "end"))
    return svg(CARD_W + GAP * 2, ch + GAP * 2, "".join(b), f"{title} ({year})")


def build_about() -> None:
    w, h = W, 336
    b = [card(4, 4, w - 14, h - 14, PAPER, TEXT, TEXT, 3, 6)]
    pw = 240
    px, py = 32, 32
    b.append(rect(px + 6, py + 6, pw, pw, TEXT))
    b.append(rect(px, py, pw, pw, ACCENT, TEXT, 3))
    b.append(image(cover(os.path.join(SRC, "profile.webp"), pw * 2, pw * 2, pixel_art=True), px + 3, py + 3, pw - 6, pw - 6))

    tx = px + pw + 40
    tw_max = w - tx - 40
    bd, _ = badge(tx, 34, "POSTED 2026", 12)
    b.append(bd)
    b.append(text("GUNAWAN WIBISONO.", tx, 96, 28, TEXT, 0.6))
    body = ("Started from attending GameDev miniclass and drawing pixel art to doing personal "
            "project and getting into Game Industry, I hope I can be a successful game developer "
            "in the future.")
    y = 126
    for line in BODY.wrap(body, 17, tw_max):
        b.append(text(line, tx, y, 17, MUTED, font=BODY))
        y += 20

    facts = [("FIELD", "Game Development"), ("LOCATION", "Malang, Jawa Timur, Indonesia"),
             ("TOOLS", "Unity, C#, Aseprite")]
    y += 14
    for label, value in facts:
        b.append(rect(tx, y - 16, tw_max, 1, BAND_LINE))
        b.append(text(label, tx, y + 4, 10, MUTED, 1.0))
        b.append(text(value, tx + 110, y + 5, 16, TEXT, font=BODY))
        y += 32
    save("about.svg", svg(w, h, "".join(b), "Gunawan Wibisono — about"))


def build_button(name: str, label: str, primary: bool = False, width: int | None = None) -> None:
    size = 12
    tw = F.measure(label, size, 1.3)
    w = (tw + 32) if width is None else width
    h = 38
    bg = ACCENT if primary else PAPER
    fg = ON_ACCENT if primary else TEXT
    b = [rect(3, 3, w, h, TEXT), rect(0, 0, w, h, bg, TEXT, 3)]
    b.append(text(label, w / 2, h / 2 + size * 0.36, size, fg, 1.3, "middle"))
    save(f"{name}.svg", svg(w + 3, h + 3, "".join(b), label))


def build_skyline() -> None:
    w, h = W, 58
    b = [rect(0, 0, w, h, "none")]
    # deterministic pseudo-random skyline
    seed = 1337
    x = 0
    while x < w:
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        bw = 18 + (seed >> 16) % 34
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        bh = 14 + (seed >> 16) % 40
        b.append(rect(x, h - bh, bw - 3, bh, TEXT))
        # windows
        wy = h - bh + 6
        while wy < h - 6:
            wx = x + 5
            while wx < x + bw - 9:
                if (wx * 7 + wy * 13) % 11 == 0:
                    b.append(rect(wx, wy, 4, 4, ACCENT))
                wx += 10
            wy += 10
        x += bw
    save("skyline.svg", svg(w, h, "".join(b), "Skyline"))


def _unused_banner() -> None:
    """Small 'posted 2026' style footer strip."""
    w, h = W, 46
    b = [rect(0, 0, w, h, BAND_BG)]
    b.append(text("CODES, ARTS, & DESIGN.", 18, 29, 12, BAND_TEXT, 1.2))
    b.append(text("HOROBOY.MY.ID", w - 18, 29, 12, ACCENT, 1.2, "end"))
    save("footer.svg", svg(w, h, "".join(b), "Footer"))



# --------------------------------------------------------------------------
# live GitHub stats (self-hosted: no third-party card service)
# --------------------------------------------------------------------------
STATS_CACHE = os.path.join(OUT, "stats.json")


def _api(path: str):
    url = f"https://api.github.com{path}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "HooroBoy-profile-readme",
        "Accept": "application/vnd.github+json",
    })
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_stats() -> dict:
    """Public numbers only, so it also works without a token."""
    user = _api("/users/HooroBoy")
    repos: list[dict] = []
    page = 1
    while True:
        chunk = _api(f"/users/HooroBoy/repos?per_page=100&page={page}&sort=pushed")
        repos += chunk
        if len(chunk) < 100:
            break
        page += 1

    own = [r for r in repos if not r["fork"]]
    recent = sorted(own, key=lambda r: r["pushed_at"], reverse=True)[:3]
    return {
        "repos": user["public_repos"],
        "stars": sum(r["stargazers_count"] for r in own),
        "followers": user["followers"],
        "following": user["following"],
        "recent": [
            {"name": r["name"], "language": r.get("language") or "-",
             "pushed": r["pushed_at"][:7]}
            for r in recent
        ],
        "updated": __import__("datetime").date.today().isoformat(),
    }


def build_stats() -> None:
    try:
        st = fetch_stats()
        with open(STATS_CACHE, "w", encoding="utf-8") as fh:
            json.dump(st, fh, indent=1, sort_keys=True)
    except Exception as e:  # offline build: fall back to the last snapshot
        print(f"  ! stats fetch failed ({e}); using cached snapshot")
        with open(STATS_CACHE, encoding="utf-8") as fh:
            st = json.load(fh)

    w, h = W, 268
    b = [card(4, 4, w - 14, h - 14, PAPER, TEXT, TEXT, 3, 6)]

    numbers = [("PUBLIC REPOS", st["repos"]), ("TOTAL STARS", st["stars"]),
               ("FOLLOWERS", st["followers"]), ("FOLLOWING", st["following"])]
    colw = (w - 80) / 4
    for i, (label, value) in enumerate(numbers):
        cx = 32 + i * colw
        if i:
            b.append(rect(cx - 22, 28, 1, 62, BAND_LINE))
        b.append(text(str(value), cx, 72, 34, ACCENT, 0.5))
        b.append(text(label, cx, 94, 10, MUTED, 1.0))

    b.append(rect(32, 116, w - 64, 2, TEXT))
    b.append(text("RECENTLY PUSHED", 32, 142, 10, MUTED, 1.2))

    y = 172
    for r in st["recent"]:
        lang = r["language"].upper()
        lw = F.measure(lang, 10, 0.8) + 16
        pill_x = w - 32 - lw - 76
        name = r["name"]
        room = pill_x - 48 - 12
        while name and BODY.measure(name, 17, 0.2) > room:
            name = name[:-1]
        if name != r["name"]:
            name = name[:-2] + ".." if len(name) > 3 else name
        b.append(rect(32, y - 10, 7, 7, ACCENT))
        b.append(text(name, 48, y, 17, TEXT, 0.2, font=BODY))
        b.append(rect(pill_x, y - 13, lw, 21, PAPER, MUTED, 2))
        b.append(text(lang, pill_x + 8, y + 2, 10, MUTED, 0.8))
        b.append(text(r["pushed"], w - 32, y + 2, 11, MUTED, 0.9, "end"))
        y += 27

    b.append(text(f"UPDATED {st['updated']}", 32, 248, 10, MUTED, 0.9))

    save("stats.svg", svg(w, h, "".join(b), "GitHub stats"))


# --------------------------------------------------------------------------
# README
# --------------------------------------------------------------------------


def build_readme() -> None:
    def link(href: str, img: str, alt: str, width: int | None = None, target_blank: bool = False) -> str:
        wa = f' width="{width}"' if width else ""
        tb = ' target="_blank"' if target_blank else ""
        return f'<a href="{href}"{tb}><img src="./assets/{img}" alt="{alt}"{wa}></a>'

    game_cells = "\n".join(
        link(f"{SITE}/projects/{g['slug']}/", f"card-{g['slug']}.svg", g["title"]) for g in GAMES
    )
    pixel_cells = "\n".join(
        link(f"{SITE}/pixels/", f"pixel-{slug}.svg", f"{title} ({year})") for slug, title, year, _ in PIXELS
    )

    stats = '<img src="./assets/stats.svg" alt="GitHub stats" width="880">'

    readme = f"""<!-- Generated by scripts/build_readme.py — edit that file, not this one. -->
<p align="center">
{link(SITE, "hero.svg", "Horoboy — CODES, ARTS, &amp; DESIGN.", 880)}
</p>

<p align="center">
{link(f"{SITE}/#projects", "btn-projects.svg", "See projects")}
{link(f"{SITE}/#about", "btn-about.svg", "About me")}
</p>

<p align="center">
{link(SITE, "marquee.svg", "Unity, C#, Game Design, Pixel Art, 3D Modeling, Aseprite, Blender, Level Design, Prototyping, UI/UX", 880)}
</p>

<img src="./assets/sec-projects.svg" alt="Fresh from the build — Featured projects" width="880">

<p align="center">
{game_cells}
</p>

<p align="center">
{link(f"{SITE}/#projects", "btn-all-projects.svg", "All projects")}
</p>

<img src="./assets/sec-pixels.svg" alt="Through the pixel — Pixel art" width="880">

<p align="center">
{pixel_cells}
</p>

<p align="center">
{link(f"{SITE}/pixels/", "btn-gallery.svg", "Full gallery")}
</p>

<img src="./assets/sec-experience.svg" alt="Experience and education — the path so far" width="880">

**Ariverse Studio** — 3 roles

| Role | Period | What I do |
| --- | --- | --- |
| **Project Manager** | 2026 — Now | Managing game development projects so they hit the quality bar, and keeping the team in shape to finish every task the studio hands over. |
| **Level Designer** | 2026 — Now | Blockouts, pacing and encounter design. Builds and tunes levels in Unity from first sketch to ship, driven by playtests and clear design docs. |
| **2D Pixel Artist** | 2025 — Now | Creating pixel assets for game projects and implementing them ready-to-use in the studio production pipeline. |

**Polinema** — Bachelor of Applied Informatics Engineering · 2024 — Now

Building a practical foundation in software development while specializing through independent
and collaborative game projects. Coursework and production work connect programming fundamentals
with Unity development, interface design and pixel art.

<img src="./assets/sec-about.svg" alt="Who is this — Gunawan Wibisono" width="880">

<img src="./assets/about.svg" alt="Gunawan Wibisono — Game Development, Malang Jawa Timur, Unity / C# / Aseprite" width="880">

<p align="center">
{link("mailto:gunawanwi376@gmail.com", "btn-email.svg", "Email")}
{link("https://github.com/HooroBoy", "btn-github.svg", "GitHub", target_blank=True)}
{link("https://horoboy.itch.io/", "btn-itch.svg", "Itch.io", target_blank=True)}
{link("https://www.linkedin.com/in/gunawanwi/", "btn-linkedin.svg", "LinkedIn", target_blank=True)}
{link("https://www.instagram.com/horo_cope/", "btn-instagram.svg", "Instagram", target_blank=True)}
</p>

<img src="./assets/sec-stats.svg" alt="GitHub stats" width="880">

{stats}

<img src="./assets/skyline.svg" alt="" width="880">
"""
    with open(os.path.join(ROOT, "README.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(readme)
    print(f"  README.md                       {len(readme)/1024:6.1f} KB")


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    print("assets:")
    build_hero()
    build_marquee()
    build_heading("sec-projects.svg", "FRESH FROM THE BUILD", "FEATURED PROJECTS",
                  "Games built from scratch — mostly Unity, C#, and pixel art.")
    build_heading("sec-pixels.svg", "THROUGH THE PIXEL", "PIXEL ART", "Featured art projects.")
    build_heading("sec-experience.svg", "EXPERIENCE & EDUCATION", "THE PATH SO FAR",
                  "Roles, coursework, and side projects that shaped how I build games.")
    build_heading("sec-about.svg", "WHO IS THIS", "ABOUT ME")
    build_heading("sec-stats.svg", "BY THE NUMBERS", "GITHUB STATS")
    ch = max(game_card_height(CARD_W, len(BODY.wrap(g["desc"], 15, CARD_W - 28)[:2])) for g in GAMES)
    for g in GAMES:
        save(f"card-{g['slug']}.svg", build_game_card(g, ch))
    for slug, title, year, path in PIXELS:
        save(f"pixel-{slug}.svg", build_pixel_card(title, year, path))
    build_about()
    build_button("btn-projects", "SEE PROJECTS", primary=True)
    build_button("btn-about", "ABOUT ME")
    build_button("btn-all-projects", "ALL PROJECTS")
    build_button("btn-gallery", "FULL GALLERY")
    build_button("btn-email", "EMAIL")
    build_button("btn-github", "GITHUB")
    build_button("btn-itch", "ITCH.IO")
    build_button("btn-linkedin", "LINKEDIN")
    build_button("btn-instagram", "INSTAGRAM")
    build_stats()
    build_skyline()
    print("readme:")
    build_readme()


if __name__ == "__main__":
    main()
