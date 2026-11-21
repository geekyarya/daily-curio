"""Narration (natural, one take per scene), background music playlists, and a broadcast-style mix."""
from __future__ import annotations

import asyncio
import math
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 24000


def _to_wav(src: Path, dst: Path) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-ac", "1", "-ar", str(SR), str(dst)], check=True)


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return data.astype(np.float32) / 32768.0


def write_wav(path: Path, samples: np.ndarray, sr: int = SR) -> None:
    pcm = (np.clip(samples, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


async def _edge(text: str, voice: dict, out: Path) -> None:
    import edge_tts
    await edge_tts.Communicate(text, voice["voice"], rate=voice.get("rate", "+0%"), pitch=voice.get("pitch", "+0Hz")).save(str(out))


async def _edge_stream(text: str, voice: dict, out: Path) -> list[tuple[float, float, str]]:
    import edge_tts
    sents = []
    with open(out, "wb") as fh:
        async for ch in edge_tts.Communicate(text, voice["voice"], rate=voice.get("rate", "+0%"),
                                             pitch=voice.get("pitch", "+0Hz"), boundary="SentenceBoundary").stream():
            if ch["type"] == "audio":
                fh.write(ch["data"])
            elif ch["type"] == "SentenceBoundary":
                start = ch["offset"] / 1e7
                sents.append((start, start + ch["duration"] / 1e7, ch["text"]))
    return sents


def tts_passage(text: str, voice: dict, workdir: Path, key, log=print) -> tuple[np.ndarray, list[tuple[float, float, str]]]:
    """Read a whole passage in one take (natural intonation across sentences).

    Returns the audio and (start, end, sentence) timings for captions. Falls back to sentence-by-sentence.
    """
    mp3, wav = workdir / f"pass_{key}.mp3", workdir / f"pass_{key}.wav"
    for attempt in range(3):
        try:
            sents = asyncio.run(_edge_stream(text, voice, mp3))
            _to_wav(mp3, wav)
            audio = read_wav(wav)
            if sents:
                return audio, sents
            return audio, [(0.0, len(audio) / SR, text)]
        except Exception as e:  # noqa: BLE001
            log(f"    edge-tts failed (attempt {attempt+1}): {e}")
    # fallback: one clip per sentence, timings from clip lengths
    import re
    parts = [p for p in re.split(r"(?<=[.!?\u0964])\s+", text.strip()) if p.strip()] or [text]
    clips, sents, t = [], [], 0.0
    for i, p in enumerate(parts):
        clip = tts_line(p, voice, workdir, f"{key}_{i}", log)
        sents.append((t, t + len(clip) / SR, p))
        clips += [clip, np.zeros(int(SR * 0.15), np.float32)]
        t += len(clip) / SR + 0.15
    return np.concatenate(clips), sents


def tts_line(text: str, voice: dict, workdir: Path, idx, log=print) -> np.ndarray:
    """Synthesise one line. edge-tts first, espeak-ng as a fallback, silence as a last resort."""
    mp3, wav = workdir / f"line_{idx}.mp3", workdir / f"line_{idx}.wav"
    for attempt in range(3):
        try:
            asyncio.run(_edge(text, voice, mp3))
            _to_wav(mp3, wav)
            return read_wav(wav)
        except Exception as e:  # noqa: BLE001
            log(f"    edge-tts failed (attempt {attempt+1}): {e}")
    if shutil.which("espeak-ng"):
        subprocess.run(["espeak-ng", "-s", "140", "-w", str(wav), text], check=True)
        tmp = workdir / f"line_{idx}_r.wav"
        _to_wav(wav, tmp)
        return read_wav(tmp)
    log("    WARNING: no TTS available, inserting silence")
    return np.zeros(int(SR * max(1.5, len(text.split()) * 0.4)), dtype=np.float32)


# --------------------------------------------------------------------------- music

PENTA = [0, 2, 4, 7, 9]


def _note(freq: float, dur: float, vol: float, sr: int) -> np.ndarray:
    t = np.arange(int(sr * dur)) / sr
    tone = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(4 * np.pi * freq * t) + 0.1 * np.sin(6 * np.pi * freq * t)
    env = np.minimum(1, t / 0.015) * np.exp(-3.2 * t / dur)
    return (tone * env * vol).astype(np.float32)


def make_music(seconds: float, seed: int, sr: int = 44100) -> np.ndarray:
    """A soft, looping music-box tune in a major pentatonic scale."""
    rnd = np.random.default_rng(seed)
    root = 261.63 * 2 ** (rnd.integers(0, 7) / 12)
    bpm = 92
    beat = 60 / bpm
    total = int(sr * (seconds + 2))
    out = np.zeros(total, dtype=np.float32)

    # 8-bar phrase, repeated with variation
    phrase = [int(rnd.integers(0, 10)) for _ in range(16)]
    chords = [0, 5, 3, 4]  # I  vi  IV  V in scale degrees (approx.)
    t, bar = 0.0, 0
    while t < seconds + 1:
        chord = chords[bar % 4]
        bass_f = root / 2 * 2 ** ([0, 9, 5, 7][chord % 4] / 12)
        seg = _note(bass_f, beat * 4, 0.10, sr)
        i = int(t * sr)
        out[i:i + len(seg)] += seg[: max(0, total - i)]
        for k in range(8):
            if rnd.random() < 0.18:
                continue
            step = phrase[(bar * 8 + k) % 16] + (1 if bar % 8 >= 4 and k % 3 == 0 else 0)
            octave, deg = divmod(step, 5)
            f = root * 2 ** ((PENTA[deg] + 12 * octave) / 12)
            seg = _note(f, beat * 0.9, 0.11, sr)
            j = int((t + k * beat / 2) * sr)
            out[j:j + len(seg)] += seg[: max(0, total - j)]
        t += beat * 4
        bar += 1
    fade = int(sr * 2)
    out[-fade:] *= np.linspace(1, 0, fade)
    return out[: int(sr * seconds)] / max(1e-6, np.abs(out).max()) * 0.8


def load_credits(music_dir: Path) -> dict:
    import json
    f = music_dir / "credits.json"
    return json.loads(f.read_text()) if f.exists() else {}


def playlist(music_dir: Path, seconds: float, seed: int) -> list[Path]:
    """Enough different tracks (rotating by seed) to cover the video without audible looping."""
    tracks = sorted(p for p in music_dir.glob("*") if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".ogg"))
    if not tracks:
        return []
    out, total, k = [], 0.0, seed % len(tracks)
    while total < seconds + 5 and len(out) < 12:
        t = tracks[k % len(tracks)]
        out.append(t)
        total += float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                       str(t)], capture_output=True, text=True).stdout.strip() or 60) - 4
        k += 1
    return out


