"""Daily themes from data/themes.json: cover text, YouTube title, description and tags."""
import json
import random
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
THEMES = DATA / "themes.json"
# Undated themes for the evening video, used in order; each has English fields and a "zh" block.
POOL = DATA / "themes_pool.json"

# Appended to every description; one is picked per day so the closing line varies.
CALLS_TO_ACTION = [
    "If this hour kept you company, leave a like and subscribe for a new lofi playlist every day. Tell us in the comments what you're doing while you listen.",
    "Subscribe for a fresh hour of lofi every day, and let us know in the comments what the weather is like where you are.",
    "A like and a subscribe help this little room reach more people. What are you working on today? Tell us below.",
    "New lofi playlist every day. Subscribe so you don't miss tomorrow's, and share what you're up to in the comments.",
    "Thanks for spending this hour here. Like, subscribe, and drop a comment with what you're listening from: your desk, your sofa, your train seat.",
    "If you'd like more slow hours like this one, subscribe. And tell us: coffee or tea today?",
]

CALLS_TO_ACTION_ZH = [
    "如果這一小時有陪到你，按個讚、訂閱頻道，每天都有新的 lofi 歌單。留言告訴我們你正在做什麼吧！",
    "訂閱頻道，每天一小時新的 lofi。也在留言區分享一下你那邊今天的天氣吧。",
    "按讚和訂閱能讓更多人找到這個小房間。你今天在忙什麼呢？留言跟我們說。",
    "每天都有新的 lofi 歌單，訂閱就不會錯過明天的。留言分享你現在在做什麼吧！",
    "謝謝你在這裡待了一小時。按讚、訂閱，留言告訴我們你在哪裡聽：書桌前、沙發上，還是通勤的路上？",
    "想要更多這樣的慢時光，就訂閱吧。也告訴我們：今天喝咖啡還是喝茶？",
]

BASE_TAGS_ZH = ["lofi", "lofi 中文", "讀書音樂", "放鬆音樂", "專注音樂", "純音樂", "lofi 歌單", "一小時 lofi", "chill beats"]

LABELS = {
    "en": {"tracklist": "Tracklist", "photo": "Background photo"},
    "zh": {"tracklist": "曲目", "photo": "背景照片"},
}

# Added after each theme's own tags; YouTube allows about 500 characters in total.
BASE_TAGS = [
    "lofi", "lofi beats", "lofi hip hop", "chill beats", "instrumental lofi",
    "lofi no vocals", "study music", "relaxing music", "lofi playlist", "1 hour lofi",
]


def load():
    return json.loads(THEMES.read_text(encoding="utf-8"))


def load_pool():
    return json.loads(POOL.read_text(encoding="utf-8")) if POOL.exists() else []


def next_from_pool(pool, used_titles):
    """The first pool theme not used yet, or None when the pool has run out."""
    return next((t for t in pool if t["cover_title"] not in used_titles), None)


def pool_remaining(pool, used_titles):
    return sum(1 for t in pool if t["cover_title"] not in used_titles)


def localized(theme, lang):
    """The theme's text in one language. Chinese falls back to English for missing fields."""
    if lang == "en":
        return theme
    return {**theme, **theme.get("zh", {})}


def for_date(themes, today):
    return next((t for t in themes if t["date"] == today.isoformat()), None)


def remaining(themes, today):
    """How many themes are scheduled after today."""
    return sum(1 for t in themes if t["date"] > today.isoformat())


def call_to_action(today, lang="en"):
    return random.Random(today.toordinal()).choice(CALLS_TO_ACTION_ZH if lang == "zh" else CALLS_TO_ACTION)


def all_tags(theme, lang="en"):
    """The theme's own tags, then generic ones; Chinese videos also keep the English tags."""
    own = theme["tags"]
    if lang == "zh":
        own = theme.get("zh", {}).get("tags", []) + BASE_TAGS_ZH + theme["tags"]
    tags, length = [], 0
    for tag in own + BASE_TAGS:
        if tag.lower() in (t.lower() for t in tags) or length + len(tag) + 1 > 480:
            continue
        tags.append(tag)
        length += len(tag) + 1
    return tags


def fallback(today, evening=False):
    """Plain theme used when nothing is scheduled, so the video still ships."""
    when = "Evening" if evening else "Living Room"
    return {
        "cover_title": f"{when} Lofi",
        "cover_subtitle": f"a playlist for {today:%B %d}",
        "youtube_title": f"{when.lower()} lofi session • {today:%B %d, %Y} • 1 hour of chill beats",
        "description": (
            "Soft light in the living room, lofi beats on the speakers, and an hour with nowhere else to be.\n\n"
            "Instrumental lofi with no vocals for reading, working from home or a slow coffee break."
        ),
        "hashtags": ["#lofi", "#chillbeats", "#studymusic"],
        "tags": ["living room lofi"],
        "theme_note_zh": "（主題庫裡沒有可用的主題，使用備用的通用標題）",
        "zh": {
            "cover_title": "夜晚的 lofi" if evening else "客廳裡的 lofi",
            "cover_subtitle": f"{today.month} 月 {today.day} 日的歌單",
            "youtube_title": f"{'夜晚' if evening else '客廳'} lofi 時光 • {today:%Y/%m/%d} • 一小時放鬆純音樂",
            "description": "暖暖的燈光、喇叭裡的 lofi，還有一個小時哪裡都不用去。\n\n"
                           "一小時純音樂 lofi，沒有人聲，適合讀書、在家工作或慢慢喝杯咖啡。",
            "hashtags": ["#lofi", "#讀書音樂", "#放鬆音樂"],
            "tags": [],
        },
    }
