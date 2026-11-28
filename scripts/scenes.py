"""The only kinds of picture allowed behind a cover, and the cover keywords.

Every background must show one of these scenes: café, scenic spot, street,
landscape, city landmark, records, hi-fi / speakers, or reading. A theme is
matched to the scene its English text points at (e.g. "coffee" -> café); themes
that point at none get one picked by date, so all eight keep coming up.

Each scene lists its own search queries (the theme's title is never searched on
its own any more, which is how rockets, letters and satellite photos got in) and
the words a photo's file name or title must contain to count as that scene.
"""
import random
import re

SCENES = {
    "cafe": {
        "zh": "咖啡廳",
        "queries": ["cafe interior", "coffee shop interior", "cafe window", "coffee cup cafe table", "cafe terrace"],
        "words": ["cafe", "café", "caffe", "coffee", "coffeehouse", "espresso", "latte", "cappuccino", "barista", "kaffee", "cafeteria"],
        "triggers": ["cafe", "café", "coffee", "latte", "espresso", "barista", "roastery", "bakery", "breakfast", "tea house", "teahouse", "afternoon tea"],
    },
    "landmark": {
        "zh": "景點",
        "queries": ["lighthouse coast", "old town square", "temple garden", "castle lake", "stone bridge river", "japanese garden"],
        "words": ["lighthouse", "castle", "temple", "shrine", "pagoda", "palace", "cathedral", "old town", "altstadt", "bridge", "garden", "monastery", "harbour", "harbor", "pier", "fortress"],
        "triggers": ["lighthouse", "temple", "garden", "castle", "shrine", "harbor", "harbour", "hot spring", "old town", "bridge", "pier"],
    },
    "street": {
        "zh": "街景",
        "queries": ["city street night", "rainy street", "narrow alley", "street at dusk", "old street shops", "street lanterns"],
        "words": ["street", "alley", "avenue", "lane", "sidewalk", "road", "crosswalk", "boulevard", "strasse", "straße", "rue", "calle", "gasse"],
        "triggers": ["street", "alley", "avenue", "lane", "brick", "lantern", "eaves", "umbrella", "convenience store", "commute", "sidewalk", "fire escape"],
    },
    "scenery": {
        "zh": "風景",
        "queries": ["mountain lake landscape", "sunset beach", "forest path", "snowy mountains", "countryside fields", "autumn forest", "sea of clouds mountain"],
        "words": ["landscape", "mountain", "mountains", "lake", "beach", "forest", "valley", "sunset", "sunrise", "river", "coast", "meadow", "hills", "waterfall", "fjord", "field", "fields", "shore", "seascape", "woods", "peak", "alps", "snow"],
        "triggers": ["lake", "mountain", "peak", "forest", "sea", "beach", "shore", "valley", "meadow", "cloud", "clouds", "snowfall", "fog", "maple", "ginkgo", "bamboo", "sunset", "dawn", "cabin", "countryside", "train window"],
    },
    "city": {
        "zh": "城市景點",
        "queries": ["city skyline night", "city skyline sunset", "cityscape", "downtown skyline", "city lights night"],
        "words": ["skyline", "cityscape", "city", "downtown", "skyscraper", "skyscrapers", "tower", "panorama", "metropolis", "urban"],
        "triggers": ["city", "skyline", "rooftop", "downtown", "tower", "new year's eve", "lights up", "above the city"],
    },
    "vinyl": {
        "zh": "唱片",
        "queries": ["vinyl record", "record player turntable", "vinyl records shop", "turntable vinyl", "record store"],
        "words": ["vinyl", "record", "records", "turntable", "gramophone", "phonograph", "lp", "platenspeler", "schallplatte"],
        "triggers": ["record", "records", "vinyl", "turntable", "lp"],
    },
    "audio": {
        "zh": "音響",
        "queries": ["hi-fi speakers", "stereo amplifier", "vintage loudspeaker", "cassette deck", "hifi audio system", "headphones"],
        "words": ["speaker", "speakers", "loudspeaker", "loudspeakers", "stereo", "amplifier", "hifi", "hi-fi", "audio", "headphones", "cassette", "radio", "receiver", "jukebox"],
        "triggers": ["speaker", "speakers", "stereo", "hi-fi", "hifi", "radio", "cassette", "headphones", "jukebox", "piano"],
    },
    "reading": {
        "zh": "讀書",
        "queries": ["reading book", "library reading room", "books on table", "bookshop interior", "open book coffee", "bookshelf"],
        "words": ["book", "books", "reading", "library", "bookshop", "bookstore", "bookcase", "bookshelf", "reader", "biblioth", "novel"],
        "triggers": ["book", "books", "reading", "library", "bookshop", "study", "studying", "desk", "page", "pages", "journal", "exam", "homework", "notebook"],
    },
}

