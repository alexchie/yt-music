"""One-time helper, run on your own computer: sign in to the YouTube channel and print
the three values to save as GitHub secrets (YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN).

Usage:
    pip install google-auth-oauthlib
    python scripts/get_youtube_token.py path/to/client_secret.json
"""
import json
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main():
    secret_file = sys.argv[1] if len(sys.argv) > 1 else "client_secret.json"
    flow = InstalledAppFlow.from_client_secrets_file(secret_file, SCOPES)
    # prompt=consent makes Google return a refresh token even if you signed in before.
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    client = json.load(open(secret_file, encoding="utf-8"))["installed"]
    print("\nSave these three as GitHub repository secrets:\n")
    print(f"YT_CLIENT_ID      = {client['client_id']}")
    print(f"YT_CLIENT_SECRET  = {client['client_secret']}")
    print(f"YT_REFRESH_TOKEN  = {creds.refresh_token}")


if __name__ == "__main__":
    main()
