# Daily Curio: an automated history & facts YouTube channel (free services only)

Every day a GitHub Actions workflow writes, fact-checks, illustrates, narrates, animates and uploads:

- **one long video**, rotating between a **Top 10** list (~9 min), a **history story** (~8 min) and a **Top 5** list (~5 min), and
- **one vertical Short** built around the most surprising fact from that video.

Topics rotate across ancient, medieval, modern and strange history, inventions, everyday objects, food, the human body,
animals, space, oceans, geography, language and famous mysteries. Recently used topics are skipped.

| Step | Service | Free allowance |
|---|---|---|
| Script and a separate fact-check review | Google **Gemini API** free tier | plenty: a few requests per run |
| Illustrations (painted documentary style) | **Cloudflare Workers AI**, FLUX.2 [klein] | 10,000 neurons/day ≈ 60 images; a run uses 30–47 |
| Narration (British documentary voice) | Microsoft Edge neural voices (`edge-tts`) | free, no key |
| Music | your own royalty-free tracks in `assets/music/`, else a generated melody | free |
| Animation and encoding | Python + ffmpeg on GitHub Actions | free for public repos |
| Publishing | YouTube Data API | 10,000 units/day; about 3,600 used per run |

## What the videos look like

- Painted documentary illustrations with slow camera moves, crossfades and subtle dust, embers or snow.
- A title card, then an animated **"#7 · The Emperor Who Fought the Sea"** card at the start of each list item (or each chapter of a story).
- The narrator ends with a recap and a comments question. English captions are uploaded, and the thumbnail is the image plus 2–4 huge words.
- Shorts are 9:16 with burned-in captions. They're scheduled to go live 6 hours after the main video.

## Accuracy

Gemini writes each script under strict rules:
- well-documented facts only
- no myths presented as true
- disputed points flagged as disputed
- no invented quotes, and no over-precise numbers

A **second Gemini pass works as a fact-checker** and rejects the script if any claim is doubtful. That catches a lot, but it is still AI, so **watch videos before making them public**, especially early on.

## Setup

1. **Secrets** (repo Settings → Secrets and variables → Actions):
   - `GEMINI_API_KEY`: from https://aistudio.google.com/apikey
   - `CLOUDFLARE_API_TOKEN`: Cloudflare → Manage account → Account API tokens → Create token, with the **Workers AI** permission. The account ID is looked up automatically. You can also set `CLOUDFLARE_ACCOUNT_ID`.
   - `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`: run `python scripts/get_youtube_token.py client_secret.json` on your computer. The Google Cloud steps are in that file.
2. **Variables** (optional): `PRIVACY_STATUS` (`private` by default, or `unlisted` / `public`), and `YOUTUBE_PLAYLIST_ID`.
3. **Channel art**: upload `assets/branding/banner.png` and `assets/branding/profile.png` in YouTube Studio → Customization → Branding.

## Running it

- **Automatically** every day at 13:17 UTC. Change the `cron` line in `.github/workflows/daily-video.yml`.
- **By hand:** Actions → *Daily video + Short* → *Run workflow*. You can pick the format (`auto`, `top10`, `top5`, `story`), give a topic such as *"Strange laws of medieval England"*, and tick *dry run* to make the videos without uploading.
- **Preview without uploading:** edit `.github/preview-request` and push. Optional lines `format=top5` and `topic=...` choose what to make.
- Download the results from the run page → **Artifacts**: `video.mp4`, `short.mp4`, `thumbnail.jpg`, `video.srt`, `video.json`.

## YouTube notes

- **Upload audit.** API projects created after July 2020 upload as **private** until they pass Google's free [YouTube API audit](https://support.google.com/youtube/contact/yt_api_form). Apply early, and publish by hand in YouTube Studio until then.
- **AI label:** `"ai_disclosure": false` in `config.json` leaves AI wording out of descriptions and leaves the "altered or synthetic content" box unticked. YouTube requires that box when content **looks realistic**, such as realistic scenes of real places or events. The painted style is meant to read as illustration. If you switch to a photo-realistic style, set `ai_disclosure` to `true`.
- **Made for Kids** is off (`"made_for_kids": false`), because the channel targets teens and adults.
- **Monetization:** YouTube can refuse to monetize repetitive, mass-produced videos. Review videos, vary topics, and add your own voice or edits where you can.

## Customising (`config.json`)

| Setting | What it does |
|---|---|
| `channel_name`, `tagline` | Shown in videos, descriptions and channel art |
| `formats`, `format_specs` | Which formats rotate, and their length and shot counts |
| `categories` | The topic pool |
| `narrator_voice` | Any edge-tts voice, e.g. `en-US-AndrewNeural`, `en-GB-RyanNeural` |
| `image.style` | The art style prompt used for every image |
| `burn_captions` | Burn captions into the long video too |

After changing the name or tagline, run `python -m curio.branding` to regenerate the banner and profile picture.

## Run locally

```bash
pip install -r requirements.txt   # also needs ffmpeg
```

```bash
export GEMINI_API_KEY=... CLOUDFLARE_API_TOKEN=...
```

```bash
python -m curio.pipeline --no-upload --format top5 --topic "Odd jobs that no longer exist"
```

Output goes to `out/`.
