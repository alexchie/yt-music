"""Daily themes from data/themes.json: cover text, YouTube title, description and tags."""
import json
import random
from pathlib import Path

THEMES = Path(__file__).resolve().parent.parent / "data" / "themes.json"

# Appended to every description; one is picked per day so the closing line varies.
CALLS_TO_ACTION = [
    "If this hour kept you company, leave a like and subscribe for a new lofi playlist every day. Tell us in the comments what you're doing while you listen.",
    "Subscribe for a fresh hour of lofi every day, and let us know in the comments what the weather is like where you are.",
    "A like and a subscribe help this little room reach more people. What are you working on today? Tell us below.",
    "New lofi playlist every day. Subscribe so you don't miss tomorrow's, and share what you're up to in the comments.",
    "Thanks for spending this hour here. Like, subscribe, and drop a comment with what you're listening from: your desk, your sofa, your train seat.",
    "If you'd like more slow hours like this one, subscribe. And tell us: coffee or tea today?",
]

# Added after each theme's own tags; YouTube allows about 500 characters in total.
BASE_TAGS = [
    "lofi", "lofi beats", "lofi hip hop", "chill beats", "instrumental lofi",
    "lofi no vocals", "study music", "relaxing music", "lofi playlist", "1 hour lofi",
]


def load():
    return json.loads(THEMES.read_text(encoding="utf-8"))


def for_date(themes, today):
    return next((t for t in themes if t["date"] == today.isoformat()), None)


def remaining(themes, today):
    """How many themes are scheduled after today."""
    return sum(1 for t in themes if t["date"] > today.isoformat())


def call_to_action(today):
    return random.Random(today.toordinal()).choice(CALLS_TO_ACTION)


def all_tags(theme):
    tags, length = [], 0
    for tag in theme["tags"] + BASE_TAGS:
        if tag.lower() in (t.lower() for t in tags) or length + len(tag) + 1 > 480:
            continue
        tags.append(tag)
        length += len(tag) + 1
    return tags


def fallback(today):
    """Plain theme used when nothing is scheduled for today, so the video still ships."""
    return {
        "cover_title": "Living Room Lofi",
        "cover_subtitle": f"a playlist for {today:%B %d}",
        "youtube_title": f"living room lofi session • {today:%B %d, %Y} • 1 hour of chill beats",
        "description": (
            "Soft light in the living room, lofi beats on the speakers, and an hour with nowhere else to be.\n\n"
            "Instrumental lofi with no vocals for reading, working from home or a slow coffee break."
        ),
        "hashtags": ["#lofi", "#chillbeats", "#studymusic"],
        "tags": ["living room lofi"],
        "theme_note_zh": "（主題庫裡沒有今天的主題，使用備用的通用標題）",
    }
