"""Channel art: YouTube banner (2560x1440, logo inside the 1546x423 safe area) and profile picture (800x800).

    python -m curio.branding    # writes assets/branding/banner.png and profile.png
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
GOLD, GOLD_DARK, NAVY, NAVY_DEEP = "#f2c14e", "#b8862b", "#16213e", "#0b1023"


def svg_png(svg: str, w: int, h: int) -> Image.Image:
    return Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svg.encode(), output_width=w, output_height=h))).convert("RGBA")


def compass(cx: float, cy: float, r: float, opacity: float = 1.0, ring: bool = True) -> str:
    """A compass rose: long N/E/S/W points, short diagonals, double ring with ticks."""
    out = f'<g opacity="{opacity}" transform="translate({cx},{cy})">'
    if ring:
        out += (f'<circle r="{r}" fill="none" stroke="{GOLD}" stroke-width="{r * .035}"/>'
                f'<circle r="{r * .88}" fill="none" stroke="{GOLD}" stroke-width="{r * .012}"/>')
        for i in range(72):
            a = i * math.pi / 36
            l = r * (.08 if i % 6 == 0 else .04)
            out += (f'<line x1="{(r * .88) * math.cos(a):.1f}" y1="{(r * .88) * math.sin(a):.1f}" '
                    f'x2="{(r * .88 - l) * math.cos(a):.1f}" y2="{(r * .88 - l) * math.sin(a):.1f}" '
                    f'stroke="{GOLD}" stroke-width="{r * .01:.1f}"/>')
    for k, (length, width) in enumerate([(r * .82, r * .13)] * 4 + [(r * .5, r * .09)] * 4):
        a = (k % 4) * math.pi / 2 + (math.pi / 4 if k >= 4 else 0)
        tip = (length * math.sin(a), -length * math.cos(a))
        left = (width * math.sin(a - math.pi / 2), -width * math.cos(a - math.pi / 2))
        right = (-left[0], -left[1])
        out += (f'<path d="M0,0 L{left[0]:.1f},{left[1]:.1f} L{tip[0]:.1f},{tip[1]:.1f} Z" fill="{GOLD}"/>'
                f'<path d="M0,0 L{right[0]:.1f},{right[1]:.1f} L{tip[0]:.1f},{tip[1]:.1f} Z" fill="{GOLD_DARK}"/>')
    return out + "</g>"


def stars(rnd, W, H, n):
    return "".join(f'<circle cx="{rnd.uniform(0, W):.0f}" cy="{rnd.uniform(0, H):.0f}" r="{rnd.choice([1.5, 2, 2.5, 3.5])}" '
                   f'fill="#fff6dc" opacity="{rnd.uniform(.25, .8):.2f}"/>' for _ in range(n))


def banner_svg(W=2560, H=1440) -> str:
    rnd = random.Random(11)
    s = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}"><defs>'
         f'<radialGradient id="g" cx=".5" cy=".5" r=".75"><stop offset="0" stop-color="#22325c"/>'
         f'<stop offset=".6" stop-color="{NAVY}"/><stop offset="1" stop-color="{NAVY_DEEP}"/></radialGradient></defs>'
         f'<rect width="{W}" height="{H}" fill="url(#g)"/>' + stars(rnd, W, H, 260))
    # faint map grid (latitude/longitude) for an explorer's-chart feel
    for x in range(0, W, 160):
        s += f'<line x1="{x}" y1="0" x2="{x}" y2="{H}" stroke="{GOLD}" stroke-width="1" opacity=".06"/>'
    for y in range(0, H, 160):
        s += f'<line x1="0" y1="{y}" x2="{W}" y2="{y}" stroke="{GOLD}" stroke-width="1" opacity=".06"/>'
    s += compass(330, H / 2, 280, .35) + compass(W - 330, H / 2, 280, .35)
    # thin gold rules framing the safe area
    s += (f'<line x1="{W / 2 - 560}" y1="{H / 2 - 175}" x2="{W / 2 + 560}" y2="{H / 2 - 175}" stroke="{GOLD}" stroke-width="3" opacity=".7"/>'
          f'<line x1="{W / 2 - 560}" y1="{H / 2 + 240}" x2="{W / 2 + 560}" y2="{H / 2 + 240}" stroke="{GOLD}" stroke-width="3" opacity=".7"/>')
    return s + "</svg>"


def profile_svg(S=800) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {S} {S}"><defs>'
            f'<radialGradient id="g" cx=".5" cy=".45" r=".7"><stop offset="0" stop-color="#26386a"/>'
            f'<stop offset="1" stop-color="{NAVY_DEEP}"/></radialGradient></defs>'
            f'<rect width="{S}" height="{S}" fill="url(#g)"/>'
            + compass(S / 2, S / 2, S * .40, 1.0)
            + f'<circle cx="{S / 2}" cy="{S / 2}" r="{S * .17}" fill="{NAVY}" stroke="{GOLD}" stroke-width="{S * .012}"/>'
            + "</svg>")


def main() -> None:
    cfg = json.loads((ROOT / "config.json").read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    W, H = 2560, 1440
    banner = svg_png(banner_svg(W, H), W, H)
    title = text_block(cfg["channel_name"].upper(), 165, 2400, fill=GOLD, stroke="#0b0805", family="serif")
    tag = text_block(cfg["tagline"], 56, 2400, fill="#fff6dc", stroke="#0b0805")
    for im in (title, tag):
        if im.width > 1540:
            im.thumbnail((1540, im.height))
    top = H / 2 - (title.height + tag.height - 40) / 2
    paste_scaled(banner, title, W / 2, top + title.height / 2)
    paste_scaled(banner, tag, W / 2, top + title.height - 40 + tag.height / 2)
    banner.convert("RGB").save(OUT / "banner.png", optimize=True)

    S = 800
    prof = svg_png(profile_svg(S), S, S)
    q = text_block("?", 230, 400, fill=GOLD, stroke="#0b0805", family="serif")
    paste_scaled(prof, q, S / 2, S / 2 + 6)
    prof.convert("RGB").save(OUT / "profile.png", optimize=True)
    print(f"wrote {OUT / 'banner.png'} and {OUT / 'profile.png'}")


if __name__ == "__main__":
    main()
