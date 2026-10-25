"""Upload the videos in the Drive output folder to YouTube, one upload per language.

The workflow downloads the folder with rclone first. make_video.py writes, for every
`<base>.mp4`, a `<base>_<lang>_description.txt` and `<base>_<lang>_cover.jpg` per
language; each description file becomes its own YouTube upload with that title,
description and tags, the matching cover as thumbnail, and a scheduled publish time
(PUBLISH_AT) when that is still in the future. Uploads are recorded in
data/uploads.json so the same version is never uploaded twice.

Needs env vars: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN (see
scripts/get_youtube_token.py), and optionally YT_PRIVACY (public / unlisted / private).

Usage: python scripts/upload_youtube.py <folder>
"""
import datetime
import json
import os
import re
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
LANGUAGE_CODES = {"zh": "zh-Hant", "en": "en"}
MAX_PER_RUN = 4  # 4 uploads + thumbnails stay well inside the 10,000 unit daily quota
# A publish time closer than this is treated as "now": YouTube needs some lead time.
MIN_LEAD = datetime.timedelta(minutes=15)


def parse_description_file(path):
    """Read the TITLE / DESCRIPTION / TAGS / LANGUAGE / PUBLISH_AT sections written by make_video.py."""
    sections, current = {}, None
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip() in ("TITLE", "DESCRIPTION", "TAGS", "LANGUAGE", "PUBLISH_AT"):
            current = line.strip()
            sections[current] = []
        elif current:
            sections[current].append(line)
    text = {k: "\n".join(v).strip() for k, v in sections.items()}
    title = text.get("TITLE", "").replace("<", "").replace(">", "")[:100]
    description = text.get("DESCRIPTION", "").replace("<", "").replace(">", "")
    tags = [t.strip() for t in text.get("TAGS", "").split(",") if t.strip()]
    publish_at = datetime.datetime.fromisoformat(text["PUBLISH_AT"]) if text.get("PUBLISH_AT") else None
    return {"title": title, "description": description, "tags": tags,
            "lang": text.get("LANGUAGE", ""), "publish_at": publish_at}


def pending(folder, done):
    """(video, description file, cover) for every language version not uploaded yet, oldest first."""
    out = []
    for desc in sorted(folder.glob("*_description.txt")):
        m = re.match(r"(.+)_(zh|en)_description\.txt$", desc.name)
        if not m or desc.name in done:
            continue
        video = folder / f"{m.group(1)}.mp4"
        if video.exists():
            out.append((video, desc, folder / f"{m.group(1)}_{m.group(2)}_cover.jpg"))
    return out


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


def upload(youtube, video, meta, privacy, publish_at):
    lang = LANGUAGE_CODES.get(meta["lang"])
    snippet = {"title": meta["title"], "description": meta["description"], "tags": meta["tags"],
               "categoryId": CATEGORY_MUSIC}
    if lang:
        snippet["defaultLanguage"] = lang
    status = {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}
    if publish_at:
        # Scheduled videos must be private until YouTube publishes them at publishAt.
        status.update(privacyStatus="private", publishAt=publish_at.astimezone(datetime.timezone.utc).isoformat())
    body = {"snippet": snippet, "status": status}
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
    jobs = pending(folder, done)[:MAX_PER_RUN]
    if not jobs:
        print("Nothing new to upload.")
        return

    privacy = os.environ.get("YT_PRIVACY") or "public"
    youtube = youtube_client()
    now = datetime.datetime.now(datetime.timezone.utc)
    for video, desc, cover in jobs:
        meta = parse_description_file(desc)
        publish_at = meta["publish_at"] if meta["publish_at"] and meta["publish_at"] - now > MIN_LEAD else None
        when = f"scheduled for {publish_at.isoformat()}" if publish_at else privacy
        print(f"Uploading {desc.name} ({when}): {meta['title']}")
        response = upload(youtube, video, meta, privacy, publish_at)
        video_id = response["id"]
        actual_privacy = response.get("status", {}).get("privacyStatus", privacy)
        print(f"Uploaded: https://youtu.be/{video_id} ({actual_privacy})")

        thumbnail = "skipped"
        if cover.exists():
            try:
                youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(cover))).execute()
                thumbnail = "set"
            except HttpError as e:
                # Custom thumbnails need a phone-verified channel; the upload itself still counts.
                thumbnail = f"failed: {e.reason}"
                print(f"Thumbnail not set: {e.reason}")

        uploads.append({
            "file": desc.name,
            "video_file": video.name,
            "lang": meta["lang"],
            "video_id": video_id,
            "url": f"https://youtu.be/{video_id}",
            "title": meta["title"],
            "privacy": actual_privacy,
            "publish_at": publish_at.isoformat() if publish_at else None,
            "thumbnail": thumbnail,
            "uploaded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        })
        # Save after every upload so a later failure never causes a duplicate.
        UPLOADS.parent.mkdir(exist_ok=True)
        UPLOADS.write_text(json.dumps(uploads, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
