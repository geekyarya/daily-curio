"""Turn illustrated shots + narration into a finished video (landscape video or vertical Short).

Each shot is a still illustration brought to life with an eased camera move (Ken Burns), crossfades between
shots, subtle particle overlays (dust, embers, snow...), list-item title cards, an animated intro and an end card.
"""
from __future__ import annotations

import math
import random
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import audio
from .images import cover
from .script import Shot

ROOT = Path(__file__).resolve().parent.parent
FONTS = {"sans": (ROOT / "assets" / "fonts" / "Montserrat.ttf", "ExtraBold"),
         "serif": (ROOT / "assets" / "fonts" / "Cinzel.ttf", "Black")}
FALLBACK_FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]

XFADE = 0.7
PAD_IN, PAD_OUT, GAP, MIN_SHOT = 0.25, 0.3, 0.12, 3.0
CARD_SECONDS = 3.4


# ----------------------------------------------------------------------------- text

def font(size: int, family: str = "sans") -> ImageFont.FreeTypeFont:
    path, weight = FONTS[family]
    if path.exists():
        f = ImageFont.truetype(str(path), size)
        try:
            f.set_variation_by_name(weight)
        except Exception:  # noqa: BLE001
            pass
        return f
    for p in FALLBACK_FONTS:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


def wrap(text: str, fnt, max_w: int) -> list[str]:
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    lines, cur = [], ""
    for w in text.split():
        trial = f"{cur} {w}".strip()
        if d.textlength(trial, font=fnt) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    return lines + ([cur] if cur else [])


def text_block(text: str, size: int, max_w: int, fill="#ffffff", stroke="#1b1408", family: str = "sans") -> Image.Image:
    """Bold outlined text with a soft shadow, as a transparent image."""
    fnt = font(size, family)
    lines = wrap(text, fnt, max_w)
    sw = max(4, size // 9)
    lh = int(size * 1.15)
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    pad = sw * 5  # room for the outline + blurred shadow, so it never gets clipped into a visible box
    w = int(max(probe.textlength(l, font=fnt) for l in lines)) + pad * 2
    h = lh * (len(lines) - 1) + size + pad * 2 + size // 4
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ds, d = ImageDraw.Draw(shadow), ImageDraw.Draw(img)
    for i, l in enumerate(lines):
        lw = d.textlength(l, font=fnt)
        x, y = (w - lw) / 2, pad + i * lh
        ds.text((x + sw, y + sw), l, font=fnt, fill=(0, 0, 0, 130), stroke_width=sw, stroke_fill=(0, 0, 0, 130))
        d.text((x, y), l, font=fnt, fill=fill, stroke_width=sw, stroke_fill=stroke)
    return Image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(sw)), img)


def paste_scaled(frame: Image.Image, im: Image.Image, cx: float, cy: float, scale: float = 1.0) -> None:
    if scale <= 0.01:
        return
    if abs(scale - 1) > 0.01:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BILINEAR)
    frame.paste(im, (int(cx - im.width / 2), int(cy - im.height / 2)), im)


