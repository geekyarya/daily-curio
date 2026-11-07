"""End-to-end: write -> review -> voice -> animate -> upload -> record history.

    python -m kidtoon.pipeline              # full run (needs API keys)
    python -m kidtoon.pipeline --no-upload  # make the video but don't publish
    python -m kidtoon.pipeline --demo       # built-in story, no API keys at all
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="use the built-in episode (no Claude call, no upload)")
    ap.add_argument("--no-upload", action="store_true", help="render only")
    ap.add_argument("--out", default=str(ROOT / "out"))
    ap.add_argument("--minutes", type=float, help="override target length")
    args = ap.parse_args()

    from .render import render_video
    from .story import demo_episode, write_episode

    cfg = json.loads((ROOT / "config.json").read_text())
    if args.minutes:
        cfg["target_minutes"] = args.minutes
    hist_path = ROOT / "data" / "episodes.json"
    history = json.loads(hist_path.read_text()) if hist_path.exists() else []
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    log("1/4 Writing episode")
    ep, prop_svg = demo_episode() if args.demo else write_episode(cfg, history, log)
    (out / "episode.json").write_text(ep.model_dump_json(indent=2))
    (out / "prop.svg").write_text(prop_svg)

    log("2/4 Producing video")
    video, thumb = render_video(ep, prop_svg, cfg, out, log)
    log(f"  -> {video} ({video.stat().st_size / 1e6:.1f} MB)")

    description = (f"{ep.description}\n\n"
                   f"Today's lesson: {ep.lesson}\n\n"
                   f"Join Tumble, Pippa and Moss for gentle stories in {cfg['channel_name']}.\n"
                   "This animated story was created with the help of AI tools and reviewed for kid-friendly content.")
    tags = list(dict.fromkeys(ep.tags + cfg["youtube"]["default_tags"]))
    (out / "description.txt").write_text(description)

    video_id = None
    if args.demo or args.no_upload or os.environ.get("DRY_RUN", "").lower() == "true":
        log("3/4 Upload skipped")
    else:
        log("3/4 Uploading to YouTube")
        from .upload import upload
        video_id = upload(video, thumb, ep.title, description, tags, cfg, log)

    if not args.demo:
        log("4/4 Recording episode history")
        history.append({"date": dt.date.today().isoformat(), "title": ep.title, "lesson": ep.lesson,
                        "prop": ep.prop_name, "video_id": video_id})
        hist_path.write_text(json.dumps(history, indent=2) + "\n")
        if video_id and os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
                f.write(f"### {ep.title}\nhttps://youtu.be/{video_id}\n\n{ep.lesson}\n")
    log("Done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
