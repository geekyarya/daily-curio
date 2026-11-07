"""Upload a finished episode to YouTube as Made-for-Kids content."""
from __future__ import annotations

import os
import time
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]


def youtube_client():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload(video: Path, thumb: Path, title: str, description: str, tags: list[str], cfg: dict, log=print) -> str:
    yt = youtube_client()
    privacy = os.environ.get("PRIVACY_STATUS", "private")
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:4900],
            "tags": tags[:30],
            "categoryId": cfg["youtube"]["category_id"],
            "defaultLanguage": cfg["language"],
            "defaultAudioLanguage": cfg["language"],
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": True,   # COPPA: required for children's content
            "containsSyntheticMedia": True,    # AI-generated content disclosure
            "embeddable": True,
            "license": "youtube",
        },
    }
    media = MediaFileUpload(str(video), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media, notifySubscribers=True)
    resp, retries = None, 0
    while resp is None:
        try:
            status, resp = req.next_chunk()
            if status:
                log(f"  uploaded {int(status.progress() * 100)}%")
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504) and retries < 5:
                retries += 1
                time.sleep(2 ** retries)
                continue
            raise
    vid = resp["id"]
    log(f"  video id: {vid} ({privacy})")

    try:
        yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(thumb), mimetype="image/jpeg")).execute()
    except HttpError as e:
        log(f"  thumbnail not set (channel may need phone verification): {e.reason}")

    playlist = os.environ.get("YOUTUBE_PLAYLIST_ID") or cfg["youtube"].get("playlist_id")
    if playlist:
        try:
            yt.playlistItems().insert(part="snippet", body={"snippet": {
                "playlistId": playlist, "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
        except HttpError as e:
            log(f"  could not add to playlist: {e.reason}")
    return vid
