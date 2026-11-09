# Instagram + Facebook Reels setup (free)

Every day the vertical Short is also posted as an **Instagram Reel** and a **Facebook Page Reel** through
Meta's free Graph API. This is the same method the AI music channel uses. You need an Instagram
**professional** account linked to a **Facebook Page**, plus a Meta app. You can reuse the music
channel's **NGR Uploader** app.

## 1. Instagram professional account
1. Create the account, e.g. `@dailycurio` / `@dailycurio.facts`. Use `assets/branding/profile.png` as the picture.
2. Go to Instagram → **Settings and activity → Account type and tools → Switch to professional account** → **Creator**, and pick category **Education** (or Digital creator).
3. Bio: `History & fascinating facts, every day 🧭 New Top 5 / Top 10 videos daily` plus your YouTube channel link.

## 2. Facebook Page linked to it
1. Create a Page at <https://www.facebook.com/pages/create> named **Daily Curio**, category **Education** or **Media/news company**.
2. Link Instagram: on the Page go to **Settings → Linked accounts → Instagram → Connect**. Or in Instagram, go to **Accounts Center → Accounts → Add accounts**.

## 3. Meta app: reuse NGR Uploader
The music channel's app already has the Instagram product and a privacy policy URL, so nothing needs creating.
1. Open <https://developers.facebook.com/apps> → **NGR Uploader** → **App settings → Basic**.
2. Note the **App ID** and **App Secret**.

## 4. Get a token in the Graph API Explorer
1. Open <https://developers.facebook.com/tools/explorer>.
2. **Meta App** = NGR Uploader, **User or Page** = User Token.
3. Add the permissions `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `instagram_basic`, `instagram_content_publish` and `business_management`.
4. Click **Generate Access Token**. In the popup, tick the **Daily Curio** Page and Instagram account. Keep the music channel's ticked as well, so its token keeps working. Then allow.
5. Copy the token. It lasts only about an hour, so do step 5 straight away.

## 5. Turn it into permanent secrets
On your computer:
```
curl -L -o get_instagram_token.py https://github.com/geekyarya/daily-curio/raw/main/scripts/get_instagram_token.py
pip install requests
python get_instagram_token.py
```
1. Paste the App ID, App Secret and token when asked.
2. When it lists your Pages, choose **Daily Curio**.
3. It saves two values to a Notepad file. The Page token doesn't expire.
4. Add both at <https://github.com/geekyarya/daily-curio/settings/secrets/actions/new>:
   - `IG_USER_ID`
   - `IG_ACCESS_TOKEN`
5. Then delete the Notepad file.

## Notes
- Reels post **publicly** as soon as the daily run finishes, even while YouTube uploads are private. To pause, set `"instagram": {"enabled": false}` and/or `"facebook": {"enabled": false}` in `config.json`.
- Instagram allows 50 API posts a day; Daily Curio posts 1.
- A failed Instagram or Facebook post doesn't stop the YouTube upload. The run is just marked failed with the reason.
