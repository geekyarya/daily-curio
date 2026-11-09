"""Daily run: pick format + topic -> write -> fact-check -> illustrate -> narrate -> animate -> upload video + Short.

    python -m curio.pipeline                            # today's format and topic, full run
    python -m curio.pipeline --no-upload                # make the videos, don't publish
    python -m curio.pipeline --format top5 --topic "Strange laws of medieval England"
    python -m curio.pipeline --demo                     # built-in script, no Gemini call, no upload
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import re
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def log(msg: str) -> None:
    print(msg, flush=True)


def soften(visual: str) -> str:
    """A plainer rewording for when a safety filter wrongly flags an image prompt."""
    first = re.split(r"(?<=[.;])\s", visual.strip())[0]
    return f"A calm, wholesome, softly lit historical scene: {first.strip(' ,.')}"


def draw(gen, visual: str, size, seed: int, out: Path) -> Path | None:
    for attempt, prompt in enumerate([visual, soften(visual)]):
        try:
            return gen.generate(prompt, size, [], seed + attempt * 7, out)
        except RuntimeError as e:
            log(f"    image failed ({'reworded' if attempt else 'original'} prompt): {str(e)[:120]}")
    return None


def illustrate(gen, shots, size, img_dir: Path, tag: str, seed: int) -> list[Path]:
    """Draw every shot; if one image can't be made at all, reuse a neighbour instead of failing the run."""
    paths: list[Path | None] = []
    for i, s in enumerate(shots):
        log(f"  {tag} image {i + 1}/{len(shots)}")
        paths.append(draw(gen, s.visual, size, seed + i * 101, img_dir / f"{tag}_{i:02d}.jpg"))
    good = [p for p in paths if p]
    if len(good) < max(2, len(paths) * 0.7):
        raise RuntimeError(f"Too many {tag} images failed ({len(paths) - len(good)} of {len(paths)})")
    for i, p in enumerate(paths):
        if p is None:
            paths[i] = next((paths[j] for j in range(i - 1, -1, -1) if paths[j]), good[0])
            log(f"  {tag} shot {i + 1}: reusing a neighbouring image")
    return paths  # type: ignore[return-value]


