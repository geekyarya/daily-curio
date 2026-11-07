"""Text-to-speech for each line, procedural background music, and mixing."""
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


def tts_line(text: str, voice: dict, workdir: Path, idx: int, log=print) -> np.ndarray:
    """Synthesise one line. edge-tts first, espeak-ng as a fallback, silence as a last resort."""
    mp3, wav = workdir / f"line{idx:03d}.mp3", workdir / f"line{idx:03d}.wav"
    for attempt in range(3):
        try:
            asyncio.run(_edge(text, voice, mp3))
            _to_wav(mp3, wav)
            return read_wav(wav)
        except Exception as e:  # noqa: BLE001
            log(f"    edge-tts failed (attempt {attempt+1}): {e}")
    if shutil.which("espeak-ng"):
        subprocess.run(["espeak-ng", "-s", "140", "-w", str(wav), text], check=True)
        tmp = workdir / f"line{idx:03d}_r.wav"
        _to_wav(wav, tmp)
        return read_wav(tmp)
    log("    WARNING: no TTS available, inserting silence")
    return np.zeros(int(SR * max(1.5, len(text.split()) * 0.4)), dtype=np.float32)


def envelope(samples: np.ndarray, fps: int) -> np.ndarray:
    """Per-video-frame loudness 0..1, used to drive mouth movement."""
    hop = SR // fps
    n = math.ceil(len(samples) / hop)
    padded = np.pad(samples, (0, n * hop - len(samples)))
    rms = np.sqrt((padded.reshape(n, hop) ** 2).mean(axis=1))
    peak = rms.max() or 1.0
    return rms / peak


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


def mix(voice_wav: Path, music: np.ndarray, out_wav: Path, music_db: float = -20.0) -> None:
    music_path = out_wav.with_name("music.wav")
    write_wav(music_path, music, 44100)
    # sidechain-style ducking: music dips while anyone is speaking
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(voice_wav), "-i", str(music_path),
        "-filter_complex",
        f"[0:a]aresample=44100,asplit=2[v][vs];[1:a]volume={music_db}dB[m];"
        "[m][vs]sidechaincompress=threshold=0.02:ratio=6:attack=20:release=400[md];"
        "[v][md]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95[out]",
        "-map", "[out]", "-ac", "2", "-ar", "44100", str(out_wav)], check=True)
