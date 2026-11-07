"""Original cast, procedural backgrounds and prop rendering.

Everything is drawn as SVG in code and rasterised with cairosvg, so the art
style stays consistent from episode to episode and no image API is needed.
"""
from __future__ import annotations

import io
import random
import re

import cairosvg
from PIL import Image

CAST = ["Tumble", "Pippa", "Moss"]

CAST_BIO = {
    "Tumble": "a cheerful, curious orange bear cub who loves to explore and sometimes rushes ahead",
    "Pippa": "a tiny, chatty blue bird who loves singing, counting and asking questions",
    "Moss": "a slow, calm, wise old green turtle who gives gentle advice",
}

SETTINGS = ["meadow", "forest", "beach", "garden", "pond", "snowy_hill", "bedroom"]
TIMES = ["morning", "day", "sunset", "night"]
EMOTIONS = ["happy", "sad", "surprised", "neutral"]

SPRITE = 400  # character viewBox size


def svg_to_image(svg: str, width: int, height: int | None = None) -> Image.Image:
    png = cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=width, output_height=height)
    return Image.open(io.BytesIO(png)).convert("RGBA")


# --------------------------------------------------------------------------- faces

def _eyes(cx1, cx2, cy, r, closed, emotion, color="#2b1d14"):
    if closed:
        return (f'<path d="M{cx1-r},{cy} q{r},{r*0.8} {2*r},0" stroke="{color}" stroke-width="6" fill="none" stroke-linecap="round"/>'
                f'<path d="M{cx2-r},{cy} q{r},{r*0.8} {2*r},0" stroke="{color}" stroke-width="6" fill="none" stroke-linecap="round"/>')
    big = 1.25 if emotion == "surprised" else 1.0
    out = ""
    for cx in (cx1, cx2):
        out += (f'<ellipse cx="{cx}" cy="{cy}" rx="{r*big}" ry="{r*1.2*big}" fill="{color}"/>'
                f'<circle cx="{cx + r*0.35}" cy="{cy - r*0.45}" r="{r*0.38}" fill="#fff"/>')
    if emotion == "sad":
        out += (f'<path d="M{cx1-r*1.4},{cy-r*1.9} l{r*2},{-r*0.7}" stroke="{color}" stroke-width="5" stroke-linecap="round"/>'
                f'<path d="M{cx2+r*1.4},{cy-r*1.9} l{-r*2},{-r*0.7}" stroke="{color}" stroke-width="5" stroke-linecap="round"/>')
    return out


def _mouth(cx, cy, w, open_, emotion, color="#5a2a1a"):
    if emotion == "surprised" or (open_ and emotion == "neutral"):
        h = w * (0.55 if open_ else 0.35)
        return f'<ellipse cx="{cx}" cy="{cy + h/3}" rx="{w*0.32}" ry="{h/2}" fill="{color}"/>'
    if emotion == "sad":
        if open_:
            return f'<path d="M{cx-w/2},{cy+w*0.35} q{w/2},{-w*0.6} {w},0 z" fill="{color}"/>'
        return f'<path d="M{cx-w/2},{cy+w*0.3} q{w/2},{-w*0.45} {w},0" stroke="{color}" stroke-width="6" fill="none" stroke-linecap="round"/>'
    if open_:  # happy / neutral talking
        return (f'<path d="M{cx-w/2},{cy} q{w/2},{w*0.9} {w},0 z" fill="{color}"/>'
                f'<path d="M{cx-w*0.25},{cy+w*0.3} q{w*0.25},{w*0.18} {w*0.5},0" fill="#e86a7a"/>')
    if emotion == "neutral":
        return f'<path d="M{cx-w*0.35},{cy+6} h{w*0.7}" stroke="{color}" stroke-width="6" stroke-linecap="round"/>'
    return f'<path d="M{cx-w/2},{cy} q{w/2},{w*0.55} {w},0" stroke="{color}" stroke-width="6" fill="none" stroke-linecap="round"/>'


def _wrap(body: str) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SPRITE} {SPRITE}">{body}</svg>'


# --------------------------------------------------------------------------- cast

