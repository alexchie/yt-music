"""Sort uploads into themed YouTube playlists (data/playlists.json).

Each video goes into one mood playlist (rain / night / study / morning / cozy) and, when the
theme mentions one, one season playlist (christmas / winter / autumn). The Chinese and English
uploads of the same video are matched on the same English theme text, so they land in the
matching playlist of each language.

Playlists are created the first time they are needed and their IDs saved in
data/playlist_ids.json. Adding to playlists needs the broader `youtube` OAuth scope; with an
older upload-only token the calls fail with 403 and the upload goes on without playlists.
"""
import json
import re
from pathlib import Path

from googleapiclient.errors import HttpError

DATA = Path(__file__).resolve().parent.parent / "data"
CONFIG = DATA / "playlists.json"
IDS = DATA / "playlist_ids.json"
LANGUAGE_CODES = {"zh": "zh-Hant", "en": "en"}


class NeedsReauth(Exception):
    """The refresh token only allows uploads; run scripts/get_youtube_token.py again."""


def load_config():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def theme_text(theme):
    """The English theme fields the keywords are matched against."""
    titles = [theme.get(k, "") for k in ("cover_title", "cover_subtitle", "youtube_title")]
    # Titles count twice: tags such as "lofi for work" are on most themes and say less about the mood.
    parts = titles + titles + [theme.get("image_query", "")] + theme.get("tags", [])
    return " | ".join(p for p in parts if p).lower()


def _score(text, keywords):
    return sum(len(re.findall(r"(?<!\w)" + re.escape(kw.lower()) + r"s?(?!\w)", text)) for kw in keywords)


def classify(text, config=None):
    """Playlist keys for a video: the best mood (or the fallback) plus the best season, if any."""
    config = config or load_config()
    text = text.lower()
    keys = []
    for group in ("mood", "season"):
        scored = [(_score(text, p["keywords"]), i, p["key"])
                  for i, p in enumerate(config["playlists"]) if p["group"] == group]
        best = max(scored, key=lambda s: (s[0], -s[1]), default=None)
        if best and best[0] > 0:
            keys.append(best[2])
        elif group == "mood":
            keys.append(config["fallback_mood"])
    return keys


class Playlists:
    def __init__(self, youtube, config=None):
        self.youtube = youtube
        self.config = config or load_config()
        self.by_key = {p["key"]: p for p in self.config["playlists"]}
        self.ids = json.loads(IDS.read_text(encoding="utf-8")) if IDS.exists() else {}
        self._existing = None
        self.disabled = False

    def _save(self):
        IDS.write_text(json.dumps(self.ids, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _call(self, request):
        try:
            return request.execute()
        except HttpError as e:
            if e.resp.status in (401, 403) and ("insufficient" in str(e).lower() or "scope" in str(e).lower()
                                                or "permission" in str(e).lower()):
                raise NeedsReauth(str(e)) from e
            raise

    def _find_existing(self, title):
        """A playlist with this title already on the channel (e.g. made by hand), or None."""
        if self._existing is None:
            self._existing, token = {}, None
            while True:
                resp = self._call(self.youtube.playlists().list(
                    part="snippet", mine=True, maxResults=50, pageToken=token))
                for item in resp.get("items", []):
                    self._existing.setdefault(item["snippet"]["title"], item["id"])
                token = resp.get("nextPageToken")
                if not token:
                    break
        return self._existing.get(title)

    def playlist_id(self, key, lang):
        name = f"{key}_{lang}"
        if name in self.ids:
            return self.ids[name]
        info = self.by_key[key].get(lang) or self.by_key[key]["en"]
        playlist_id = self._find_existing(info["title"])
        if not playlist_id:
            snippet = {"title": info["title"], "description": info["description"]}
            if lang in LANGUAGE_CODES:
                snippet["defaultLanguage"] = LANGUAGE_CODES[lang]
            resp = self._call(self.youtube.playlists().insert(
                part="snippet,status", body={"snippet": snippet, "status": {"privacyStatus": "public"}}))
            playlist_id = resp["id"]
            print(f"Created playlist {info['title']}: {playlist_id}")
        self.ids[name] = playlist_id
        self._save()
        return playlist_id

    def add(self, video_id, keys, lang):
        """Add the video to each playlist (newest first). Returns the playlist titles it went into."""
        added = []
        for key in keys:
            if key not in self.by_key:
                continue
            body = {"snippet": {"playlistId": self.playlist_id(key, lang), "position": 0,
                                "resourceId": {"kind": "youtube#video", "videoId": video_id}}}
            try:
                self._call(self.youtube.playlistItems().insert(part="snippet", body=body))
            except HttpError as e:
                if e.resp.status == 400 and "position" in str(e).lower():
                    # Playlists sorted by something other than "manual" refuse a position.
                    del body["snippet"]["position"]
                    self._call(self.youtube.playlistItems().insert(part="snippet", body=body))
                else:
                    raise
            added.append((self.by_key[key].get(lang) or self.by_key[key]["en"])["title"])
        return added