def plan(cfg: dict, history: list[dict], fmt: str | None, topic: str | None) -> tuple[str, str]:
    """Rotate formats day by day; pick the least recently used topic category."""
    day = dt.datetime.now(dt.timezone.utc).date().toordinal()
    if not fmt or fmt == "auto":
        fmt = cfg["formats"][day % len(cfg["formats"])]
    used = [h.get("category") for h in history[-len(cfg["categories"]):]]
    fresh = [c for c in cfg["categories"] if c not in used] or cfg["categories"]
    category = random.Random(day).choice(fresh)
    return fmt, category


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--skip-short", action="store_true")
    ap.add_argument("--format", default=os.environ.get("VIDEO_FORMAT") or "auto")
    ap.add_argument("--topic", default=os.environ.get("VIDEO_TOPIC") or "")
    ap.add_argument("--out", default=str(ROOT / "out"))
    args = ap.parse_args()

    from .images import ImageGen
    from .render import make_video, thumbnail, write_srt
    from .script import Video, write_video

    cfg = json.loads((ROOT / "config.json").read_text())
    hist_path = ROOT / "data" / "videos.json"
    history = json.loads(hist_path.read_text()) if hist_path.exists() else []
    out = Path(args.out)
    work, img_dir = out / "work", out / "images"
    work.mkdir(parents=True, exist_ok=True)
    img_dir.mkdir(parents=True, exist_ok=True)

    # check the image keys first, so a missing secret fails in seconds, not after the script is written
    if args.demo and not os.environ.get("CLOUDFLARE_API_TOKEN"):
        os.environ["CURIO_ALLOW_ANON"] = "1"  # low-quality preview art; never used for real uploads
        cfg["image"]["providers"] = ["pollinations"]
    if os.environ.get("IMAGE_PROVIDERS"):  # e.g. "cloudflare_schnell,cloudflare_flux2" for a cheaper run
        cfg["image"]["providers"] = [p.strip() for p in os.environ["IMAGE_PROVIDERS"].split(",") if p.strip()]
    gen = ImageGen(cfg, None, log)
    if not args.demo and not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit("Missing secret: add GEMINI_API_KEY in the repo's Settings → Secrets and variables → Actions")

    fmt, category = plan(cfg, history, args.format, args.topic)
    log(f"1/5 Writing a {fmt} video ({args.topic or category})")
    if args.demo:
        v = Video.model_validate_json((ROOT / "curio" / "demo_video.json").read_text())
    else:
        from .llm import Gemini
        v = write_video(cfg, history, fmt, category, args.topic, Gemini(cfg["text_models"], log), log)
    (out / "video.json").write_text(v.model_dump_json(indent=2))
    seed = zlib.crc32(v.title.encode())

    log("2/5 Illustrating")
    land, port = tuple(cfg["image"]["landscape"]), tuple(cfg["image"]["portrait"])
    thumb_src = draw(gen, v.thumbnail_visual + ". Striking, high-contrast, single clear focal point on the right side",
                     land, seed, img_dir / "thumb.jpg")
    imgs = illustrate(gen, v.shots, land, img_dir, "video", seed)
    thumb_src = thumb_src or imgs[0]
    short_imgs = [] if args.skip_short else illustrate(gen, v.short.shots, port, img_dir, "short", seed + 7)
    log(f"  {gen.count} new images")

    log("3/5 Producing videos")
    video_mp4, short_mp4 = out / "video.mp4", out / "short.mp4"
    end_line = "A new video every day"
    tl = make_video(v.shots, imgs, cfg, work, video_mp4, portrait=False, title=v.title, end_line=end_line,
                    title_image=thumb_src, seed=seed, tag="video", log=log)
    write_srt(tl, out / "video.srt")
    thumbnail(thumb_src, v.thumbnail_text or v.title, out / "thumbnail.jpg")
    if not args.skip_short:
        make_video(v.short.shots, short_imgs, cfg, work, short_mp4, portrait=True, title=v.short.title,
                   end_line=end_line, title_image=None, seed=seed + 1, tag="short", log=log)

    tags = list(dict.fromkeys(v.tags + cfg["youtube"]["default_tags"]))
    footer = f"\n\n{cfg['channel_name']}: {cfg['tagline'].lower()}. Subscribe for a new video every day."
    if cfg.get("ai_disclosure"):
        footer += "\nScript, narration and illustrations were made with the help of AI tools and fact-checked."
    desc = v.description + footer
    short_desc = f"{v.short.description}\n\nFull video: \"{v.title}\" on our channel.{footer}\n#shorts"
    (out / "description.txt").write_text(desc)

    ids = {"video": None, "short": None}
    if args.demo or args.no_upload or os.environ.get("DRY_RUN", "").lower() == "true":
        log("4/5 Upload skipped")
    else:
        log("4/5 Uploading")
        from . import upload
        yt = upload.client()
        ids["video"] = upload.upload(yt, video_mp4, v.title, desc, tags, cfg,
                                     thumb=out / "thumbnail.jpg", srt=out / "video.srt", log=log)
        if not args.skip_short:
            title = v.short.title if "#shorts" in v.short.title.lower() else f"{v.short.title} #shorts"
            ids["short"] = upload.upload(yt, short_mp4, title, short_desc, tags, cfg,
                                         delay_hours=cfg.get("short_delay_hours", 0), log=log)

    # Instagram + Facebook Page Reels from the Short. Each post is independent; failures fail the run at the end.
    errors, ig_link = [], None
    publishing = not (args.demo or args.no_upload or args.skip_short or os.environ.get("DRY_RUN", "").lower() == "true")
    if publishing:
        from . import facebook, instagram
        caption = instagram.build_caption(v.short.title, v.short.description, v.title, cfg)
        if cfg.get("instagram", {}).get("enabled") and instagram.have_credentials():
            try:
                log("  posting Instagram Reel")
                ig_link = instagram.post_reel(str(short_mp4), caption, cfg)
            except Exception as e:  # noqa: BLE001
                errors.append(f"Instagram: {e}")
        elif cfg.get("instagram", {}).get("enabled"):
            log("  no IG_ACCESS_TOKEN secret: skipping Instagram")
        if cfg.get("facebook", {}).get("enabled") and facebook.have_credentials():
            try:
                log("  posting Facebook Page Reel")
                facebook.post_reel(str(short_mp4), caption, cfg)
            except Exception as e:  # noqa: BLE001
                errors.append(f"Facebook: {e}")

    if not args.demo:
        log("5/5 Saving history")
        history.append({"date": dt.datetime.now(dt.timezone.utc).date().isoformat(), "format": fmt, "category": category,
                        "title": v.title, "video_id": ids["video"], "short_id": ids["short"], "instagram": ig_link})
        hist_path.write_text(json.dumps(history, indent=2) + "\n")
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
                f.write(f"### {v.title}\n\n{fmt} · {category}\n\n")
                for k, val in ids.items():
                    if val:
                        f.write(f"- {k}: https://youtu.be/{val}\n")
    for e in errors:
        log(f"::error::{e}")
    log("Done")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
