"""Find one copyright-free photo for today's theme on Openverse and download it.

Only CC0 and public-domain images are used, so the video needs no on-screen credit;
the source is still written into the YouTube description. Openverse needs no API key.
Returns None (and the video falls back to the images in assets/backgrounds) when
nothing suitable is found or the service is unreachable.
"""
import json
import random
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.openverse.org/v1/images/"
USER_AGENT = "yt-music-daily/1.0 (https://github.com/alexchie/yt-music)"
MIN_WIDTH = 1600
MIN_RATIO = 1.4  # wide enough to crop to 16:9 without losing most of the picture
GENERIC_QUERIES = ["cozy living room", "cozy interior", "autumn window light"]


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def search(query):
    params = urllib.parse.urlencode({
        "q": query,
        "license": "cc0,pdm",
        "category": "photograph",
        "aspect_ratio": "wide",
        "size": "large",
        "mature": "false",
        "page_size": 20,
    })
    return json.loads(_get(f"{API}?{params}"))["results"]


def queries(theme):
    """The theme's own image_query first, then the cover title with fewer and fewer words."""
    out = []
    if theme.get("image_query"):
        out.append(theme["image_query"])
    words = [w for w in theme.get("cover_title", "").split() if len(w) > 2]
    for n in range(len(words), 1, -1):
        out.append(" ".join(words[:n]))
    return out + GENERIC_QUERIES


def usable(result, used_ids):
    w, h = result.get("width") or 0, result.get("height") or 0
    return (
        result.get("id") not in used_ids
        and result.get("url")
        and w >= MIN_WIDTH
        and h
        and w / h >= MIN_RATIO
    )


def credit(result):
    """One line for the description, e.g. Background photo: "Title" by X (CC0) via Flickr: <url>."""
    title = (result.get("title") or "Untitled").strip()
    by = f" by {result['creator']}" if result.get("creator") else ""
    lic = "Public Domain" if result.get("license") == "pdm" else f"CC0 {result.get('license_version') or '1.0'}"
    via = f" via {result['source'].title()}" if result.get("source") else ""
    line = f'Background photo: "{title}"{by} ({lic}){via}: {result.get("foreign_landing_url") or result["url"]}'
    return line.replace("<", "").replace(">", "")


def fetch(theme, used_ids, out_dir, seed):
    """Download one image for the theme. Returns (path, info dict) or None."""
    rng = random.Random(seed)
    for query in queries(theme):
        try:
            results = [r for r in search(query) if usable(r, used_ids)]
        except Exception as e:  # network or API error: try the next query, then give up
            print(f"Openverse search failed for {query!r}: {e}")
            continue
        rng.shuffle(results)
        for result in results[:5]:
            try:
                data = _get(result["url"], timeout=60)
            except Exception as e:
                print(f"Download failed for {result['url']}: {e}")
                continue
            path = Path(out_dir) / f"background_{result['id']}"
            path.write_bytes(data)
            print(f"Background from Openverse ({query!r}): {result.get('title')} - {result.get('foreign_landing_url')}")
            return path, {
                "id": result["id"],
                "query": query,
                "title": result.get("title"),
                "creator": result.get("creator"),
                "license": result.get("license"),
                "landing_url": result.get("foreign_landing_url"),
                "image_url": result["url"],
                "credit": credit(result),
            }
    return None
