"""Daily run: write -> review -> illustrate -> voice -> animate -> upload episode + Short -> record history.

    python -m kidtoon.pipeline               # full run
    python -m kidtoon.pipeline --no-upload   # make the videos, don't publish
    python -m kidtoon.pipeline --demo        # built-in script (no Gemini call), no upload
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def log(msg: str) -> None:
    print(msg, flush=True)


def illustrate(gen, shots, size, img_dir: Path, tag: str, seed: int) -> list[Path]:
    paths = []
    for i, s in enumerate(shots):
        log(f"  {tag} shot {i + 1}/{len(shots)}")
        paths.append(gen.generate(s.visual, size, list(s.characters), seed + i * 101, img_dir / f"{tag}_{i:02d}.jpg"))
    return paths


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--skip-short", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "out"))
    args = ap.parse_args()

    from .images import ImageGen
    from .render import make_video, thumbnail, write_srt
    from .story import Episode, write_episode

    cfg = json.loads((ROOT / "config.json").read_text())
    hist_path = ROOT / "data" / "episodes.json"
    history = json.loads(hist_path.read_text()) if hist_path.exists() else []
    out = Path(args.out)
    work, img_dir = out / "work", out / "images"
    work.mkdir(parents=True, exist_ok=True)
    img_dir.mkdir(parents=True, exist_ok=True)

    # check the image keys first, so a missing secret fails in seconds, not after the story is written
    if args.demo and not os.environ.get("CLOUDFLARE_API_TOKEN"):
        os.environ["KIDTOON_ALLOW_ANON"] = "1"  # low-quality preview art; never used for real uploads
        cfg["image"]["providers"] = ["pollinations"]
    gen = ImageGen(cfg, ROOT / ("assets/cast" if not args.demo else "out/demo_cast"), log)

    log("1/5 Writing the episode")
    if args.demo:
        ep = Episode.model_validate_json((ROOT / "kidtoon" / "demo_episode.json").read_text())
    else:
        from .llm import Gemini
        ep = write_episode(cfg, history, Gemini(cfg["text_models"], log), log)
    (out / "episode.json").write_text(ep.model_dump_json(indent=2))
    seed = zlib.crc32(ep.title.encode())

    log("2/5 Illustrating")
    gen.ensure_cast()
    land, port = tuple(cfg["image"]["landscape"]), tuple(cfg["image"]["portrait"])
    thumb_src = gen.generate(ep.thumbnail_visual + ". Expressive, bright, eye-catching close-up, characters looking at the viewer",
                             land, list(ep.thumbnail_characters), seed, img_dir / "thumb.jpg")
    ep_imgs = illustrate(gen, ep.shots, land, img_dir, "ep", seed)
    short_imgs = [] if args.skip_short else illustrate(gen, ep.short.shots, port, img_dir, "short", seed + 7)
    log(f"  {gen.count} new images")

    log("3/5 Producing videos")
    episode_mp4, short_mp4 = out / "episode.mp4", out / "short.mp4"
    tl = make_video(ep.shots, ep_imgs, cfg, work, episode_mp4, portrait=False, title=ep.title, lesson=ep.lesson,
                    title_image=thumb_src, seed=seed, tag="episode", log=log)
    write_srt(tl, out / "episode.srt")
    thumbnail(thumb_src, ep.title, out / "thumbnail.jpg")
    if not args.skip_short:
        make_video(ep.short.shots, short_imgs, cfg, work, short_mp4, portrait=True, title=ep.short.title,
                   lesson=ep.lesson, title_image=None, seed=seed + 1, tag="short", log=log)

    tags = list(dict.fromkeys(ep.tags + cfg["youtube"]["default_tags"]))
    footer = f"\n\nJoin Tumble, Pippa and Moss for gentle stories in {cfg['channel_name']}."
    if cfg.get("ai_disclosure"):
        footer += "\nStory, pictures and voices were created with the help of AI tools and reviewed for kid-friendly content."
    ep_desc = f"{ep.description}\n\nToday's lesson: {ep.lesson}{footer}"
    short_desc = f"{ep.short.description}\n\nWatch the full story \"{ep.title}\" on our channel.{footer}\n#shorts"
    (out / "description.txt").write_text(ep_desc)

    ids = {"episode": None, "short": None}
    if args.demo or args.no_upload or os.environ.get("DRY_RUN", "").lower() == "true":
        log("4/5 Upload skipped")
    else:
        log("4/5 Uploading")
        from . import upload
        yt = upload.client()
        ids["episode"] = upload.upload(yt, episode_mp4, ep.title, ep_desc, tags, cfg,
                                       thumb=out / "thumbnail.jpg", srt=out / "episode.srt", log=log)
        if not args.skip_short:
            title = ep.short.title if "#shorts" in ep.short.title.lower() else f"{ep.short.title} #shorts"
            ids["short"] = upload.upload(yt, short_mp4, title, short_desc, tags, cfg,
                                         delay_hours=cfg.get("short_delay_hours", 0), log=log)

    if not args.demo:
        log("5/5 Saving history")
        history.append({"date": dt.date.today().isoformat(), "title": ep.title, "lesson": ep.lesson,
                        "episode_id": ids["episode"], "short_id": ids["short"]})
        hist_path.write_text(json.dumps(history, indent=2) + "\n")
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
                f.write(f"### {ep.title}\n\n{ep.lesson}\n\n")
                for k, v in ids.items():
                    if v:
                        f.write(f"- {k}: https://youtu.be/{v}\n")
    log("Done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
