"""Channel art: YouTube banner (2560x1440, key content inside the 1546x423 safe area) and profile picture (800x800).

    python -m kidtoon.branding    # writes assets/branding/banner.png and profile.png
"""
from __future__ import annotations

import io
import json
import math
import random
from pathlib import Path

import cairosvg
from PIL import Image

from .render import paste_scaled, text_block

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "branding"


def svg_png(svg: str, w: int, h: int) -> Image.Image:
    return Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svg.encode(), output_width=w, output_height=h))).convert("RGBA")


def maple_leaf(cx: float, cy: float, size: float, color: str, rot: float = 0, face: bool = False) -> str:
    """A rounded, friendly maple leaf centred on (cx, cy); `size` is its height."""
    half = [(100, 6), (113, 38), (131, 28), (125, 70), (152, 48), (159, 63), (182, 56), (171, 86),
            (192, 96), (151, 124), (159, 143), (121, 134), (113, 154), (104, 152)]
    pts = half + [(200 - x, y) for x, y in reversed(half)]
    k = size / 190
    d = "M" + " L".join(f"{(x - 100) * k:.1f},{(y - 95) * k:.1f}" for x, y in pts) + " Z"
    body = (f'<path d="{d}" fill="{color}" stroke="{color}" stroke-width="{size * 0.06:.1f}" stroke-linejoin="round"/>'
            f'<path d="M0,{60 * k:.1f} q{-6 * k:.1f},{26 * k:.1f} {6 * k:.1f},{48 * k:.1f}" stroke="#8a4b22" '
            f'stroke-width="{size * 0.05:.1f}" fill="none" stroke-linecap="round"/>')
    if face:
        e = size * 0.045
        body += (f'<ellipse cx="{-22 * k:.1f}" cy="{0 * k:.1f}" rx="{e:.1f}" ry="{e * 1.25:.1f}" fill="#3a1d0e"/>'
                 f'<ellipse cx="{22 * k:.1f}" cy="{0 * k:.1f}" rx="{e:.1f}" ry="{e * 1.25:.1f}" fill="#3a1d0e"/>'
                 f'<circle cx="{-19 * k:.1f}" cy="{-5 * k:.1f}" r="{e * .4:.1f}" fill="#fff"/>'
                 f'<circle cx="{25 * k:.1f}" cy="{-5 * k:.1f}" r="{e * .4:.1f}" fill="#fff"/>'
                 f'<circle cx="{-40 * k:.1f}" cy="{22 * k:.1f}" r="{e * 1.3:.1f}" fill="#ff9a8a" opacity=".7"/>'
                 f'<circle cx="{40 * k:.1f}" cy="{22 * k:.1f}" r="{e * 1.3:.1f}" fill="#ff9a8a" opacity=".7"/>'
                 f'<path d="M{-16 * k:.1f},{24 * k:.1f} q{16 * k:.1f},{18 * k:.1f} {32 * k:.1f},0" stroke="#3a1d0e" '
                 f'stroke-width="{size * 0.028:.1f}" fill="none" stroke-linecap="round"/>')
    return f'<g transform="translate({cx:.1f},{cy:.1f}) rotate({rot:.1f})">{body}</g>'


def cloud(x, y, s):
    return "".join(f'<circle cx="{x + dx * s:.0f}" cy="{y + dy * s:.0f}" r="{r * s:.0f}" fill="#fff" opacity=".95"/>'
                   for dx, dy, r in [(0, 0, 50), (55, -25, 62), (115, 0, 50), (58, 18, 50), (-40, 12, 36), (155, 14, 36)])


def tree(x, base, s, canopy=("#f26b38", "#e8562a", "#f9a03f")):
    out = f'<path d="M{x - 18 * s},{base} q{8 * s},{-90 * s} {4 * s},{-200 * s} h{28 * s} q{-6 * s},{110 * s} {10 * s},{200 * s} z" fill="#8a5a33"/>'
    for dx, dy, r, c in [(0, -260, 110, 0), (-95, -200, 85, 1), (95, -200, 85, 1), (-55, -320, 80, 2), (60, -315, 82, 2), (0, -190, 90, 0)]:
        out += f'<circle cx="{x + dx * s:.0f}" cy="{base + dy * s:.0f}" r="{r * s:.0f}" fill="{canopy[c]}"/>'
    return out


def flowers(rnd, x0, x1, y0, y1, n):
    out = ""
    for _ in range(n):
        x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
        c = rnd.choice(["#ff6f91", "#ffc75f", "#fff", "#c79bff", "#ff9671"])
        r = rnd.uniform(7, 12)
        out += "".join(f'<circle cx="{x + dx * r:.0f}" cy="{y + dy * r:.0f}" r="{r * .8:.0f}" fill="{c}"/>'
                       for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)])
        out += f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r * .6:.0f}" fill="#ffde59"/>'
    return out


