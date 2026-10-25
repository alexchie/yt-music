"""Upload the newest video in the Drive output folder to YouTube.

The workflow downloads the folder with rclone first; this script picks the newest
`*.mp4` that has a matching `_description.txt`, uploads it with that title, description
and tags, sets `_cover.jpg` as the thumbnail, and records it in data/uploads.json so
the same file is never uploaded twice.

Needs env vars: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN (see
scripts/get_youtube_token.py), and optionally YT_PRIVACY (public / unlisted / private).

Usage: python scripts/upload_youtube.py <folder>
"""
import datetime
import json
import os
import sys
import time
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).resolve().parent.parent
UPLOADS = ROOT / "data" / "uploads.json"
TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CATEGORY_MUSIC = "10"


def parse_description_file(path):
    """Read the TITLE / DESCRIPTION / TAGS sections written by make_video.py."""
    sections, current = {}, None
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip() in ("TITLE", "DESCRIPTION", "TAGS"):
            current = line.strip()
            sections[current] = []
        elif current:
            sections[current].append(line)
    text = {k: "\n".join(v).strip() for k, v in sections.items()}
    title = text.get("TITLE", "").replace("<", "").replace(">", "")[:100]
    description = text.get("DESCRIPTION", "").replace("<", "").replace(">", "")
    tags = [t.strip() for t in text.get("TAGS", "").split(",") if t.strip()]
    return title, description, tags


def newest_video(folder, done):
    """The newest mp4 with a description file that has not been uploaded yet."""
    candidates = []
    for video in folder.glob("*.mp4"):
        desc = video.with_name(f"{video.stem}_description.txt")
        if desc.exists() and video.name not in done:
            candidates.append(video)
    return max(candidates, key=lambda p: p.name, default=None)  # names start with the date


def youtube_client():
    creds = Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri=TOKEN_URI,
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload(youtube, video, title, description, tags, privacy):
    body = {
        "snippet": {"title": title, "description": description, "tags": tags, "categoryId": CATEGORY_MUSIC},
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(str(video), chunksize=16 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response, retries = None, 0
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                print(f"  {int(status.progress() * 100)}%", flush=True)
        except HttpError as e:
            if e.resp.status not in (500, 502, 503, 504) or retries >= 5:
                raise
            retries += 1
            time.sleep(2 ** retries)
        except (ConnectionError, TimeoutError):
            if retries >= 5:
                raise
            retries += 1
            time.sleep(2 ** retries)
    return response


def main():
    folder = Path(sys.argv[1])
    uploads = json.loads(UPLOADS.read_text(encoding="utf-8")) if UPLOADS.exists() else []
    done = {u["file"] for u in uploads}
    video = newest_video(folder, done)
    if video is None:
        print("Nothing new to upload.")
        return

    title, description, tags = parse_description_file(video.with_name(f"{video.stem}_description.txt"))
    privacy = os.environ.get("YT_PRIVACY") or "public"
    print(f"Uploading {video.name} as {privacy}: {title}")
    youtube = youtube_client()
    response = upload(youtube, video, title, description, tags, privacy)
    video_id = response["id"]
    actual_privacy = response.get("status", {}).get("privacyStatus", privacy)
    print(f"Uploaded: https://youtu.be/{video_id} ({actual_privacy})")

    thumbnail = "skipped"
    cover = video.with_name(f"{video.stem}_cover.jpg")
    if cover.exists():
        try:
            youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(cover))).execute()
            thumbnail = "set"
        except HttpError as e:
            # Custom thumbnails need a phone-verified channel; the upload itself still counts.
            thumbnail = f"failed: {e.reason}"
            print(f"Thumbnail not set: {e.reason}")

    uploads.append({
        "file": video.name,
        "video_id": video_id,
        "url": f"https://youtu.be/{video_id}",
        "title": title,
        "privacy": actual_privacy,
        "thumbnail": thumbnail,
        "uploaded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    })
    UPLOADS.parent.mkdir(exist_ok=True)
    UPLOADS.write_text(json.dumps(uploads, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
