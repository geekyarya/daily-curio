# Maple Meadow Friends: an automated kids' story channel (free services only)

Every day, a GitHub Actions workflow makes and uploads a **~6-minute illustrated story episode** and a
**vertical YouTube Short**. Nothing in it costs money.

| Step | Service | Free allowance |
|---|---|---|
| Story, storyboard and kid-safety review | Google **Gemini API** free tier | plenty: about 4–10 requests per run |
| Illustrations, with the same characters in every shot | **Cloudflare Workers AI**, FLUX.2 [klein] with character reference images | 10,000 neurons/day ≈ 55–60 images; one episode + Short uses about 35 |
| Character and narrator voices | Microsoft Edge neural voices (`edge-tts`) | free, no key |
| Music | your own royalty-free tracks in `assets/music/`, else a generated melody | free |
| Animation and encoding | Python + ffmpeg on GitHub Actions | free for public repos |
| Publishing | YouTube Data API | 10,000 units/day; about 3,600 used per run |

## What the videos look like

- Every shot is a painted storybook illustration. Tumble the bear cub, Pippa the bird and Moss the tortoise stay consistent because each image is drawn from the character reference sheets in `assets/cast/`.
- Slow camera moves (zooms and pans), crossfades between shots, and animated particles (snow, fireflies, petals, bubbles, sparkles).
- An animated title card, an end card with the lesson, a separate voice for each character, music that dips under speech, and English captions uploaded to YouTube.
- The Short is a 9:16 mini-story with burned-in captions. It is scheduled to go live 6 hours after the episode.

## Setup (once, about 30 minutes)

1. **Push this folder to a new public GitHub repo.** Public repos get unlimited free Actions minutes.

2. **Gemini (stories)**: create a free key at https://aistudio.google.com/apikey and save it as the repo secret `GEMINI_API_KEY`.

3. **Cloudflare (pictures)**: sign up free at https://dash.cloudflare.com.
   - Your *Account ID* is in the dashboard sidebar. Save it as the secret `CLOUDFLARE_ACCOUNT_ID`.
   - Go to My Profile → API Tokens → Create Token → "Workers AI" template. Save the token as the secret `CLOUDFLARE_API_TOKEN`.

4. **YouTube**
   - In Google Cloud Console, create a project and enable **YouTube Data API v3**.
   - Set up the OAuth consent screen (External), add yourself as a test user, then **Publish app** so the login doesn't expire after 7 days.
   - Create an OAuth client ID of type **Desktop app** and download it as `client_secret.json`.
   - On your own computer, run:
     ```bash
     pip install google-auth-oauthlib
     python scripts/get_youtube_token.py client_secret.json
     ```
   - Sign in as the channel owner, then save the 3 printed values as the secrets `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET` and `YOUTUBE_REFRESH_TOKEN`.

5. **Optional repo variables**: `PRIVACY_STATUS` (`private` by default, or `unlisted` / `public`) and `YOUTUBE_PLAYLIST_ID`.

6. **First run**: edit `.github/preview-request` (any change) and push it, which starts a dry run. Or go to Actions → *Daily episode + Short* → *Run workflow* with **dry_run** ticked.
   - The first run designs the 3 characters and commits them to `assets/cast/`.
   - Download the videos from the run's artifacts and check them.
   - If you don't like a character, replace its PNG with your own drawing, or delete it so it's redesigned on the next run.

## Important YouTube rules

- **Upload audit.** API projects created after July 2020 can only upload **private** videos until they pass Google's free [YouTube API audit](https://support.google.com/youtube/contact/yt_api_form). Apply early, and publish by hand in YouTube Studio until then.
- **Made for Kids** (COPPA) and the **AI content** label are set automatically on every upload.
- **Monetization.** YouTube can refuse to monetise mass-produced or repetitive videos. Watch the episodes, keep the stories varied, and add your own touches (characters, music, intro).
- **Thumbnails** need a phone-verified channel.

## Human review (strongly recommended for a kids' channel)

Gemini reviews each script against strict child-safety rules before anything is drawn, but a person should still check the result. Either:

- keep `PRIVACY_STATUS=private` and publish each video yourself in YouTube Studio, **or**
- under Settings → Environments → `youtube`, add yourself as a *required reviewer*. Each run then waits for your approval.

## Customising

| What | Where |
|---|---|
| Channel name, episode length, art style, characters, voices, schedule of Shorts | `config.json` |
| Daily time | `cron` in `.github/workflows/daily-episode.yml` |
| Story and safety rules | `kidtoon/story.py` |
| Camera moves, effects, title and end cards | `kidtoon/render.py` |
| Music | drop `.mp3` files into `assets/music/` (e.g. from the YouTube Audio Library, *no attribution required* filter) |

## Run locally

```bash
pip install -r requirements.txt     # also needs ffmpeg
export GEMINI_API_KEY=... CLOUDFLARE_ACCOUNT_ID=... CLOUDFLARE_API_TOKEN=...
python -m kidtoon.pipeline --no-upload
python -m kidtoon.pipeline --demo   # built-in script, no Gemini needed
```

The output goes to `out/`: `episode.mp4`, `short.mp4`, `thumbnail.jpg`, `episode.srt`, `episode.json`, plus every illustration in `out/images/`.

**If the daily image allowance runs out**, the run stops before uploading anything, so no off-model video gets published. One episode + Short needs about 35 images, which fits comfortably in the free allowance.
You can add `"pollinations"` (with a free `POLLINATIONS_API_KEY` from https://enter.pollinations.ai) or `"cloudflare_schnell"` to `image.providers` in `config.json` as fallbacks. Neither can use the character reference sheets, so characters may look different.

`--demo` without a Cloudflare key uses the anonymous Pollinations endpoint for low-quality preview art. It's only for checking that the pipeline runs.
