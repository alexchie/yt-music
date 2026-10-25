"""One-time helper, run on your own computer: sign in to the YouTube channel and print
the refresh token to save as the GitHub secret YT_REFRESH_TOKEN.

Usage:
    pip install google-auth-oauthlib
    python scripts/get_youtube_token.py                      # asks for the client ID and secret
    python scripts/get_youtube_token.py client_secret.json   # or reads the downloaded JSON
"""
import json
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def client_config():
    if len(sys.argv) > 1:
        return json.load(open(sys.argv[1], encoding="utf-8"))
    client_id = input("OAuth 用戶端 ID: ").strip()
    client_secret = input("OAuth 用戶端密碼: ").strip()
    return {"installed": {
        "client_id": client_id,
        "client_secret": client_secret,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }}


def main():
    config = client_config()
    flow = InstalledAppFlow.from_client_config(config, SCOPES)
    # prompt=consent makes Google return a refresh token even if you signed in before.
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    client = config["installed"]
    print("\nSave these as GitHub repository secrets:\n")
    print(f"YT_CLIENT_ID      = {client['client_id']}")
    print(f"YT_CLIENT_SECRET  = {client['client_secret']}")
    print(f"YT_REFRESH_TOKEN  = {creds.refresh_token}")


if __name__ == "__main__":
    main()
