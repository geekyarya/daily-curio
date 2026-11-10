# Daily Curio: an automated Hindi facts YouTube channel (free services only)

Every day a GitHub Actions workflow writes, fact-checks, illustrates, narrates **in Hindi**, animates and uploads:

- **one long video**, alternating between a **Top 10** (~6 min) and a **Top 5** (~3–4 min) countdown of quick, surprising facts, and
- **one vertical Short** built around the most surprising fact from that video.

The facts cover anything: science, animals, the human body, space, food, India, world geography, everyday things,
psychology, technology, oceans, money, sports, records, nature, inventions, language, weather and odd moments from
history. Recently used themes are skipped. Narration, titles, on-screen text and captions are in Hindi
(Devanagari, with common English words like "Facts"). Image prompts stay in English for the image model.

| Step | Service | Free allowance |
|---|---|---|
| Script and a separate fact-check review | Google **Gemini API** free tier | plenty: a few requests per run |
| Illustrations (painted documentary style) | **Cloudflare Workers AI**, FLUX.2 [klein] | 10,000 neurons/day ≈ 60 images; a run uses 30–47 |
| Hindi narration (`hi-IN-MadhurNeural`; `hi-IN-SwaraNeural` for a female voice) | Microsoft Edge neural voices (`edge-tts`) | free, no key |
| Music | your own royalty-free tracks in `assets/music/`, else a generated melody | free |
| Animation and encoding | Python + ffmpeg on GitHub Actions | free for public repos |
| Publishing | YouTube Data API | 10,000 units/day; about 3,600 used per run |

## What the videos look like

- Vivid digital illustrations with slow camera moves, crossfades and subtle dust, embers or snow.
- A title card, then an animated **"#7 · समुद्र का सबसे गहरा राज़"** card at the start of each fact.
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
   - `YT_TOKEN`: one JSON secret, `{"client_id": "...", "client_secret": "...", "refresh_token": "...", "token_uri": "https://oauth2.googleapis.com/token"}`. Get the refresh token from https://developers.google.com/oauthplayground using your own **Web application** OAuth client (redirect URI `https://developers.google.com/oauthplayground`). Use the scopes `youtube.upload`, plus `youtube.force-ssl` for captions. Sign in as the channel owner and pick this channel. The consent screen must be **In production**, or the token expires in 7 days. Separate `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET` / `YOUTUBE_REFRESH_TOKEN` secrets also work.
2. **Variables** (optional): `PRIVACY_STATUS` (`private` by default, or `unlisted` / `public`), and `YOUTUBE_PLAYLIST_ID`.
3. **Channel art**: upload `assets/branding/banner.png` and `assets/branding/profile.png` in YouTube Studio → Customization → Branding.

## Running it

- **Automatically** every day at 13:23 UTC (18:53 IST). A backup run at 16:23 UTC posts only if nothing went up that day. Keep extra runs to a minimum: Cloudflare's free image allowance behaves like a rolling 24-hour window, so two big runs close together can run out. Change the `cron` line in `.github/workflows/daily-video.yml`.
- **By hand:** Actions → *Daily video + Short* → *Run workflow*. You can pick the format (`auto`, `top10`, `top5`), give a theme such as *"समुद्र के रहस्य"* or *"facts about the brain"*, and tick *dry run* to make the videos without uploading.
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
