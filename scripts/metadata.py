"""Ask Claude for today's theme, cover text, YouTube title and description."""
import base64
import io
import json

import anthropic
from PIL import Image

SYSTEM_PROMPT = """You are the creative director of a YouTube channel that uploads one music playlist of about an hour every day. Each video shows a single still picture of a living room with speakers; today's picture is attached.

Your job is to invent today's theme and write its packaging. Write everything in English except theme_note_zh.

What works on YouTube music and ambience channels in 2026 (from a study of about 2,300 top videos):
- One specific moment and feeling beats a generic genre. Generic "cafe background music" is saturated; the specific version is where smaller channels break out.
- Title formula: a specific moment or place + a month, season or time of day + the weather or light + one detail you can almost hear + what the music is for. Under fifteen words.
- Lowercase, feeling-first titles are rising (for example: "it's raining outside and the record is still spinning").
- Seasons drive the biggest views. Sell the mood (harvest, first frost, candlelit, fresh start, slow spring rain) rather than the holiday's name, and lean into the next seasonal moment 4-8 weeks ahead.
- Rising moods: vintage and lounge, "oldies playing in another room", focus and work-from-home sessions, quiet luxury, slow mornings, gentle nostalgia.
- Leave out: names of films, games, franchises or real artists; claims like "no AI" or "human-made"; medical promises (describe how the music feels, not what it treats); repeating the place, weather and mood of recent videos.

Build today's theme from the attached picture: a moment that could happen in that room, matching its light, time of day and mood, plus the season, the weather outside and what the listener is doing (reading, a slow coffee, working from home, a rainy Sunday, a quiet dinner, tidying up, a nap). Do not describe anything the picture contradicts (for example a fireplace or snow when none is shown). Weather outside is fine when no window view is visible.

Describe the music only as: {music_style}. Do not name instruments or genres beyond that description. The track names are a hint about the mood.

Fields:
- cover_title: 2-4 words in Title Case, printed large in the middle of the thumbnail. Soft and evocative, e.g. "Late Autumn Vinyl", "Slow Sunday Light". It must not repeat or closely echo any past cover title.
- cover_subtitle: 3-7 lowercase words printed under it, e.g. "a living room playlist for slow afternoons".
- youtube_title: 55-95 characters following the formula. At most one emoji, used as a separator. It must clearly differ from every past title.
- description: three short paragraphs separated by blank lines. The first 150 characters appear in search results, so open with an inviting line that puts the viewer in the room. Then when to play it. Then a gentle invitation to like, subscribe and say in the comments what they are doing while listening. No timestamps and no hashtags (both are added automatically).
- hashtags: exactly 3, each starting with #, no spaces.
- tags: 12-20 search tags people would actually type.
- theme_note_zh: one sentence in Traditional Chinese explaining today's concept to the channel owner."""

SCHEMA = {
    "type": "object",
    "properties": {
        "cover_title": {"type": "string"},
        "cover_subtitle": {"type": "string"},
        "youtube_title": {"type": "string"},
        "description": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "tags": {"type": "array", "items": {"type": "string"}},
        "theme_note_zh": {"type": "string"},
    },
    "required": [
        "cover_title", "cover_subtitle", "youtube_title", "description",
        "hashtags", "tags", "theme_note_zh",
    ],
    "additionalProperties": False,
}

SEASONS = {
    12: "early winter", 1: "midwinter", 2: "late winter",
    3: "early spring", 4: "spring", 5: "late spring",
    6: "early summer", 7: "midsummer", 8: "late summer",
    9: "early autumn", 10: "autumn", 11: "late autumn",
}


def image_block(path):
    """The background as a small JPEG content block, enough for Claude to read the scene."""
    img = Image.open(path).convert("RGB")
    img.thumbnail((1280, 1280))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    data = base64.standard_b64encode(buf.getvalue()).decode()
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}}


def generate(cfg, today, track_names, history, background):
    """Return a metadata dict whose cover_title and youtube_title are not in history."""
    client = anthropic.Anthropic()
    recent = history[-cfg["history_for_prompt"]:]
    used = {h["cover_title"].lower() for h in history} | {h["youtube_title"].lower() for h in history}

    user = (
        f"Today is {today:%A, %B %d, %Y} ({SEASONS[today.month]} in the northern hemisphere).\n\n"
        "Past cover titles and video titles, most recent last (do not repeat them):\n"
        + ("\n".join(f"- {h['cover_title']} | {h['youtube_title']}" for h in recent) or "- (none yet)")
        + "\n\nToday's tracks, in play order:\n"
        + "\n".join(f"- {n}" for n in track_names)
    )
    messages = [{"role": "user", "content": [image_block(background), {"type": "text", "text": user}]}]

    for _ in range(3):
        response = client.beta.messages.create(
            model=cfg["model"],
            max_tokens=16000,
            system=SYSTEM_PROMPT.replace("{music_style}", cfg["music_style"]),
            messages=messages,
            output_config={
                "effort": "medium",
                "format": {"type": "json_schema", "schema": SCHEMA},
            },
            betas=["server-side-fallback-2026-07-01"],
            extra_body={"fallbacks": "default"},
        )
        if response.stop_reason == "refusal":
            raise RuntimeError(f"Claude declined the request: {response.stop_details}")
        if response.stop_reason == "max_tokens":
            raise RuntimeError("Claude's answer was cut off (max_tokens)")
        text = next(b.text for b in response.content if b.type == "text")
        data = json.loads(text)
        if data["cover_title"].lower() not in used and data["youtube_title"].lower() not in used:
            return data
        messages += [
            {"role": "assistant", "content": response.content},
            {"role": "user", "content": "That title was already used on an earlier video. Write a completely different theme."},
        ]
    raise RuntimeError("Could not get a unique title after 3 attempts")


def fallback(today):
    """Plain metadata used when the API is unavailable, so the video still ships."""
    return {
        "cover_title": "Living Room Vinyl",
        "cover_subtitle": f"a playlist for {today:%B %d}",
        "youtube_title": f"Living Room Vinyl Session • {today:%B %d, %Y} • 1 Hour Relaxing Playlist",
        "description": (
            "Soft light in the living room, lofi beats on the speakers, and an hour with nowhere else to be.\n\n"
            "Play it while you read, work from home or take a slow coffee break.\n\n"
            "If this hour kept you company, leave a like, subscribe, and tell us what you're doing while you listen."
        ),
        "hashtags": ["#relaxingmusic", "#vinyl", "#playlist"],
        "tags": ["relaxing music", "living room playlist", "vinyl music", "1 hour music", "background music"],
        "theme_note_zh": "（AI 產生失敗，這是備用的通用標題）",
    }