def tumble_svg(mouth_open=False, eyes_closed=False, emotion="happy") -> str:
    o, d, b = "#f59a3c", "#c96f1f", "#fde2bf"
    return _wrap(
        f'<ellipse cx="200" cy="385" rx="110" ry="12" fill="#000" opacity=".15"/>'
        f'<ellipse cx="150" cy="370" rx="38" ry="22" fill="{d}"/><ellipse cx="250" cy="370" rx="38" ry="22" fill="{d}"/>'
        f'<ellipse cx="200" cy="295" rx="95" ry="85" fill="{o}"/>'
        f'<ellipse cx="200" cy="310" rx="58" ry="55" fill="{b}"/>'
        f'<ellipse cx="110" cy="285" rx="24" ry="40" fill="{d}" transform="rotate(25 110 285)"/>'
        f'<ellipse cx="290" cy="285" rx="24" ry="40" fill="{d}" transform="rotate(-25 290 285)"/>'
        f'<circle cx="122" cy="72" r="36" fill="{o}"/><circle cx="122" cy="72" r="20" fill="{b}"/>'
        f'<circle cx="278" cy="72" r="36" fill="{o}"/><circle cx="278" cy="72" r="20" fill="{b}"/>'
        f'<circle cx="200" cy="145" r="100" fill="{o}"/>'
        f'<ellipse cx="200" cy="180" rx="50" ry="38" fill="{b}"/>'
        f'<ellipse cx="200" cy="162" rx="16" ry="11" fill="#3b2314"/>'
        f'<circle cx="140" cy="180" r="13" fill="#ff8a8a" opacity=".55"/><circle cx="260" cy="180" r="13" fill="#ff8a8a" opacity=".55"/>'
        + _eyes(162, 238, 125, 11, eyes_closed, emotion)
        + _mouth(200, 182, 34, mouth_open, emotion)
    )


def pippa_svg(mouth_open=False, eyes_closed=False, emotion="happy") -> str:
    bl, dk, bel = "#4aa8ff", "#2b7fd6", "#d8eeff"
    beak = ('<path d="M200,190 l-26,-14 l52,0 z" fill="#ffb43b"/><path d="M200,202 l-22,-8 l44,0 z" fill="#f08a1c"/>'
            if mouth_open else '<path d="M174,180 l26,22 l26,-22 z" fill="#ffb43b"/>')
    if emotion == "surprised" and not mouth_open:
        beak = '<path d="M176,180 l24,14 l24,-14 z" fill="#ffb43b"/><circle cx="200" cy="200" r="7" fill="#f08a1c"/>'
    return _wrap(
        f'<ellipse cx="200" cy="385" rx="80" ry="10" fill="#000" opacity=".15"/>'
        f'<path d="M178,330 v45 m-12,0 h24 M222,330 v45 m-12,0 h24" stroke="#f08a1c" stroke-width="7" stroke-linecap="round"/>'
        f'<path d="M190,95 q-10,-50 20,-60 q-5,30 5,55 z" fill="{dk}"/>'
        f'<path d="M205,92 q15,-45 40,-40 q-20,20 -18,48 z" fill="{bl}"/>'
        f'<ellipse cx="200" cy="215" rx="118" ry="122" fill="{bl}"/>'
        f'<ellipse cx="200" cy="260" rx="70" ry="68" fill="{bel}"/>'
        f'<path d="M95,215 q-55,30 -30,95 q35,-20 50,-60 z" fill="{dk}"/>'
        f'<path d="M305,215 q55,30 30,95 q-35,-20 -50,-60 z" fill="{dk}"/>'
        f'<circle cx="140" cy="200" r="12" fill="#ff8aa8" opacity=".55"/><circle cx="260" cy="200" r="12" fill="#ff8aa8" opacity=".55"/>'
        + _eyes(160, 240, 160, 13, eyes_closed, emotion)
        + beak
    )


def moss_svg(mouth_open=False, eyes_closed=False, emotion="happy") -> str:
    g, dg, sh, shd = "#8fd16a", "#5fa743", "#7b5a36", "#5c4126"
    hexes = "".join(
        f'<path d="M{x},{y} l22,-13 l22,13 v26 l-22,13 l-22,-13 z" fill="#93703f" stroke="{shd}" stroke-width="4"/>'
        for x, y in [(126, 238), (176, 214), (226, 238), (151, 280), (201, 280), (101, 280), (251, 280)]
    )
    return _wrap(
        f'<ellipse cx="200" cy="388" rx="150" ry="12" fill="#000" opacity=".15"/>'
        f'<ellipse cx="105" cy="360" rx="30" ry="26" fill="{g}"/><ellipse cx="260" cy="360" rx="30" ry="26" fill="{g}"/>'
        f'<path d="M50,345 q0,-170 155,-170 q155,0 155,170 z" fill="{sh}"/>'
        + hexes +
        f'<rect x="45" y="330" width="320" height="26" rx="13" fill="#c9a66b"/>'
        f'<path d="M345,330 q20,-25 10,-55" stroke="{g}" stroke-width="40" stroke-linecap="round" fill="none"/>'
        f'<circle cx="330" cy="175" r="68" fill="{g}"/>'
        f'<circle cx="300" cy="200" r="11" fill="#ff8a8a" opacity=".5"/>'
        f'<path d="M285,130 q20,-14 40,-4 M335,124 q18,-8 34,4" stroke="{dg}" stroke-width="6" fill="none" stroke-linecap="round"/>'
        + _eyes(305, 352, 158, 10, eyes_closed, emotion, "#1e2a14")
        + _mouth(332, 198, 30, mouth_open, emotion, "#2f4a1f")
    )


