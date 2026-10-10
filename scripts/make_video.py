"""Build today's ~1 hour music video from a random selection of tracks.

Steps: pick 8-9 tracks -> crossfade them into one audio file -> draw the cover and
one "now playing" frame per track -> encode the video -> write the metadata to
data/history.json and the output folder. Titles and text come from data/themes.json.

Usage: python scripts/make_video.py
"""
import datetime
import json
import os
import random
import re
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import themes  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"
HISTORY = ROOT / "data" / "history.json"
AUDIO_EXT = {".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".opus"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
CJK_FONTS = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "C:/Windows/Fonts/msjh.ttc",
]
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
FFPROBE = os.environ.get("FFPROBE", "ffprobe")


def run(cmd):
    subprocess.run(cmd, check=True)


def duration(path):
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return float(out)


def pick_tracks(cfg, tracks):
    """Random tracks (count from config) whose crossfaded length lands closest to the target."""
    fade = cfg["crossfade_seconds"]
    target = cfg["target_minutes"] * 60
    lo = min(cfg["track_count_min"], len(tracks))
    hi = min(cfg["track_count_max"], len(tracks))
    best, best_gap = None, None
    for _ in range(5000):
        chosen = random.sample(tracks, random.randint(lo, hi))
        total = sum(d for _, d in chosen) - fade * (len(chosen) - 1)
        gap = abs(total - target)
        if best_gap is None or gap < best_gap:
            best, best_gap = chosen, gap
    return best


def display_name(path):
    return re.sub(r"[_]+", " ", path.stem).strip()


def font(name, size, variation=None):
    f = ImageFont.truetype(str(FONTS / name), size)
    if variation:
        f.set_variation_by_name(variation)
    return f


def text_font(text, size, latin_name, variation=None):
    """Latin text uses the serif font; anything else falls back to a CJK font."""
    if all(ord(c) < 0x2000 for c in text):
        return font(latin_name, size, variation)
    for path in CJK_FONTS:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return font(latin_name, size, variation)


def fit(text, size, max_width, make_font):
    while size > 20:
        f = make_font(size)
        if f.getlength(text) <= max_width:
            return f
        size -= 4
    return make_font(size)


def draw_shadowed(base, xy, text, fnt, fill, anchor, shadow_alpha=150, blur=6):
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text((xy[0] + 2, xy[1] + 3), text, font=fnt, fill=(0, 0, 0, shadow_alpha), anchor=anchor)
    base.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(blur)))
    ImageDraw.Draw(base).text(xy, text, font=fnt, fill=fill, anchor=anchor)


def pick_background(cfg, history):
    """The least recently used background, so every image appears once before any repeats."""
    images = sorted(p for p in (ROOT / cfg["backgrounds_dir"]).iterdir() if p.suffix.lower() in IMAGE_EXT)
    if not images:
        sys.exit(f"No images found in {cfg['backgrounds_dir']}")
    last_used = {h.get("background"): i for i, h in enumerate(history)}
    oldest = min(last_used.get(p.name, -1) for p in images)
    return random.choice([p for p in images if last_used.get(p.name, -1) == oldest])


def load_background(cfg, path):
    img = Image.open(path).convert("RGB")
    w, h = cfg["width"], cfg["height"]
    scale = max(w / img.width, h / img.height)
    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    left, top = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((left, top, left + w, top + h)).convert("RGBA")


def make_cover(bg, title, subtitle, out_path):
    w, h = bg.size
    img = bg.copy()
    # Soft dark glow in the centre so the text reads on the bright marble wall.
    glow = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).rounded_rectangle(
        (w * 0.17, h * 0.33, w * 0.83, h * 0.67), radius=60, fill=(20, 16, 12, 120)
    )
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(50)))

    title_font = fit(title, 170, w * 0.78, lambda s: font("CormorantGaramond.ttf", s, "SemiBold"))
    sub_font = fit(subtitle, 58, w * 0.7, lambda s: font("CormorantGaramond-Italic.ttf", s, "Medium Italic"))
    draw_shadowed(img, (w / 2, h * 0.47), title, title_font, (255, 248, 236, 255), "mm", 180, 10)
    line_y = h * 0.56
    ImageDraw.Draw(img).line((w / 2 - 70, line_y, w / 2 + 70, line_y), fill=(236, 214, 170, 230), width=2)
    draw_shadowed(img, (w / 2, h * 0.61), subtitle, sub_font, (245, 236, 220, 255), "mm", 160, 8)
    img.convert("RGB").save(out_path, quality=92)


def make_track_frame(bg, index, total, name, out_path):
    w, h = bg.size
    img = bg.copy()
    # Gentle dark gradient along the bottom for legibility.
    grad = Image.new("L", (1, h), 0)
    for y in range(h):
        t = max(0.0, (y - h * 0.62) / (h * 0.38))
        grad.putpixel((0, y), int(170 * t ** 1.6))
    shade = Image.new("RGBA", bg.size, (10, 8, 6, 255))
    shade.putalpha(grad.resize(bg.size))
    img.alpha_composite(shade)

    x = int(w * 0.045)
    label_font = font("CormorantGaramond-Italic.ttf", 40, "Medium Italic")
    name_font = fit(name, 64, w * 0.9, lambda s: text_font(name, s, "PlayfairDisplay.ttf", "Regular"))
    draw_shadowed(img, (x, h - 150), f"now playing  \u00b7  {index:02d} / {total:02d}", label_font,
                  (236, 214, 170, 255), "ls", 160, 5)
    draw_shadowed(img, (x, h - 72), name, name_font, (255, 250, 242, 255), "ls", 170, 6)
    img.convert("RGB").save(out_path, quality=92)


