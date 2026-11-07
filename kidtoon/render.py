"""Build the audio timeline, animate every frame and encode the final video."""
from __future__ import annotations

import math
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

from . import audio
from .art import CAST, background_svg, character_sprites, svg_to_image
from .story import Episode

INTRO, OUTRO = 4.0, 5.0
SCENE_PAD_IN, SCENE_PAD_OUT, LINE_GAP = 0.8, 0.7, 0.35
FADE = 0.35
SPEAKER_COLORS = {"narrator": "#6d4c41", "Tumble": "#e07b1a", "Pippa": "#1f78d1", "Moss": "#3f8f3a"}

FONT_PATHS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]


def font(size: int) -> ImageFont.FreeTypeFont:
    for p in FONT_PATHS:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt, max_w: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=fnt) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    return lines + [cur] if cur else lines


def outlined_text(img: Image.Image, text: str, size: int, y: int, fill="#ffffff", stroke="#3b2a6b", max_w=None) -> int:
    d = ImageDraw.Draw(img)
    fnt = font(size)
    max_w = max_w or int(img.width * 0.9)
    for line in wrap(d, text, fnt, max_w):
        w = d.textlength(line, font=fnt)
        d.text(((img.width - w) / 2, y), line, font=fnt, fill=fill, stroke_width=max(4, size // 10), stroke_fill=stroke)
        y += int(size * 1.18)
    return y


@dataclass
class Seg:
    start: float
    end: float
    scene: int
    speaker: str
    text: str
    emotion: str
    env: np.ndarray


@dataclass
class Timeline:
    scenes: list[tuple[float, float]] = field(default_factory=list)
    segs: list[Seg] = field(default_factory=list)
    duration: float = 0.0


def build_audio(ep: Episode, cfg: dict, work: Path, log=print) -> tuple[Timeline, Path]:
    fps, voices = cfg["fps"], cfg["voices"]
    tl, chunks, t, idx = Timeline(), [], INTRO, 0
    chunks.append(np.zeros(int(audio.SR * INTRO), np.float32))
    for si, scene in enumerate(ep.scenes):
        s0 = t
        chunks.append(np.zeros(int(audio.SR * SCENE_PAD_IN), np.float32))
        t += SCENE_PAD_IN
        for line in scene.lines:
            log(f"  voice {idx+1}: {line.speaker}: {line.text[:60]}")
            clip = audio.tts_line(line.text, voices.get(line.speaker, voices["narrator"]), work, idx, log)
            dur = len(clip) / audio.SR
            tl.segs.append(Seg(t, t + dur, si, line.speaker, line.text, line.emotion, audio.envelope(clip, fps)))
            chunks += [clip, np.zeros(int(audio.SR * LINE_GAP), np.float32)]
            t += dur + LINE_GAP
            idx += 1
        chunks.append(np.zeros(int(audio.SR * SCENE_PAD_OUT), np.float32))
        t += SCENE_PAD_OUT
        tl.scenes.append((s0, t))
    chunks.append(np.zeros(int(audio.SR * OUTRO), np.float32))
    voice = np.concatenate(chunks)
    tl.duration = len(voice) / audio.SR
    vpath = work / "voice.wav"
    audio.write_wav(vpath, voice * 0.95)
    music = audio.make_music(tl.duration, seed=abs(hash(ep.title)) % 2**32)
    mixed = work / "mix.wav"
    audio.mix(vpath, music, mixed)
    return tl, mixed


class Animator:
    def __init__(self, ep: Episode, prop_svg: str, cfg: dict, tl: Timeline):
        self.ep, self.cfg, self.tl = ep, cfg, tl
        self.W, self.H, self.fps = cfg["width"], cfg["height"], cfg["fps"]
        self.ground = int(self.H * 0.82)
        size = int(self.H * 0.42)
        self.sprites = {n: character_sprites(n, size) for n in CAST}
        self.flipped = {n: {k: ImageOps.mirror(v) for k, v in s.items()} for n, s in self.sprites.items()}
        self.prop = svg_to_image(prop_svg, int(self.H * 0.24))
        self.bgs = [svg_to_image(background_svg(s.setting, s.time_of_day, self.W, self.H, seed=i * 7919 + len(ep.title)),
                                 self.W, self.H).convert("RGB") for i, s in enumerate(ep.scenes)]
        self.title_bg = svg_to_image(background_svg("meadow", "day", self.W, self.H, seed=42), self.W, self.H).convert("RGB")
        self.end_bg = svg_to_image(background_svg("meadow", "sunset", self.W, self.H, seed=43), self.W, self.H).convert("RGB")
        self.caption_cache: dict[int, Image.Image] = {}
        self.show_captions = cfg.get("captions", True)

    # ---- helpers
    def _place(self, frame: Image.Image, img: Image.Image, cx: float, bottom: float):
        frame.paste(img, (int(cx - img.width / 2), int(bottom - img.height)), img)

    def _caption(self, i: int) -> Image.Image:
        if i not in self.caption_cache:
            seg = self.tl.segs[i]
            fnt = font(int(self.H * 0.045))
            tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
            lines = wrap(tmp, seg.text, fnt, int(self.W * 0.78))
            lh = int(fnt.size * 1.25)
            h = lh * len(lines) + 40
            img = Image.new("RGBA", (int(self.W * 0.84), h), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.rounded_rectangle((0, 0, img.width - 1, h - 1), radius=30, fill=(255, 255, 255, 225),
                                outline=SPEAKER_COLORS.get(seg.speaker, "#555"), width=6)
            y = 20
            for ln in lines:
                w = d.textlength(ln, font=fnt)
                d.text(((img.width - w) / 2, y), ln, font=fnt, fill="#2d2d2d")
                y += lh
            self.caption_cache[i] = img
        return self.caption_cache[i]

    def _cast(self, frame, names, t, speaking=None, mouth=False, emotions=None, wave=False, prop=False):
        n = len(names) + (1 if prop else 0)
        slots = [self.W * (k + 1) / (n + 1) for k in range(n)]
        if prop:
            mid = n // 2
            px = slots.pop(mid)
            bob = math.sin(t * 2.2) * 12
            self._place(frame, self.prop, px, self.ground - 30 + bob)
        for k, name in enumerate(names):
            x = slots[k]
            phase = k * 1.7
            emo = (emotions or {}).get(name, "happy")
            blink = ((t + phase * 1.3) % 3.7) < 0.13
            talking = speaking == name
            if talking:
                dy = -abs(math.sin(t * 7)) * 12
            elif wave:
                dy = -abs(math.sin(t * 5 + phase)) * 30
            else:
                dy = math.sin(t * 2 + phase) * 5
            if name == "Pippa":
                dy += -60 + math.sin(t * 3 + phase) * 10
            # Moss is drawn facing right; mirror him on the right half so he faces his friends
            bank = self.flipped if (name == "Moss" and x > self.W / 2) else self.sprites
            img = bank[name][(emo, talking and mouth, blink)]
            self._place(frame, img, x, self.ground + dy)

    # ---- frame
    def frame(self, fi: int) -> Image.Image:
        t = fi / self.fps
        tl = self.tl
        if t < INTRO:
            f = self.title_bg.copy()
            self._cast(f, CAST, t, wave=True)
            outlined_text(f, self.cfg["channel_name"], int(self.H * 0.06), int(self.H * 0.08), fill="#ffe066")
            outlined_text(f, self.ep.title, int(self.H * 0.085), int(self.H * 0.18))
            return self._fade(f, t, 0, INTRO)
        if t >= tl.duration - OUTRO:
            s = tl.duration - OUTRO
            f = self.end_bg.copy()
            self._cast(f, CAST, t, wave=True)
            y = outlined_text(f, "The End!", int(self.H * 0.11), int(self.H * 0.07), fill="#ffe066")
            outlined_text(f, self.ep.lesson, int(self.H * 0.05), y + 10, max_w=int(self.W * 0.8))
            return self._fade(f, t, s, tl.duration)
        si = next((i for i, (a, b) in enumerate(tl.scenes) if a <= t < b), len(tl.scenes) - 1)
        scene = self.ep.scenes[si]
        f = self.bgs[si].copy()
        cur = next((i for i, s in enumerate(tl.segs) if s.start <= t < s.end), None)
        emotions, speaking, mouth = {}, None, False
        for s in tl.segs:
            if s.scene == si and s.start <= t:
                emotions[s.speaker] = s.emotion
        if cur is not None:
            seg = tl.segs[cur]
            speaking = seg.speaker
            k = int((t - seg.start) * self.fps)
            mouth = k < len(seg.env) and seg.env[k] > 0.22
        self._cast(f, list(scene.characters), t, speaking, mouth, emotions, prop=scene.show_prop)
        if cur is not None and self.show_captions:
            cap = self._caption(cur)
            f.paste(cap, ((self.W - cap.width) // 2, self.H - cap.height - 30), cap)
        a, b = tl.scenes[si]
        return self._fade(f, t, a, b)

    def _fade(self, f: Image.Image, t: float, a: float, b: float) -> Image.Image:
        k = min(1.0, (t - a) / FADE, (b - t) / FADE)
        if k >= 1:
            return f
        return Image.blend(Image.new("RGB", f.size, "black"), f, max(0.0, k))

    def thumbnail(self, path: Path) -> None:
        f = self.bgs[0].copy()
        self._cast(f, CAST, 0.3, emotions={"Tumble": "surprised"}, prop=True)
        outlined_text(f, self.ep.title, int(self.H * 0.11), int(self.H * 0.06), fill="#fff59d", stroke="#2c1a5e")
        f.convert("RGB").resize((1280, 720), Image.LANCZOS).save(path, quality=90)


def render_video(ep: Episode, prop_svg: str, cfg: dict, out_dir: Path, log=print) -> tuple[Path, Path]:
    work = out_dir / "work"
    work.mkdir(parents=True, exist_ok=True)
    log("Recording voices and music")
    tl, mixed = build_audio(ep, cfg, work, log)
    log(f"Animating {tl.duration:.1f}s of video")
    anim = Animator(ep, prop_svg, cfg, tl)
    thumb = out_dir / "thumbnail.jpg"
    anim.thumbnail(thumb)
    video = out_dir / "episode.mp4"
    fps, W, H = cfg["fps"], cfg["width"], cfg["height"]
    proc = subprocess.Popen([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
        "-i", str(mixed),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-tune", "animation",
        "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(video)],
        stdin=subprocess.PIPE)
    total = int(tl.duration * fps)
    for fi in range(total):
        proc.stdin.write(anim.frame(fi).convert("RGB").tobytes())
        if fi % (fps * 15) == 0:
            log(f"  frame {fi}/{total}")
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg encoding failed")
    return video, thumb