CHAR_FUNCS = {"Tumble": tumble_svg, "Pippa": pippa_svg, "Moss": moss_svg}
CHAR_SCALE = {"Tumble": 1.0, "Pippa": 0.72, "Moss": 0.95}


def character_sprites(name: str, size: int) -> dict:
    """Pre-render every pose of a character: (emotion, mouth_open, eyes_closed) -> RGBA image."""
    fn = CHAR_FUNCS[name]
    px = int(size * CHAR_SCALE[name])
    return {
        (emo, m, e): svg_to_image(fn(m, e, emo), px)
        for emo in EMOTIONS for m in (False, True) for e in (False, True)
    }


# --------------------------------------------------------------------------- backgrounds

SKY = {
    "morning": ("#ffd9a8", "#9fd8ff"),
    "day": ("#6ec6ff", "#d6f1ff"),
    "sunset": ("#ff8a65", "#ffd27a"),
    "night": ("#0d1b4a", "#3a3f8f"),
}


def _sky(time, W, H, rnd):
    top, bot = SKY[time]
    s = (f'<defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{top}"/>'
         f'<stop offset="1" stop-color="{bot}"/></linearGradient></defs><rect width="{W}" height="{H}" fill="url(#sky)"/>')
    if time == "night":
        for _ in range(70):
            s += f'<circle cx="{rnd.randint(0, W)}" cy="{rnd.randint(0, int(H*.55))}" r="{rnd.choice([2, 2, 3, 4])}" fill="#fff8d0" opacity="{rnd.uniform(.5, 1):.2f}"/>'
        s += f'<circle cx="{W*.8}" cy="{H*.18}" r="70" fill="#fff6c8"/><circle cx="{W*.8+30}" cy="{H*.18-15}" r="62" fill="{top}"/>'
    else:
        sx, sy = (W * .15, H * .2) if time != "sunset" else (W * .75, H * .48)
        col = "#ffe066" if time != "sunset" else "#ffb347"
        s += f'<circle cx="{sx}" cy="{sy}" r="95" fill="{col}" opacity=".35"/><circle cx="{sx}" cy="{sy}" r="70" fill="{col}"/>'
        for _ in range(rnd.randint(3, 5)):
            cx, cy, k = rnd.randint(250, W - 150), rnd.randint(70, int(H * .35)), rnd.uniform(.7, 1.3)
            s += "".join(f'<circle cx="{cx+dx*k}" cy="{cy+dy*k}" r="{r*k}" fill="#fff" opacity=".92"/>'
                         for dx, dy, r in [(0, 0, 45), (50, -20, 55), (100, 0, 45), (50, 15, 45)])
    return s


def _hills(W, H, colors, base, rnd):
    s = ""
    for i, c in enumerate(colors):
        y = base - 140 + i * 70
        pts = f"M0,{H} L0,{y} "
        for x in range(0, W + 400, 400):
            pts += f"Q{x+200},{y - rnd.randint(40, 120)} {x+400},{y} "
        s += f'<path d="{pts} L{W},{H} z" fill="{c}"/>'
    return s


def _tree(x, y, k, leaf="#4caf50", trunk="#8d5a2b"):
    return (f'<rect x="{x-14*k}" y="{y-120*k}" width="{28*k}" height="{120*k}" rx="{8*k}" fill="{trunk}"/>'
            f'<circle cx="{x}" cy="{y-170*k}" r="{75*k}" fill="{leaf}"/><circle cx="{x-55*k}" cy="{y-130*k}" r="{50*k}" fill="{leaf}"/>'
            f'<circle cx="{x+55*k}" cy="{y-130*k}" r="{50*k}" fill="{leaf}"/>')


def _pine(x, y, k, col="#2e7d4f", snow=False):
    s = f'<rect x="{x-10*k}" y="{y-40*k}" width="{20*k}" height="{40*k}" fill="#6d4524"/>'
    for i in range(3):
        w, top = (90 - i * 22) * k, y - (40 + i * 55) * k
        s += f'<path d="M{x-w},{top} L{x},{top-90*k} L{x+w},{top} z" fill="{col}"/>'
        if snow:
            s += f'<path d="M{x-w*.35},{top-60*k} L{x},{top-90*k} L{x+w*.35},{top-60*k} z" fill="#fff"/>'
    return s