# Voice: rumble cut, a touch of warmth and presence, de-essing, gentle compression (radio/YouTube voiceover style)
VOICE_FX = ("highpass=f=75,equalizer=f=180:t=q:w=1.1:g=2.5,equalizer=f=3200:t=q:w=1.4:g=2,"
            "deesser=i=0.35,acompressor=threshold=-20dB:ratio=3:attack=8:release=180:makeup=2")


def mix(voice_wav: Path, out_wav: Path, seconds: float, seed: int, music_dir: Path, music_db: float = -6.0) -> list[str]:
    """Polish the narration, lay a ducked music bed under it, master to YouTube loudness. Returns tracks used."""
    tracks = playlist(music_dir, seconds, seed)
    used = [t.name for t in tracks]
    if not tracks:
        gen = out_wav.with_name("music.wav")
        write_wav(gen, make_music(seconds, seed), 44100)
        tracks = [gen]
    inputs, chain = [], ""
    for i, t in enumerate(tracks):
        inputs += ["-i", str(t)]
        chain += f"[{i + 1}:a]aresample=44100,aformat=channel_layouts=stereo[t{i}];"
    prev = "t0"
    for i in range(1, len(tracks)):  # crossfade track into track
        chain += f"[{prev}][t{i}]acrossfade=d=4:c1=tri:c2=tri[x{i}];"
        prev = f"x{i}"
    fade_start = max(0.0, seconds - 4)
    raw = out_wav.with_name(out_wav.stem + "_raw.wav")
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(voice_wav), *inputs, "-filter_complex",
        chain +
        f"[0:a]aresample=44100,{VOICE_FX},asplit=2[v][vs];"
        f"[{prev}]atrim=0:{seconds:.2f},volume={music_db}dB,afade=t=in:d=1.5,afade=t=out:st={fade_start:.2f}:d=4[m];"
        # duck the music ~9 dB while someone speaks, release smoothly in pauses
        "[m][vs]sidechaincompress=threshold=0.015:ratio=8:attack=40:release=650:makeup=1[md];"
        "[v][md]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.9[out]",
        "-map", "[out]", "-ac", "2", "-ar", "48000", str(raw)], check=True)
    master(raw, out_wav)
    return used


def master(src: Path, dst: Path, target: float = -14.0) -> None:
    """Two-pass loudness normalisation (linear gain, so speech/music balance and pauses stay natural)."""
    import json
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(src), "-af",
                        f"loudnorm=I={target}:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af",
                    f"loudnorm=I={target}:TP=-1.5:LRA=11:linear=true:measured_I={m['input_i']}:"
                    f"measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:"
                    f"offset={m['target_offset']}", "-ar", "48000", str(dst)], check=True)