def ease(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def pop(x: float) -> float:
    """Scale curve for pop-in text: 0 -> slight overshoot -> 1."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    return ease(x) + 0.2 * math.sin(x * math.pi) * (1 - x)


# ----------------------------------------------------------------------------- particles

class Particles:
    COUNTS = {"snow": 70, "rain": 90, "leaves": 22, "petals": 26, "bubbles": 22, "sparkles": 30, "fireflies": 26,
              "dust": 55, "embers": 45}

    def __init__(self, kind: str, W: int, H: int, seed: int):
        self.kind, self.W, self.H = kind, W, H
        rnd = random.Random(seed)
        self.p = [(rnd.random(), rnd.random(), rnd.uniform(.6, 1.4), rnd.uniform(0, 6.28))
                  for _ in range(self.COUNTS.get(kind, 0))]
        self.sprites = self._sprites(kind, max(W, H) / 1920) if self.p else []

    @staticmethod
    def _sprites(kind: str, u: float) -> list[Image.Image]:
        out: list[Image.Image] = []

        def canvas(s):
            return Image.new("RGBA", (s, s), (0, 0, 0, 0))

        if kind == "snow":
            for r in (5, 7, 9):
                s = int(r * 4 * u) + 2
                im = canvas(s)
                ImageDraw.Draw(im).ellipse((s / 4, s / 4, 3 * s / 4, 3 * s / 4), fill=(255, 255, 255, 230))
                out.append(im.filter(ImageFilter.GaussianBlur(1)))
        elif kind == "rain":
            s = int(40 * u)
            im = Image.new("RGBA", (4, s), (0, 0, 0, 0))
            ImageDraw.Draw(im).line((2, 0, 2, s), fill=(200, 225, 255, 150), width=2)
            out.append(im)
        elif kind in ("leaves", "petals"):
            cols = ([(240, 140, 40), (220, 90, 40), (250, 190, 60)] if kind == "leaves"
                    else [(255, 182, 203), (255, 205, 220), (250, 160, 190)])
            for c in cols:
                s = int(34 * u)
                base = canvas(s)
                ImageDraw.Draw(base).ellipse((s * .15, s * .35, s * .85, s * .65), fill=c + (235,))
                out += [base.rotate(a, resample=Image.BILINEAR) for a in range(0, 180, 30)]
        elif kind == "bubbles":
            for r in (14, 20, 28):
                s = int(r * 2.4 * u)
                im = canvas(s)
                d = ImageDraw.Draw(im)
                d.ellipse((2, 2, s - 3, s - 3), outline=(255, 255, 255, 200), width=max(2, int(3 * u)), fill=(200, 235, 255, 40))
                d.ellipse((s * .25, s * .2, s * .42, s * .35), fill=(255, 255, 255, 220))
                out.append(im)
        elif kind == "sparkles":
            for r in (14, 20):
                s = int(r * 3 * u)
                im = canvas(s)
                c = s / 2
                ImageDraw.Draw(im).polygon([(c, 0), (c * 1.15, c * .85), (s, c), (c * 1.15, c * 1.15), (c, s),
                                            (c * .85, c * 1.15), (0, c), (c * .85, c * .85)], fill=(255, 245, 190, 255))
                out.append(im.filter(ImageFilter.GaussianBlur(0.6)))
        elif kind == "dust":
            for r in (3, 4, 6):
                s = int(r * 5 * u) + 2
                im = canvas(s)
                ImageDraw.Draw(im).ellipse((s * .3, s * .3, s * .7, s * .7), fill=(255, 240, 210, 150))
                out.append(im.filter(ImageFilter.GaussianBlur(s * .12)))
        elif kind == "embers":
            for r, c in ((4, (255, 170, 60)), (6, (255, 120, 40)), (5, (255, 210, 120))):
                s = int(r * 6 * u) + 2
                im = canvas(s)
                ImageDraw.Draw(im).ellipse((s * .32, s * .32, s * .68, s * .68), fill=c + (255,))
                out.append(im.filter(ImageFilter.GaussianBlur(s * .1)))
        elif kind == "fireflies":
            s = int(36 * u)
            im = canvas(s)
            ImageDraw.Draw(im).ellipse((s * .3, s * .3, s * .7, s * .7), fill=(255, 240, 140, 255))
            out.append(im.filter(ImageFilter.GaussianBlur(s * .12)))
        return out

    def draw(self, frame: Image.Image, t: float) -> None:
        W, H, k = self.W, self.H, self.kind
        for i, (x0, y0, sp, ph) in enumerate(self.p):
            spr = self.sprites[i % len(self.sprites)]
            scale = 1.0
            if k == "snow":
                x, y = x0 * W + math.sin(t * .8 * sp + ph) * 30, (y0 * H + t * 70 * sp) % (H + 40) - 20
            elif k == "rain":
                x, y = (x0 * W - t * 120) % W, (y0 * H + t * 900 * sp) % (H + 60) - 30
            elif k in ("leaves", "petals"):
                spr = self.sprites[(i * 6 + int(t * 4 * sp)) % len(self.sprites)]
                x = (x0 * W + t * 60 * sp + math.sin(t * 1.3 + ph) * 50) % (W + 60) - 30
                y = (y0 * H + t * 55 * sp) % (H + 60) - 30
            elif k == "bubbles":
                x, y = x0 * W + math.sin(t * 1.1 * sp + ph) * 25, H + 40 - ((1 - y0) * H + t * 80 * sp) % (H + 80)
            elif k == "sparkles":
                x, y = x0 * W, y0 * H * 0.8
                scale = max(0.0, math.sin(t * 2.2 * sp + ph)) ** 3
            elif k == "dust":
                x = (x0 * W + t * 14 * sp + math.sin(t * .5 + ph) * 40) % W
                y = (y0 * H - t * 9 * sp + math.cos(t * .4 + ph) * 30) % H
                scale = 0.6 + 0.4 * math.sin(t * 1.5 * sp + ph)
            elif k == "embers":
                x = x0 * W + math.sin(t * 1.7 * sp + ph) * 35
                y = H + 30 - ((1 - y0) * H + t * 140 * sp) % (H + 60)
                scale = 0.5 + 0.5 * abs(math.sin(t * 4 * sp + ph))
            elif k == "fireflies":
                x, y = x0 * W + math.sin(t * .4 * sp + ph) * 60, y0 * H * .85 + math.cos(t * .5 * sp + ph) * 40
                scale = 0.55 + 0.45 * math.sin(t * 3 * sp + ph)
            else:
                return
            paste_scaled(frame, spr, x, y, scale)


# ----------------------------------------------------------------------------- timeline

@dataclass
class Seg:
    start: float
    end: float
    speaker: str
    text: str


@dataclass
class Timeline:
    shots: list[tuple[float, float]] = field(default_factory=list)
    segs: list[Seg] = field(default_factory=list)
    intro: float = 0.0
    outro: float = 0.0
    duration: float = 0.0


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'“])", text.strip())
    return [p for p in parts if p.strip()]


def record(shots: list[Shot], cfg: dict, work: Path, intro: float, outro: float, tag: str, log=print) -> tuple[Timeline, Path]:
    """Voice every sentence of narration and lay the shots out on a timeline."""
    voice_cfg = cfg["narrator_voice"]
    sr = audio.SR
    tl = Timeline(intro=intro, outro=outro)
    chunks: list[np.ndarray] = []
    n = 0  # samples so far, so timings match the audio exactly

    def add(x: np.ndarray):
        nonlocal n
        chunks.append(x)
        n += len(x)

    def silence(sec: float):
        add(np.zeros(int(sr * sec), np.float32))

    silence(intro)
    idx = 0
    for shot in shots:
        s0 = n / sr
        silence(PAD_IN)
        for sent in sentences(shot.narration):
            clip = audio.tts_line(sent, voice_cfg, work, f"{tag}{idx:03d}", log)
            idx += 1
            t0 = n / sr
            add(clip)
            tl.segs.append(Seg(t0, n / sr, "narrator", sent))
            silence(GAP)
        silence(PAD_OUT)
        if n / sr - s0 < MIN_SHOT:
            silence(MIN_SHOT - (n / sr - s0))
        tl.shots.append((s0, n / sr))
    silence(outro)
    voice = np.concatenate(chunks)
    tl.duration = len(voice) / sr
    path = work / f"{tag}_voice.wav"
    audio.write_wav(path, voice * 0.95)
    log(f"  {tag}: {len(tl.segs)} sentences, {tl.duration:.1f}s")
    return tl, path


def write_srt(tl: Timeline, path: Path) -> None:
    def ts(x: float) -> str:
        ms = int(round(x * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    path.write_text("\n".join(f"{i}\n{ts(s.start)} --> {ts(s.end)}\n{s.text}\n" for i, s in enumerate(tl.segs, 1)))


# ----------------------------------------------------------------------------- film

class Film:
    def __init__(self, shots: list[Shot], images: list[Path], tl: Timeline, size: tuple[int, int], fps: int,
                 title: str, channel: str, end_line: str, title_image: Path | None, captions: bool, seed: int):
        self.tl, self.fps = tl, fps
        self.W, self.H = size
        self.portrait = self.H > self.W
        self.captions = captions
        self.src = [self._prep(p, 1.16) for p in images]  # headroom for camera moves
        self.fx = [Particles(s.effect, self.W, self.H, seed + i) for i, s in enumerate(shots)]
        rnd = random.Random(seed)
        self.moves = [s.camera if s.camera != "still" else rnd.choice(["zoom_in", "zoom_out"]) for s in shots]
        maxw = int(self.W * 0.86)
        big = int(self.H * 0.1) if not self.portrait else int(self.W * 0.085)
        self.title_img = text_block(title, big, maxw)
        self.channel_img = text_block(channel.upper(), int(big * 0.5), maxw, fill="#ffd34d", family="serif")
        self.end_img = text_block("Thanks for watching!", int(big * 1.1), maxw, fill="#ffd34d")
        self.lesson_img = text_block(end_line, int(big * 0.55), maxw)
        self.cards = {i: text_block(s.card, int(min(self.W, self.H) * 0.075), int(self.W * 0.88), fill="#ffd34d")
                      for i, s in enumerate(shots) if s.card}
        band_h = int(self.H * 0.4)
        grad = Image.linear_gradient("L").resize((self.W, band_h)).point(lambda v: int(v * 0.75))
        self.band = Image.new("RGBA", (self.W, band_h), (8, 6, 4, 255))
        self.band.putalpha(grad)
        self.title_bg = self._prep(title_image, 1.12) if title_image else self.src[0]
        last = self.src[-1].resize((self.W, self.H), Image.BILINEAR)
        self.end_bg = Image.blend(last.filter(ImageFilter.GaussianBlur(14)), Image.new("RGB", last.size, "#120c06"), 0.45)
        self.cap_cache: dict[int, Image.Image] = {}

    def _prep(self, path: Path, over: float) -> Image.Image:
        return cover(Image.open(path).convert("RGB"), (int(self.W * over), int(self.H * over)))

    def _camera(self, img: Image.Image, move: str, p: float) -> Image.Image:
        sw, sh = img.size
        e = ease(p)
        zmax = sw / self.W
        if move == "zoom_in":
            z, fx, fy = 1 + (zmax - 1) * e, .5, .45
        elif move == "zoom_out":
            z, fx, fy = zmax - (zmax - 1) * e, .5, .45
        else:
            z = zmax
            fx, fy = {"pan_left": (1 - e, .5), "pan_right": (e, .5),
                      "pan_up": (.5, 1 - e), "pan_down": (.5, e)}.get(move, (.5, .5))
        bw, bh = sw / z, sh / z
        x0, y0 = (sw - bw) * fx, (sh - bh) * fy
        return img.resize((self.W, self.H), Image.BILINEAR, box=(x0, y0, x0 + bw, y0 + bh))

    def _shot_frame(self, i: int, t: float) -> Image.Image:
        a, b = self.tl.shots[i]
        p = (t - a + XFADE / 2) / (b - a + XFADE)  # keep moving through the crossfades
        f = self._camera(self.src[i], self.moves[i], p)
        self.fx[i].draw(f, t)
        return f

    def _caption(self, idx: int) -> Image.Image:
        if idx not in self.cap_cache:
            size = int(min(self.W, self.H) * (0.06 if self.portrait else 0.05))
            self.cap_cache[idx] = text_block(self.tl.segs[idx].text, size, int(self.W * 0.84), stroke="#1d1d1d")
        return self.cap_cache[idx]

    def frame(self, fi: int) -> Image.Image:
        t = fi / self.fps
        tl = self.tl
        if t < tl.intro:
            return self._fade(self._title_frame(t), t)
        if t >= tl.duration - tl.outro:
            s = tl.duration - tl.outro
            f = self.end_bg.copy()
            y = self.H * 0.38
            paste_scaled(f, self.end_img, self.W / 2, y, pop((t - s - 0.2) / 0.6))
            paste_scaled(f, self.lesson_img, self.W / 2, y + (self.end_img.height + self.lesson_img.height) / 2, pop((t - s - 0.9) / 0.6))
            xa = (t - s) / 0.5
            if xa < 1:  # dissolve from the last shot into the end card
                f = Image.blend(self._shot_frame(len(self.src) - 1, t), f, xa)
            return self._fade(f, t)

        i = next((k for k, (a, b) in enumerate(tl.shots) if a <= t < b), len(tl.shots) - 1)
        a, b = tl.shots[i]
        f = self._shot_frame(i, t)
        if i > 0 and t - a < XFADE / 2:
            f = Image.blend(self._shot_frame(i - 1, t), f, 0.5 + (t - a) / XFADE)
        elif i < len(tl.shots) - 1 and b - t < XFADE / 2:
            f = Image.blend(f, self._shot_frame(i + 1, t), 0.5 - (b - t) / XFADE)
        if tl.intro and i == 0 and t - a < XFADE:  # dissolve from the title card into the first shot
            f = Image.blend(self._title_frame(t), f, (t - a) / XFADE)
        if i in self.cards and t - a < CARD_SECONDS:  # list item / chapter title
            k = min(1.0, (t - a) / 0.35, (CARD_SECONDS - (t - a)) / 0.4)
            band = self.band.copy()
            band.putalpha(band.getchannel("A").point(lambda v: int(v * k)))
            f.paste(band, (0, self.H - band.height), band)
            card = self.cards[i]
            paste_scaled(f, card, self.W / 2, self.H * 0.83, pop((t - a) / 0.5) * (1 if k >= 1 or t - a < 1 else k))
        if self.portrait and tl.intro == 0 and t < 3.0:  # Shorts: title over the opening shot
            paste_scaled(f, self.title_img, self.W / 2, self.H * 0.17, pop(t / 0.6) * min(1.0, (3 - t) / 0.4))
        if self.captions:
            cur = next((k for k, s in enumerate(tl.segs) if s.start <= t < s.end), None)
            if cur is not None:
                cap = self._caption(cur)
                f.paste(cap, ((self.W - cap.width) // 2, int(self.H * (0.8 if self.portrait else 0.97)) - cap.height), cap)
        return self._fade(f, t)

    def _title_frame(self, t: float) -> Image.Image:
        p = t / (self.tl.intro + XFADE)
        f = Image.blend(self._camera(self.title_bg, "zoom_in", p), Image.new("RGB", (self.W, self.H)), 0.15)
        y1 = self.H * 0.15
        paste_scaled(f, self.channel_img, self.W / 2, y1, pop((t - 0.2) / 0.6))
        paste_scaled(f, self.title_img, self.W / 2, y1 + (self.channel_img.height + self.title_img.height) / 2,
                     pop((t - 0.6) / 0.7))
        return f

    def _fade(self, f: Image.Image, t: float) -> Image.Image:
        k = min(1.0, t / 0.5, (self.tl.duration - t) / 0.8)
        return f if k >= 1 else Image.blend(Image.new("RGB", f.size), f, max(0.0, k))

    def encode(self, audio_path: Path, out: Path, log=print) -> None:
        proc = subprocess.Popen([
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{self.W}x{self.H}", "-r", str(self.fps), "-i", "-",
            "-i", str(audio_path),
            "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
        total = int(self.tl.duration * self.fps)
        for fi in range(total):
            proc.stdin.write(self.frame(fi).tobytes())
            if fi % (self.fps * 30) == 0:
                log(f"    frame {fi}/{total}")
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError("ffmpeg failed")


def make_video(shots, images, cfg, work: Path, out: Path, *, portrait: bool, title: str, end_line: str,
               title_image: Path | None, seed: int, tag: str, log=print) -> Timeline:
    size = (1080, 1920) if portrait else (1920, 1080)
    intro, outro = (0.0, 2.0) if portrait else (3.0, 5.0)
    tl, voice = record(shots, cfg, work, intro, outro, tag, log)
    mixed = work / f"{tag}_mix.wav"
    audio.mix(voice, mixed, tl.duration, seed, ROOT / "assets" / "music")
    film = Film(shots, images, tl, size, cfg["fps"], title, cfg["channel_name"], end_line, title_image,
                portrait or cfg.get("burn_captions", False), seed)
    log(f"  rendering {tag} ({tl.duration:.0f}s)")
    film.encode(mixed, out, log)
    return tl


def thumbnail(image: Path, text: str, out: Path) -> None:
    """Facts-channel thumbnail: striking image, darkened left side, 2-4 huge words."""
    img = cover(Image.open(image).convert("RGB"), (1280, 720))
    shade = Image.linear_gradient("L").rotate(-90, expand=True).resize((1280, 720)).point(lambda v: int(v * 0.8))
    img.paste(Image.new("RGB", img.size, (10, 8, 6)), (0, 0), shade)
    words = text.upper().split()
    lines = [" ".join(words[i:i + 2]) for i in range(0, len(words), 2)][:3]
    blocks = [text_block(line, 130, 760, fill="#ffd34d" if n % 2 == 0 else "#ffffff", stroke="#0b0805")
              for n, line in enumerate(lines)]
    step = 150  # line spacing in pixels (blocks carry padding for the outline and shadow)
    y = 360 - (step * (len(blocks) - 1) + blocks[0].height) / 2
    for tb in blocks:
        img.paste(tb, (20, int(y)), tb)
        y += step
    img.save(out, quality=92)
