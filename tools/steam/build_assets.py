"""Steam store images at Valve's exact sizes, from the pet stills in site/img. Output: tools/steam/assets/."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
IMG = ROOT / "site" / "img"
OUT = Path(__file__).resolve().parent / "assets"; OUT.mkdir(exist_ok=True)
PURPLE, CREAM, INK = (90, 63, 192), (255, 248, 240), (35, 33, 59)
PETS = ["antenna", "ears", "leaf", "horns"]


def font(size, bold=True):
    for name in (["seguisb.ttf", "segoeuib.ttf"] if bold else ["segoeui.ttf"]):
        p = Path("C:/Windows/Fonts") / name
        if p.exists(): return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def pets_row(width, height, px, hats=False, y=None):
    """The four pets in a row on a see-through layer."""
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gap = px * 0.74
    x0 = width / 2 - gap * 1.5
    for i, pid in enumerate(PETS):
        im = Image.open(IMG / (f"{pid}-hat.png" if hats else f"{pid}.png")).convert("RGBA").resize((px, px), Image.LANCZOS)
        layer.alpha_composite(im, (round(x0 + i * gap - px / 2), round((height - px) / 2 if y is None else y)))
    return layer


def wordmark(size):
    return font(size)


def capsule(w, h, title=True, tagline=True, hats=False):
    im = Image.new("RGBA", (w, h), PURPLE + (255,))
    d = ImageDraw.Draw(im)
    for i in range(0, w, max(8, w // 40)):                  # a faint stripe texture so it isn't a flat slab
        d.line([(i, 0), (i + h, h)], fill=(102, 76, 206, 255), width=max(1, w // 400))
    px = round(h * (0.56 if title else 0.78))
    im.alpha_composite(pets_row(w, h, px, hats=hats, y=round(h * (0.3 if title else 0.1))))
    if title:
        f = wordmark(round(h * 0.2)); tw = f.getlength("Perchlings")
        d.text(((w - tw) / 2, h * 0.05), "Perchlings", font=f, fill=CREAM + (255,))
    if tagline and w >= 600:
        f2 = font(round(h * 0.06), bold=False); line = "Little pets with big personalities, on your taskbar. First one free."
        d.text(((w - f2.getlength(line)) / 2, h * 0.9), line, font=f2, fill=(230, 222, 255, 255))
    return im.convert("RGB")


capsule(920, 430, hats=True).save(OUT / "header_capsule_920x430.png")
capsule(460, 215, hats=True).save(OUT / "small_capsule_460x215.png")
capsule(231, 87, title=False, tagline=False, hats=True).save(OUT / "small_capsule_231x87.png")
capsule(1232, 706, hats=True).save(OUT / "main_capsule_1232x706.png")
# vertical and library capsules: the pets stacked two by two under the name
for name, (w, h) in (("vertical_capsule_748x896", (748, 896)), ("library_capsule_600x900", (600, 900))):
    im = Image.new("RGBA", (w, h), PURPLE + (255,)); d = ImageDraw.Draw(im)
    f = wordmark(round(w * 0.16)); tw = f.getlength("Perchlings"); d.text(((w - tw) / 2, h * 0.06), "Perchlings", font=f, fill=CREAM + (255,))
    px = round(w * 0.42)
    for i, pid in enumerate(PETS):
        p = Image.open(IMG / f"{pid}-hat.png").convert("RGBA").resize((px, px), Image.LANCZOS)
        im.alpha_composite(p, (round(w * 0.06 + (i % 2) * w * 0.46), round(h * 0.24 + (i // 2) * h * 0.36)))
    im.convert("RGB").save(OUT / f"{name}.png")
# library hero and logo
hero = Image.new("RGBA", (3840, 1240), PURPLE + (255,)); hero.alpha_composite(pets_row(3840, 1240, 900, hats=True)); hero.convert("RGB").save(OUT / "library_hero_3840x1240.png")
logo = Image.new("RGBA", (1280, 720), (0, 0, 0, 0)); d = ImageDraw.Draw(logo); f = wordmark(200); tw = f.getlength("Perchlings")
d.text(((1280 - tw) / 2, 230), "Perchlings", font=f, fill=CREAM + (255,), stroke_width=8, stroke_fill=INK + (255,)); logo.save(OUT / "library_logo_1280x720.png")
print("wrote", len(list(OUT.glob("*.png"))), "images to", OUT)