def _flower(x, y, rnd):
    c = rnd.choice(["#ff6f91", "#ffc75f", "#f9f871", "#c34a9b", "#ff9671", "#fff"])
    return (f'<path d="M{x},{y} v-28" stroke="#3f8f3a" stroke-width="4"/>'
            + "".join(f'<circle cx="{x+dx}" cy="{y-30+dy}" r="8" fill="{c}"/>' for dx, dy in [(-8, 0), (8, 0), (0, -8), (0, 8)])
            + f'<circle cx="{x}" cy="{y-30}" r="6" fill="#ffde59"/>')


def background_svg(setting: str, time: str, W: int, H: int, seed: int) -> str:
    rnd = random.Random(seed)
    ground = int(H * 0.84)
    night = time == "night"
    dim = '<rect width="100%" height="100%" fill="#0a1033" opacity=".35"/>' if night else ""
    if setting == "bedroom":
        win = _sky(time, 520, 380, rnd)
        s = (f'<rect width="{W}" height="{H}" fill="#ffe8d6"/>'
             + "".join(f'<rect x="{x}" y="0" width="60" height="{ground}" fill="#ffd9c0"/>' for x in range(0, W, 120))
             + f'<rect y="{ground}" width="{W}" height="{H-ground}" fill="#c8915e"/>'
             f'<svg x="{W*.62}" y="120" width="520" height="380" viewBox="0 0 520 380">{win}</svg>'
             f'<rect x="{W*.62}" y="120" width="520" height="380" fill="none" stroke="#fff" stroke-width="22"/>'
             f'<path d="M{W*.62+260},120 v380 M{W*.62},310 h520" stroke="#fff" stroke-width="12"/>'
             f'<rect x="80" y="{ground-230}" width="420" height="160" rx="30" fill="#7fb7ff"/>'
             f'<rect x="80" y="{ground-290}" width="40" height="290" rx="12" fill="#9b6b43"/>'
             f'<rect x="460" y="{ground-200}" width="40" height="200" rx="12" fill="#9b6b43"/>'
             f'<ellipse cx="200" cy="{ground-240}" rx="75" ry="35" fill="#fff"/>'
             f'<ellipse cx="{W/2}" cy="{ground+70}" rx="430" ry="55" fill="#ff9e9e" opacity=".7"/>'
             f'<rect x="{W*.36}" y="200" width="300" height="20" fill="#9b6b43"/>'
             f'<rect x="{W*.36+20}" y="150" width="40" height="50" fill="#ff6f91"/><rect x="{W*.36+70}" y="140" width="34" height="60" fill="#4aa8ff"/>'
             f'<circle cx="{W*.36+200}" cy="170" r="28" fill="#ffc75f"/>')
        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}">{s}{dim}</svg>'

    s = _sky(time, W, H, rnd)
    if setting == "snowy_hill":
        s += _hills(W, H, ["#e3f0ff", "#f4f9ff", "#ffffff"], ground, rnd)
        for _ in range(7):
            s += _pine(rnd.randint(0, W), ground - rnd.randint(40, 110), rnd.uniform(.6, 1.1), snow=True)
        s += f'<rect y="{ground}" width="{W}" height="{H-ground}" fill="#fbfdff"/>'
        for _ in range(90):
            s += f'<circle cx="{rnd.randint(0, W)}" cy="{rnd.randint(0, H)}" r="{rnd.choice([3, 4, 5])}" fill="#fff" opacity=".85"/>'
    elif setting == "beach":
        s += f'<rect y="{H*.5}" width="{W}" height="{H*.2}" fill="#3fa9e0"/>'
        for x in range(0, W, 160):
            s += f'<path d="M{x},{H*.56} q40,-18 80,0" stroke="#bfe9ff" stroke-width="6" fill="none"/>'
        s += f'<path d="M0,{H*.68} Q{W/2},{H*.62} {W},{H*.68} L{W},{H} L0,{H} z" fill="#f7d79c"/>'
        for _ in range(10):
            x, y = rnd.randint(40, W - 40), rnd.randint(int(H * .74), H - 30)
            s += f'<path d="M{x},{y} q14,-24 28,0 z" fill="{rnd.choice(["#ffb3c1", "#fff2cc", "#ffd6a5"])}"/>'
        s += (f'<path d="M{W*.08},{ground} q-20,-200 40,-330" stroke="#8d5a2b" stroke-width="26" fill="none"/>'
              + "".join(f'<path d="M{W*.08+40},{ground-330} q{dx},{dy} {dx*1.8},{dy*.3+60}" stroke="#3c9d4e" stroke-width="22" fill="none" stroke-linecap="round"/>'
                        for dx, dy in [(-120, -60), (120, -60), (-90, 10), (100, 20)]))
    else:
        greens = {"meadow": ["#9ad66b", "#7cc35a", "#64b04c"], "forest": ["#5d9c4a", "#4c8a3d", "#3f7a33"],
                  "garden": ["#a3d977", "#8bc964", "#73b850"], "pond": ["#98d46a", "#80c45a", "#69b14d"]}[setting]
        s += _hills(W, H, greens, ground, rnd)
        if setting == "forest":
            for _ in range(9):
                s += _tree(rnd.randint(0, W), ground - rnd.randint(20, 90), rnd.uniform(.8, 1.4), rnd.choice(["#3e8e41", "#2e7d32", "#4caf50"]))
            for _ in range(5):
                x = rnd.randint(50, W - 50)
                s += f'<rect x="{x-6}" y="{ground+20}" width="12" height="22" fill="#fff3e0"/><path d="M{x-24},{ground+22} q24,-34 48,0 z" fill="#e53935"/>'
        else:
            for _ in range(3):
                s += _tree(rnd.choice([rnd.randint(60, 400), rnd.randint(W - 400, W - 60)]), ground - rnd.randint(30, 80), rnd.uniform(.7, 1.0))
        if setting == "garden":
            for x in range(0, W, 70):
                s += f'<rect x="{x}" y="{ground-130}" width="40" height="130" rx="8" fill="#fff6e8"/>'
            s += f'<rect y="{ground-105}" width="{W}" height="16" fill="#fff6e8"/><rect y="{ground-50}" width="{W}" height="16" fill="#fff6e8"/>'
        s += f'<rect y="{ground}" width="{W}" height="{H-ground}" fill="{greens[-1]}"/>'
        if setting == "pond":
            s += f'<ellipse cx="{W*.5}" cy="{ground+45}" rx="{W*.3}" ry="70" fill="#4fb3e8"/><ellipse cx="{W*.5}" cy="{ground+35}" rx="{W*.26}" ry="45" fill="#7dccf2"/>'
            for _ in range(5):
                x = rnd.randint(int(W * .25), int(W * .75))
                s += f'<ellipse cx="{x}" cy="{ground+40+rnd.randint(-20, 20)}" rx="34" ry="12" fill="#3c9d4e"/>'
            for x in (W * .17, W * .2, W * .8, W * .83):
                s += f'<path d="M{x},{ground+40} v-140" stroke="#5b8c32" stroke-width="7"/><rect x="{x-8}" y="{ground-130}" width="16" height="50" rx="8" fill="#7a4b26"/>'
        for _ in range(40 if setting in ("meadow", "garden") else 12):
            s += _flower(rnd.randint(0, W), rnd.randint(ground + 10, H - 10), rnd)
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}">{s}{dim}</svg>'


