"""Make already-uploaded private videos public (one-off). Skips entries before `--since` (YYYY-MM-DD).

    python -m curio.publish_backlog --since 2026-11-10
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .upload import client

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="0000-00-00")
    args = ap.parse_args()
    cfg = json.loads((ROOT / "config.json").read_text())
    history = json.loads((ROOT / "data" / "videos.json").read_text())
    ids = [i for h in history if h["date"] >= args.since for i in (h.get("video_id"), h.get("short_id")) if i]
    yt = client()
    done = 0
    for k in range(0, len(ids), 50):
        for item in yt.videos().list(part="status,snippet", id=",".join(ids[k:k + 50])).execute().get("items", []):
            st, title = item["status"], item["snippet"]["title"]
            if st.get("privacyStatus") == "public" or st.get("publishAt"):
                print(f"  already public/scheduled: {title}")
                continue
            yt.videos().update(part="status", body={"id": item["id"], "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": bool(cfg["youtube"].get("made_for_kids", False)),
                "containsSyntheticMedia": bool(cfg.get("ai_disclosure")),
                "embeddable": True, "license": "youtube"}}).execute()
            done += 1
            print(f"  now public: https://youtu.be/{item['id']}  {title}")
    print(f"Made {done} videos public ({len(ids)} checked).")


if __name__ == "__main__":
    main()