def banner_svg(W=2560, H=1440) -> str:
    rnd = random.Random(7)
    s = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}"><defs>'
         '<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#7cc8f5"/>'
         '<stop offset=".6" stop-color="#c9ecff"/><stop offset="1" stop-color="#fff3d6"/></linearGradient>'
         '<radialGradient id="sun"><stop offset="0" stop-color="#fff6b0"/><stop offset=".55" stop-color="#ffd84d"/>'
         '<stop offset="1" stop-color="#ffd84d" stop-opacity="0"/></radialGradient></defs>'
         f'<rect width="{W}" height="{H}" fill="url(#sky)"/>')
    # sun with soft rays (just outside the safe area, visible on TV/desktop)
    sx, sy = 640, 330
    s += "".join(f'<path d="M{sx},{sy} L{sx + 900 * math.cos(a):.0f},{sy + 900 * math.sin(a):.0f} '
                 f'L{sx + 900 * math.cos(a + .09):.0f},{sy + 900 * math.sin(a + .09):.0f} Z" fill="#fff8cf" opacity=".28"/>'
                 for a in [i * math.pi / 9 for i in range(18)])
    s += f'<circle cx="{sx}" cy="{sy}" r="260" fill="url(#sun)"/><circle cx="{sx}" cy="{sy}" r="120" fill="#ffd84d"/>'
    for x, y, k in [(1050, 300, 1.0), (1700, 240, 1.25), (2150, 420, .9), (300, 560, .8), (1380, 470, .6)]:
        s += cloud(x, y, k)
    # rolling hills
    for i, (c, y) in enumerate([("#a6dc7c", 930), ("#8ccd62", 1000), ("#74bd4d", 1080)]):
        d = f"M0,{H} L0,{y} "
        for x in range(0, W + 640, 640):
            d += f"Q{x + 320},{y - 90 + i * 25} {x + 640},{y} "
        s += f'<path d="{d} L{W},{H} z" fill="{c}"/>'
    s += tree(330, 1100, 1.25) + tree(2240, 1110, 1.15, ("#f9a03f", "#f26b38", "#ffc75f"))
    s += flowers(rnd, 0, W, 1060, H - 20, 70)
    # drifting maple leaves
    for x, y, k, r in [(980, 980, 60, -20), (1640, 1010, 52, 25), (2000, 760, 46, 40), (560, 860, 50, -35),
                       (1260, 1060, 40, 10), (1880, 1120, 55, -15), (720, 1150, 44, 30)]:
        s += maple_leaf(x, y, k, rnd.choice(["#f26b38", "#f9a03f", "#e8562a"]), r)
    return s + "</svg>"


def profile_svg(S=800) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {S} {S}"><defs>'
            '<radialGradient id="bg" cx=".5" cy=".38" r=".7"><stop offset="0" stop-color="#fff7c2"/>'
            '<stop offset=".55" stop-color="#ffe07a"/><stop offset="1" stop-color="#ffc24a"/></radialGradient></defs>'
            f'<rect width="{S}" height="{S}" fill="url(#bg)"/>'
            f'<path d="M0,{S * .80} Q{S * .25},{S * .70} {S * .5},{S * .78} T{S},{S * .74} V{S} H0 z" fill="#8ccd62"/>'
            f'<path d="M0,{S * .88} Q{S * .3},{S * .80} {S * .6},{S * .88} T{S},{S * .85} V{S} H0 z" fill="#74bd4d"/>'
            + maple_leaf(S * .5, S * .47, S * .66, "#f26b38", -6, face=True)
            + "</svg>")


def main() -> None:
    cfg = json.loads((ROOT / "config.json").read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    W, H = 2560, 1440
    banner = svg_png(banner_svg(W, H), W, H)
    # logo inside the 1546x423 safe area that every device shows
    title = text_block(cfg["channel_name"], 122, 2400, fill="#ffffff", stroke="#e8562a")
    tag = text_block("Gentle stories for little ones", 58, 2400, fill="#fff6b0", stroke="#3d2a73")
    for im in (title, tag):  # keep the logo inside the safe area
        if im.width > 1540:
            im.thumbnail((1540, im.height))
    gap = -30
    top = H / 2 - (title.height + tag.height + gap) / 2
    paste_scaled(banner, title, W / 2, top + title.height / 2)
    paste_scaled(banner, tag, W / 2, top + title.height + gap + tag.height / 2)
    banner.convert("RGB").save(OUT / "banner.png", optimize=True)
    svg_png(profile_svg(800), 800, 800).convert("RGB").save(OUT / "profile.png", optimize=True)
    print(f"wrote {OUT / 'banner.png'} and {OUT / 'profile.png'}")


if __name__ == "__main__":
    main()