def build_audio(cfg, chosen, out_path):
    fade = cfg["crossfade_seconds"]
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error"]
    for path, _ in chosen:
        cmd += ["-i", str(path)]
    parts = [f"[{i}:a]aformat=sample_rates=44100:channel_layouts=stereo[a{i}]" for i in range(len(chosen))]
    prev = "a0"
    for i in range(1, len(chosen)):
        out = "aout" if i == len(chosen) - 1 else f"x{i}"
        parts.append(f"[{prev}][a{i}]acrossfade=d={fade}:c1=tri:c2=tri[{out}]")
        prev = out
    if len(chosen) == 1:
        parts[0] = parts[0].replace("[a0]", "[aout]")
    cmd += ["-filter_complex", ";".join(parts), "-map", "[aout]", "-c:a", "aac", "-b:a", "192k", str(out_path)]
    run(cmd)


def timestamp(seconds):
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def slug(text):
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-") or "video"


def main():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    today = datetime.datetime.now(ZoneInfo(cfg["timezone"])).date()
    music_dir = ROOT / cfg["music_dir"]
    out_dir = ROOT / cfg["output_dir"]
    work = out_dir / "work"
    work.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in music_dir.rglob("*") if p.suffix.lower() in AUDIO_EXT)
    if not files:
        sys.exit(f"No audio files found in {music_dir}")
    fade = cfg["crossfade_seconds"]
    tracks = [(p, d) for p in files if (d := duration(p)) > fade * 3]
    chosen = pick_tracks(cfg, tracks)

    # Each track starts `fade` seconds before the previous one ends; the on-screen
    # title switches halfway through the crossfade.
    starts, t = [], 0.0
    for _, d in chosen:
        starts.append(t)
        t += d - fade
    total = t + fade
    switches = [0.0] + [s + fade / 2 for s in starts[1:]]
    names = [display_name(p) for p, _ in chosen]
    print(f"{len(chosen)} tracks, {total / 60:.1f} min")

    history = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else []
    all_themes = themes.load()
    meta = themes.for_date(all_themes, today)
    scheduled = meta is not None
    if not scheduled:
        print(f"No theme scheduled for {today}, using fallback")
        meta = themes.fallback(today)
    background = ROOT / cfg["backgrounds_dir"] / meta.get("background", "")
    if not background.is_file():
        background = pick_background(cfg, history)
    print(f"Theme: {meta['cover_title']} | {meta['youtube_title']}")
    print(f"Background: {background.name}")

    base = f"{today:%Y-%m-%d}_{slug(meta['cover_title'])}"
    bg = load_background(cfg, background)
    cover = out_dir / f"{base}_cover.jpg"
    make_cover(bg, meta["cover_title"], meta["cover_subtitle"], cover)

    frames = []
    for i, name in enumerate(names):
        frame = work / f"track_{i:02d}.jpg"
        make_track_frame(bg, i + 1, len(names), name, frame)
        frames.append(frame)

    # Image sequence for the concat demuxer: cover first, then one frame per track.
    cover_s = cfg["cover_seconds"]
    segments = [(cover, cover_s)]
    for i, frame in enumerate(frames):
        start = max(switches[i], cover_s)
        end = switches[i + 1] if i + 1 < len(frames) else total
        segments.append((frame, end - start))
    concat = work / "frames.txt"
    concat.write_text(
        "".join(f"file '{p.as_posix()}'\nduration {d:.3f}\n" for p, d in segments)
        + f"file '{segments[-1][0].as_posix()}'\n",
        encoding="utf-8",
    )

    audio = work / "audio.m4a"
    build_audio(cfg, chosen, audio)

    video = out_dir / f"{base}.mp4"
    run([
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-stats",
        "-f", "concat", "-safe", "0", "-i", str(concat), "-i", str(audio),
        "-map", "0:v", "-map", "1:a",
        "-vf", f"fps={cfg['fps']},format=yuv420p",
        "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-crf", "22",
        "-c:a", "copy", "-shortest", "-movflags", "+faststart", str(video),
    ])

    chapters = "\n".join(f"{timestamp(s)} {n}" for s, n in zip(switches, names))
    description = (
        f"{meta['description'].strip()}\n\n{themes.call_to_action(today)}\n\n"
        f"Tracklist\n{chapters}\n\n{' '.join(meta['hashtags'])}"
    )
    tags = themes.all_tags(meta)
    (out_dir / f"{base}_description.txt").write_text(
        f"TITLE\n{meta['youtube_title']}\n\nDESCRIPTION\n{description}\n\nTAGS\n{', '.join(tags)}\n",
        encoding="utf-8",
    )

    history.append({
        **meta,
        "date": today.isoformat(),
        "description": description,
        "tags": tags,
        "tracks": names,
        "background": background.name,
        "duration_seconds": round(total),
        "files": [video.name, cover.name, f"{base}_description.txt"],
        "scheduled_theme": scheduled,
        "themes_remaining": themes.remaining(all_themes, today),
    })
    HISTORY.parent.mkdir(exist_ok=True)
    HISTORY.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Done: {video}")


if __name__ == "__main__":
    main()