# Photos whose name says they are documents, artwork, space or military shots are never
# backgrounds, whatever scene word they also contain.
BLOCKED = [
    "letter", "letters", "page", "manuscript", "map", "diagram", "chart", "poster", "logo", "drawing",
    "engraving", "lithograph", "illustration", "painting", "sketch", "stamp", "postcard", "newspaper",
    "document", "catalog", "scan", "scanned", "satellite", "nasa", "noaa", "rocket", "launch", "air force",
    "army", "navy", "military", "dpla", "met", "tomb", "cemetery", "grave", "accident", "rockslide",
    "crash", "protest", "screenshot", "tv series", "film", "dwarfs", "portrait", "x-ray", "microscope",
    "patent", "blueprint", "orbiter", "spacecraft", "astronaut",
]

# Weather / time words that are added in front of a scene's queries when the theme has them.
MODIFIERS = ["rain", "rainy", "snow", "snowy", "night", "autumn", "winter", "christmas", "sunset", "fog", "foggy", "morning"]


def theme_text(theme):
    # Titles count twice: tags are generic and say less about the picture.
    titles = [theme.get(k, "") for k in ("cover_title", "cover_subtitle", "youtube_title")]
    parts = titles + titles + [theme.get("image_query", "")] + list(theme.get("tags", []))
    return " | ".join(p for p in parts if p).lower()


def _hits(text, words):
    return sum(len(re.findall(r"(?<!\w)" + re.escape(w.lower()) + r"(?!\w)", text)) for w in words)


def scene_for(theme, seed):
    """The best-matching scene for the theme, or one picked by seed when nothing matches."""
    text = theme_text(theme)
    scored = sorted(((_hits(text, s["triggers"]), i, key) for i, (key, s) in enumerate(SCENES.items())),
                    key=lambda s: (-s[0], s[1]))
    if scored[0][0] > 0:
        return scored[0][2]
    return random.Random(seed).choice(list(SCENES))


def queries(theme, scene):
    """The scene's queries, first with the theme's weather/time words in front of them."""
    text = theme_text(theme)
    mods = [m for m in MODIFIERS if re.search(r"(?<!\w)" + m + r"(?!\w)", text)][:2]
    base = SCENES[scene]["queries"]
    # "morning city skyline night" helps nobody: only add a word to queries without one.
    plain = [q for q in base if not any(re.search(r"\b" + m + r"\b", q) for m in MODIFIERS)]
    return [f"{m} {q}" for m in mods for q in plain[:3]] + base


def _name(title):
    return " " + re.sub(r"[_\-]+", " ", (title or "").lower()) + " "


def blocked(title):
    return bool(_hits(_name(title), BLOCKED) or re.search(r"\biss\d", _name(title)))


def matches(title, scene):
    """True when a photo's file name / title says it shows the scene and isn't a blocked kind."""
    name = _name(title)
    if blocked(title):
        return False
    return _hits(name, [w.strip() for w in SCENES[scene]["words"]]) > 0


