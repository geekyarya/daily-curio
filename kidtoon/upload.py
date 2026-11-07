"""Upload episodes and Shorts to YouTube as Made-for-Kids content."""
from __future__ import annotations

import datetime as dt
import os
import time
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.force-ssl"]


def client():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload(yt, video: Path, title: str, description: str, tags: list[str], cfg: dict, *,
           thumb: Path | None = None, srt: Path | None = None, delay_hours: float = 0, log=print) -> str:
    privacy = os.environ.get("PRIVACY_STATUS", "private")
    status = {
        "privacyStatus": privacy,
        "selfDeclaredMadeForKids": True,   # COPPA: required for children's content
        "containsSyntheticMedia": True,    # AI-generated content disclosure
        "embeddable": True,
        "license": "youtube",
    }
    if privacy == "public" and delay_hours > 0:  # schedule: upload private, YouTube publishes it later
        at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=delay_hours)
        status |= {"privacyStatus": "private", "publishAt": at.strftime("%Y-%m-%dT%H:%M:%SZ")}
    body = {
        "snippet": {
            "title": title[:100], "description": description[:4900], "tags": tags[:30],
            "categoryId": cfg["youtube"]["category_id"],
            "defaultLanguage": cfg["language"], "defaultAudioLanguage": cfg["language"],
        },
        "status": status,
    }
    media = MediaFileUpload(str(video), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp, retries = None, 0
    while resp is None:
        try:
            st, resp = req.next_chunk()
            if st:
                log(f"    {int(st.progress() * 100)}%")
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504) and retries < 6:
                retries += 1
                time.sleep(2 ** retries)
                continue
            raise
    vid = resp["id"]
    log(f"    uploaded https://youtu.be/{vid} ({status['privacyStatus']}{', publishes ' + status['publishAt'] if 'publishAt' in status else ''})")

    if thumb:
        _try(log, "thumbnail (needs a phone-verified channel)", lambda: yt.thumbnails().set(
            videoId=vid, media_body=MediaFileUpload(str(thumb), mimetype="image/jpeg")).execute())
    if srt:
        _try(log, "captions", lambda: yt.captions().insert(
            part="snippet",
            body={"snippet": {"videoId": vid, "language": cfg["language"], "name": "English", "isDraft": False}},
            media_body=MediaFileUpload(str(srt), mimetype="application/octet-stream")).execute())
    playlist = os.environ.get("YOUTUBE_PLAYLIST_ID") or cfg["youtube"].get("playlist_id")
    if playlist:
        _try(log, "playlist", lambda: yt.playlistItems().insert(part="snippet", body={"snippet": {
            "playlistId": playlist, "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute())
    return vid


def _try(log, what, fn):
    try:
        fn()
    except HttpError as e:
        log(f"    {what} skipped: {e.reason}")
