# Maple Meadow Friends: an automated kids' cartoon channel

A GitHub Actions workflow writes, animates, voices and uploads a new children's cartoon episode to YouTube on a schedule.

```
cron ─► Claude writes episode ─► Claude safety review ─► Claude draws the episode's prop (SVG)
     ─► TTS voices per character ─► generated music-box score (ducked under speech)
     ─► animated frames (lip-sync, blinking, bobbing, captions, fades) ─► MP4 + thumbnail
     ─► YouTube upload (Made for Kids, AI disclosure) ─► history committed back to the repo
```

**Cast** (original characters drawn in code, so they look the same in every episode):
Tumble the orange bear cub, Pippa the little blue bird, and Moss the wise old turtle.

## Setup (about 20 minutes, once)

1. **Push this folder to a new GitHub repo.**
2. **Anthropic key**: add the repo secret `ANTHROPIC_API_KEY`.
3. **YouTube API access**
   - In Google Cloud Console, create a project and enable **YouTube Data API v3**.
   - Set up the OAuth consent screen (External), add yourself as a test user, then **Publish app** so the refresh token doesn't expire after 7 days.
   - Create an OAuth client ID of type **Desktop app** and download it as `client_secret.json`.
   - On your computer, run:
     ```bash
     pip install google-auth-oauthlib
     python scripts/get_youtube_token.py client_secret.json
     ```
   - Sign in as the channel owner, then add the printed `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET` and `YOUTUBE_REFRESH_TOKEN` as repo secrets.
4. **Repo variables** (optional, under Settings → Secrets and variables → Actions → Variables):
   - `PRIVACY_STATUS`: `private` (default), `unlisted` or `public`.
   - `YOUTUBE_PLAYLIST_ID`: the playlist each new episode is added to.
5. **Test it**: go to Actions → *Daily episode* → *Run workflow* with **dry_run** ticked, then download the video from the run's artifacts.

## Important YouTube rules

- **Upload audit.** API projects created after July 2020 can only upload **private** videos until they pass Google's free [YouTube API audit](https://support.google.com/youtube/contact/yt_api_form). Apply early. Until it's approved, publish videos by hand in YouTube Studio.
- **Made for Kids.** Every upload sets `selfDeclaredMadeForKids: true`, as COPPA requires. That turns off comments, personalised ads and notifications on those videos.
- **AI disclosure.** `containsSyntheticMedia: true` is set, and the description says AI tools were used.
- **Repetitive content and monetization.** YouTube may refuse to monetise mass-produced, template-like videos. To reduce the risk, vary the stories, keep a human looking at episodes, and add new settings and characters over time.
- **Thumbnails** need a phone-verified channel. Without one, the upload still works and the thumbnail step is skipped.
- **Quota.** One upload uses about 1,600 of the default 10,000 daily API units, so the limit is about 6 uploads a day.

## Human review (recommended for a kids' channel)

- Keep `PRIVACY_STATUS=private` and approve each video in YouTube Studio, **or**
- under Settings → Environments → `youtube`, add yourself as a *required reviewer*. Each run then waits for your click before it starts.

## Run locally

```bash
pip install -r requirements.txt            # also needs ffmpeg and libcairo2
python -m kidtoon.pipeline --demo          # built-in story, no keys needed
python -m kidtoon.pipeline --no-upload     # real Claude-written episode, no upload
```

The output goes to `out/`: `episode.mp4`, `thumbnail.jpg`, `episode.json`, `description.txt`.

## Customising

| What | Where |
|---|---|
| Channel name, length, age range, model, voices | `config.json` |
| Schedule | `cron` line in `.github/workflows/daily-episode.yml` |
| Story rules and safety rules | `kidtoon/story.py` (`SAFETY_RULES`, system prompt) |
| Characters, backgrounds | `kidtoon/art.py` (plain SVG drawn in code) |
| Animation, captions, title and end cards | `kidtoon/render.py` |
| Music | `kidtoon/audio.py` (`make_music`) |

Voices use the free `edge-tts` service. If it is unreachable, the pipeline falls back to `espeak-ng`, which sounds robotic. For better voices, swap `tts_line` in `kidtoon/audio.py` to a paid TTS API.

**Cost per episode:** about $0.10–0.25 in Claude API usage. Everything else is free: GitHub Actions minutes for public repos, edge-tts, and the YouTube API.