# --------------------------------------------------------------------------- props

FALLBACK_PROP = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 300">'
                 '<path d="M150,20 L185,110 L280,115 L205,175 L232,270 L150,215 L68,270 L95,175 L20,115 L115,110 Z" '
                 'fill="#ffd54f" stroke="#f9a825" stroke-width="10" stroke-linejoin="round"/>'
                 '<circle cx="120" cy="150" r="10" fill="#5d4037"/><circle cx="180" cy="150" r="10" fill="#5d4037"/>'
                 '<path d="M125,185 q25,20 50,0" stroke="#5d4037" stroke-width="8" fill="none" stroke-linecap="round"/></svg>')

_BANNED = re.compile(r"<\s*(script|image|foreignObject|use|iframe|object|embed|style)\b|<!ENTITY|<!DOCTYPE|href\s*=|url\(\s*['\"]?(?!#)|\bon\w+\s*=",
                     re.IGNORECASE)


def sanitize_svg(svg: str) -> str | None:
    """Accept only self-contained vector SVG (no external refs, scripts or entities)."""
    m = re.search(r"<svg\b.*</svg>", svg, re.DOTALL | re.IGNORECASE)
    if not m:
        return None
    svg = m.group(0)
    if _BANNED.search(svg) or len(svg) > 60_000:
        return None
    if "xmlns=" not in svg[:300]:
        svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    try:
        svg_to_image(svg, 64)
    except Exception:
        return None
    return svg
