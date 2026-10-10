"""Draw the channel logo (800x800 + 2400x2400) and banner (2560x1440) for Hearth & Hi-Fi."""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"
OUT = Path(__file__).resolve().parent

NAME = "Hearth & Hi-Fi"
TAGLINE = "a new hour of cozy lofi, every day"

ESPRESSO = (34, 24, 19)
AMBER = (214, 150, 74)
HONEY = (240, 196, 128)
CREAM = (246, 236, 220)


def font(name, size, variation=None):
    f = ImageFont.truetype(str(FONTS / name), size)
    if variation:
        f.set_variation_by_name(variation)
    return f


def radial_glow(size, center, radius, color, strength):
    """A soft round glow on a transparent layer."""
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    steps = 60
    for i in range(steps):
        r = radius * (1 - i / steps)
        a = int(strength * (i / steps) ** 2)
        d.ellipse([center[0] - r, center[1] - r, center[0] + r, center[1] + r], fill=(*color, a))
    return layer.filter(ImageFilter.GaussianBlur(radius / 12))


def logo(size=2400):
    s = size
    img = Image.new("RGBA", (s, s), (*ESPRESSO, 255))
    img.alpha_composite(radial_glow((s, s), (s / 2, s / 2), s * 0.62, AMBER, 120))
    d = ImageDraw.Draw(img)
    c = s / 2

    # Vinyl record with grooves.
    rec = s * 0.36
    d.ellipse([c - rec, c - rec, c + rec, c + rec], fill=(16, 12, 10))
    for i in range(14):
        r = rec * (0.96 - i * 0.04)
        shade = 34 if i % 2 else 26
        d.ellipse([c - r, c - r, c + r, c + r], outline=(shade, shade - 4, shade - 6), width=max(2, s // 600))
    # Warm sheen across the grooves.
    sheen = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(sheen).pieslice([c - rec, c - rec, c + rec, c + rec], 205, 245, fill=(*HONEY, 40))
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).ellipse([c - rec, c - rec, c + rec, c + rec], fill=255)
    sheen = sheen.filter(ImageFilter.GaussianBlur(s / 18))
    sheen.putalpha(Image.composite(sheen.getchannel("A"), Image.new("L", (s, s), 0), mask))
    img.alpha_composite(sheen)
    d = ImageDraw.Draw(img)

    # Amber label with the ampersand.
    lab = rec * 0.44
    d.ellipse([c - lab, c - lab, c + lab, c + lab], fill=AMBER)
    d.ellipse([c - lab * 0.93, c - lab * 0.93, c + lab * 0.93, c + lab * 0.93], outline=HONEY, width=max(3, s // 400))
    amp = font("CormorantGaramond-Italic.ttf", int(s * 0.26), "SemiBold Italic")
    d.text((c, c + s * 0.012), "&", font=amp, fill=ESPRESSO, anchor="mm")
    hole = s * 0.012
    d.ellipse([c - hole, c - hole, c + hole, c + hole], fill=ESPRESSO)

    # Thin outer ring so the circle crop looks finished.
    ring = s * 0.455
    d.ellipse([c - ring, c - ring, c + ring, c + ring], outline=(*HONEY, 180), width=max(4, s // 300))
    return img.convert("RGB")


def banner(bg_path):
    W, H = 2560, 1440
    bg = Image.open(bg_path).convert("RGB")
    scale = max(W / bg.width, H / bg.height)
    bg = bg.resize((math.ceil(bg.width * scale), math.ceil(bg.height * scale)), Image.LANCZOS)
    left, top = (bg.width - W) // 2, (bg.height - H) // 2
    bg = bg.crop((left, top, left + W, top + H)).filter(ImageFilter.GaussianBlur(6))
    img = bg.convert("RGBA")
    img.alpha_composite(Image.new("RGBA", (W, H), (*ESPRESSO, 150)))

    # Darker band behind the text, inside YouTube's 1546x423 safe area.
    band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(band).rounded_rectangle([W / 2 - 900, H / 2 - 260, W / 2 + 900, H / 2 + 260], 260, fill=(*ESPRESSO, 140))
    img.alpha_composite(band.filter(ImageFilter.GaussianBlur(90)))
    img.alpha_composite(radial_glow((W, H), (W / 2, H / 2), 700, AMBER, 60))
    d = ImageDraw.Draw(img)

    title = font("CormorantGaramond.ttf", 190, "SemiBold")
    sub = font("CormorantGaramond-Italic.ttf", 64, "Medium Italic")
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text((W / 2, H / 2 - 50), NAME, font=title, fill=(0, 0, 0, 200), anchor="mm")
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)))
    d = ImageDraw.Draw(img)
    d.text((W / 2, H / 2 - 50), NAME, font=title, fill=CREAM, anchor="mm")
    d.line([W / 2 - 110, H / 2 + 62, W / 2 + 110, H / 2 + 62], fill=HONEY, width=3)
    d.text((W / 2, H / 2 + 128), TAGLINE, font=sub, fill=HONEY, anchor="mm")
    return img.convert("RGB")


if __name__ == "__main__":
    big = logo(2400)
    big.save(OUT / "logo-2400.png")
    big.resize((800, 800), Image.LANCZOS).save(OUT / "logo-800.png")
    banner(ROOT / "assets" / "backgrounds" / "living-room-04.png").save(OUT / "banner-2560x1440.jpg", quality=92)
    print("done")
