"""One-time helper: run on your own computer to get a YouTube refresh token.

1. Google Cloud Console -> create a project -> enable "YouTube Data API v3".
2. OAuth consent screen -> External -> add yourself as a test user,
   then click "Publish app" (In production) so the refresh token doesn't expire after 7 days.
3. Credentials -> Create OAuth client ID -> "Desktop app" -> download JSON as client_secret.json.
4. pip install google-auth-oauthlib && python scripts/get_youtube_token.py client_secret.json
5. Sign in with the Google account that owns the kids channel (pick the channel if asked).
"""
import json
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]

path = sys.argv[1] if len(sys.argv) > 1 else "client_secret.json"
flow = InstalledAppFlow.from_client_secrets_file(path, SCOPES)
creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
client = json.load(open(path))["installed"]
print("\nAdd these as GitHub repository secrets (Settings -> Secrets and variables -> Actions):\n")
print(f"YOUTUBE_CLIENT_ID={client['client_id']}")
print(f"YOUTUBE_CLIENT_SECRET={client['client_secret']}")
print(f"YOUTUBE_REFRESH_TOKEN={creds.refresh_token}")