# Big, searchable words for the Chinese cover. The first match becomes the
# highlighted hook ("聖誕 lofi"); the rest are the usual reasons people search.
HOOKS_ZH = [
    (["christmas", "holiday", "gingerbread", "ornament", "ornaments", "christmas eve"], "聖誕"),
    (["new year's eve", "last night of the year"], "跨年"),
    (["new year"], "新年"),
    (["rain", "rainy", "drizzle", "storm", "umbrella"], "雨天"),
    (["snow", "snowy", "snowfall", "snowed"], "下雪天"),
]
# Used only when the scene itself is no strong search word (see cover_keywords_zh).
HOOKS_ZH_LATER = [
    (["midnight", "late night", "night", "2am", "moon", "moonlit"], "深夜"),
    (["winter", "december", "january", "frozen", "cold"], "冬日"),
    (["autumn", "october", "november", "maple", "ginkgo", "pumpkin"], "秋日"),
    (["morning", "mornings", "sunrise", "dawn", "breakfast"], "早晨"),
]
SCENE_HOOK_ZH = {
    "cafe": "咖啡廳", "landmark": "旅行", "street": "街角", "scenery": "放空",
    "city": "城市夜景", "vinyl": "黑膠", "audio": "Hi-Fi", "reading": "讀書",
}
STUDY_WORDS = ["study", "studying", "focus", "exam", "deep work", "lock in"]
USES_ZH = ["讀書", "工作", "放鬆", "專注"]


def cover_keywords_zh(theme, scene):
    """(hook, uses): e.g. ("聖誕 lofi", ["讀書", "放鬆", "專注"])."""
    text = theme_text(theme)
    hook = next((zh for words, zh in HOOKS_ZH if _hits(text, words)), None)
    # A scene word only counts when the theme itself is about that scene (not picked by date).
    own_scene = _hits(text, SCENES[scene]["triggers"]) > 0
    if not hook and own_scene and scene in ("cafe", "vinyl", "reading"):
        hook = SCENE_HOOK_ZH[scene]
    if not hook:
        hook = next((zh for words, zh in HOOKS_ZH_LATER if _hits(text, words)), None)
    if not hook and own_scene and scene in ("city", "street"):
        hook = SCENE_HOOK_ZH[scene]
    if not hook and _hits(text, STUDY_WORDS):
        hook = "讀書"
    hook = hook or (SCENE_HOOK_ZH[scene] if own_scene else "放鬆")
    uses = [u for u in USES_ZH if u != hook][:3]
    return f"{hook} lofi", uses


# A/B test on the Chinese cover: "keywords" (hook pill + uses) vs "sentence" (one full,
# spoken-style line). Videos alternate between the two; history.json records which one.
SENTENCES_ZH = {
    "聖誕": ["聖誕夜，就讓這些歌陪你", "一放就有聖誕節的感覺"],
    "跨年": ["一年的最後，留一小時給自己"],
    "新年": ["新的一年，從一小時的安靜開始"],
    "雨天": ["下雨天最適合聽的一小時", "聽著雨聲，心就靜下來了"],
    "下雪天": ["外面下雪，屋裡只剩這些歌"],
    "深夜": ["睡不著的時候，聽這個就對了", "深夜一個人，剛好需要這些歌"],
    "咖啡廳": ["像坐在咖啡廳裡一樣放鬆", "一杯咖啡的時間，什麼都不用想"],
    "黑膠": ["老唱片的聲音，真的很療癒"],
    "讀書": ["讀書時放這個，真的比較專心", "一小時，專心把事情做完"],
    "早晨": ["早上放這個，一整天心情都好"],
}
SENTENCES_ZH_ANY = [
    "聽了真的會放鬆的音樂",
    "一按下播放，心就靜下來了",
    "工作讀書都適合，一小時不打擾",
    "累了嗎？聽一小時再說",
    "今天辛苦了，聽點溫柔的音樂吧",
]
ZH_COVER_VARIANTS = ("keywords", "sentence")


def zh_cover_variant(today, slot):
    """Alternate the variants so each publish slot (am / pm) gets both over two days."""
    return ZH_COVER_VARIANTS[(today.toordinal() + slot) % 2]


def cover_sentence_zh(theme, scene, seed):
    """One full sentence for the "sentence" cover, matching the theme when one fits."""
    hook = cover_keywords_zh(theme, scene)[0].removesuffix(" lofi")
    options = SENTENCES_ZH.get(hook, []) + SENTENCES_ZH_ANY
    return random.Random(seed).choice(options)
