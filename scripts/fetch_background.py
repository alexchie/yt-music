"""Find one copyright-free photo for today's theme and download it.

Wikimedia Commons is searched first, then Openverse (which often times out from
GitHub's runners). Only CC0 and public-domain images are used, so the video needs
no on-screen credit; the source is still written into the YouTube description.
Neither service needs an API key. Returns None (and the video falls back to the
images in assets/backgrounds) when nothing suitable is found or both are unreachable.
"""
import json
import random
import re
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
OPENVERSE_API = "https://api.openverse.org/v1/images/"
USER_AGENT = "yt-music-daily/1.0 (https://github.com/alexchie/yt-music)"
MIN_WIDTH = 1600
MIN_RATIO = 1.4  # wide enough to crop to 16:9 without losing most of the picture
DOWNLOAD_WIDTH = 1920
GENERIC_QUERIES = ["cozy living room", "cozy interior", "autumn window light"]
# These Openverse sources only hand out small previews (960-1024 px), never the original.
SMALL_PREVIEW_SOURCES = {"rawpixel", "stocksnap"}


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _plain(html):
    """Commons metadata is HTML; keep the text."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()


def search_commons(query):
    params = urllib.parse.urlencode({
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrnamespace": 6,  # File: pages
        "gsrsearch": f"{query} filetype:bitmap",
        "gsrlimit": 40,
        "prop": "imageinfo",
        "iiprop": "url|size|extmetadata",
        "iiextmetadatafilter": "License|LicenseShortName|Artist|ObjectName",
        "iiurlwidth": DOWNLOAD_WIDTH,
    })
    pages = json.loads(_get(f"{COMMONS_API}?{params}", timeout=20)).get("query", {}).get("pages", {})
    out = []
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        meta = {k: (v or {}).get("value", "") for k, v in (info.get("extmetadata") or {}).items()}
        short = _plain(meta.get("LicenseShortName")).lower()
        if meta.get("License", "").lower() == "cc0" or "cc0" in short:
            lic = "CC0 1.0"
        elif meta.get("License", "").lower() == "pd" or short.startswith("public domain"):
            lic = "Public Domain"
        else:
            continue
        out.append({
            "id": f"commons:{page.get('pageid')}",
            "url": info.get("thumburl") or info.get("url"),
            "width": info.get("width"),
            "height": info.get("height"),
            "title": _plain(meta.get("ObjectName")) or page.get("title", "").removeprefix("File:").rsplit(".", 1)[0],
            "creator": _plain(meta.get("Artist"))[:80],
            "license": lic,
            "source": "Wikimedia Commons",
            "landing_url": info.get("descriptionurl"),
        })
    return out


def search_openverse(query):
    params = urllib.parse.urlencode({
        "q": query, "license": "cc0,pdm", "category": "photograph",
        "aspect_ratio": "wide", "size": "large", "mature": "false", "page_size": 20,
    })
    results = json.loads(_get(f"{OPENVERSE_API}?{params}", timeout=15))["results"]
    return [{
        "id": r["id"],
        "url": r.get("url"),
        "width": r.get("width"),
        "height": r.get("height"),
        "title": r.get("title"),
        "creator": r.get("creator"),
        "license": "Public Domain" if r.get("license") == "pdm" else f"CC0 {r.get('license_version') or '1.0'}",
        "source": (r.get("source") or "").title(),
        "landing_url": r.get("foreign_landing_url") or r.get("url"),
    } for r in results if r.get("source") not in SMALL_PREVIEW_SOURCES]


SOURCES = [("Commons", search_commons), ("Openverse", search_openverse)]


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
    """Size metadata can be missing, so only reject what is known to be too small;
    the downloaded file is checked again."""
    if result["id"] in used_ids or not result.get("url"):
        return False
    w, h = result.get("width") or 0, result.get("height") or 0
    if w and w < MIN_WIDTH:
        return False
    return not (w and h and w / h < MIN_RATIO)


def credit(result):
    """One line for the description, e.g. Background photo: "Title" by X (CC0 1.0) via Wikimedia Commons: <url>."""
    title = (result.get("title") or "Untitled").strip()
    by = f" by {result['creator']}" if result.get("creator") else ""
    via = f" via {result['source']}" if result.get("source") else ""
    line = f'Background photo: "{title}"{by} ({result["license"]}){via}: {result["landing_url"]}'
    return line.replace("<", "").replace(">", "")


def fetch(theme, used_ids, out_dir, seed):
    """Download one image for the theme. Returns (path, info dict) or None."""
    rng = random.Random(seed)
    for name, search in SOURCES:
        failures = 0
        for query in queries(theme):
            try:
                found = search(query)
            except Exception as e:  # network or API error: try the next query
                print(f"{name} search failed for {query!r}: {e}")
                failures += 1
                if failures >= 2:  # the service is down; don't wait on every query
                    break
                continue
            results = [r for r in found if usable(r, used_ids)]
            print(f"{name} {query!r}: {len(found)} copyright-free results, {len(results)} usable")
            rng.shuffle(results)
            for result in results[:6]:
                try:
                    data = _get(result["url"], timeout=60)
                except Exception as e:
                    print(f"Download failed for {result['url']}: {e}")
                    continue
                path = Path(out_dir) / f"background_{re.sub(r'[^A-Za-z0-9-]', '_', str(result['id']))}"
                path.write_bytes(data)
                # Some sources only serve a small preview even when the original is large.
                try:
                    with Image.open(path) as img:
                        real_width, real_height = img.size
                except Exception:
                    real_width, real_height = 0, 1
                if real_width < MIN_WIDTH or real_width / real_height < MIN_RATIO:
                    print(f"Skipped {result['url']}: {real_width}x{real_height}")
                    continue
                print(f"Background from {name} ({query!r}): {result.get('title')} - {result['landing_url']}")
                return path, {
                    "id": result["id"],
                    "query": query,
                    "title": result.get("title"),
                    "creator": result.get("creator"),
                    "license": result["license"],
                    "landing_url": result["landing_url"],
                    "image_url": result["url"],
                    "credit": credit(result),
                }
    return None
