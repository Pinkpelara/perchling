"""Eggs, hatchlings and colours.

A pet that gets played with finds an egg. The egg hatches a day later into a new pet, one of the four kinds,
in a colour rolled from the table below. The odds are printed here and in the app; nothing about it costs
money and nothing is random about the price. Colours are applied to the pet's own frames on the fly
(a hue shift, a saturation and a lightness change), so every outfit still fits.
"""
import json, random, time
from datetime import datetime
from PIL import Image, ImageDraw

# the four kinds, and the hue their body colour sits at (degrees), so a target colour can be reached from any of them
BASE_HUE = {"antenna": 172, "ears": 347, "leaf": 112, "horns": 30}
LABEL = {"antenna": "Teal", "ears": "Pink", "leaf": "Green", "horns": "Gold"}

# tier -> (odds in percent, [(colour name, hue or None for the natural colour, sat, light)])
TABLE = {
    "common":    (60, [("Natural", None, 1.0, 1.0)]),
    "uncommon":  (30, [("Lilac", 270, 1.0, 1.02), ("Mint", 150, 0.95, 1.06), ("Peach", 22, 1.0, 1.05), ("Sky", 205, 1.0, 1.04)]),
    "rare":      (9,  [("Midnight", 240, 1.1, 0.62), ("Sunset", 8, 1.25, 1.0), ("Snow", None, 0.18, 1.22)]),
    "legendary": (1,  [("Golden", 46, 1.35, 1.12)]),
}
GOOD_DAY_TOUCHES = 3      # a day counts toward an egg when the pet was touched at least this often
GOOD_DAYS_FOR_EGG = 7
HATCH_HOURS = 24
MAX_PETS = 6


def roll(rnd=None):
    rnd = rnd or random.Random()
    r = rnd.uniform(0, 100); acc = 0
    for tier, (odds, colours) in TABLE.items():
        acc += odds
        if r <= acc:
            name, hue, sat, light = rnd.choice(colours)
            return {"tier": tier, "name": name, "hue": hue, "sat": sat, "light": light}
    name, hue, sat, light = TABLE["common"][1][0]
    return {"tier": "common", "name": name, "hue": hue, "sat": sat, "light": light}


def odds_text():
    return ", ".join(f"{tier} {odds}%" for tier, (odds, _) in TABLE.items())


def recolor(im, species, variant):
    """Shift a frame's colours toward the variant. Eyes and whites barely move; the body takes the new hue."""
    if not variant or (variant.get("hue") is None and variant.get("sat", 1) == 1 and variant.get("light", 1) == 1):
        return im
    alpha = im.getchannel("A")
    hsv = im.convert("RGB").convert("HSV")
    h, s, v = hsv.split()
    if variant.get("hue") is not None:
        shift = int(round(((variant["hue"] - BASE_HUE.get(species, 0)) % 360) / 360 * 255))
        h = h.point(lambda x, sh=shift: (x + sh) % 256)
    if variant.get("sat", 1) != 1:
        s = s.point(lambda x, k=variant["sat"]: max(0, min(255, int(x * k))))
    if variant.get("light", 1) != 1:
        v = v.point(lambda x, k=variant["light"]: max(0, min(255, int(x * k))))
    out = Image.merge("HSV", (h, s, v)).convert("RGBA")
    out.putalpha(alpha)
    return out


def egg_image(px, seed=0):
    """A pale egg with pastel spots, see-through around it."""
    rnd = random.Random(seed)
    im = Image.new("RGBA", (px, px), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    w, h = px * 0.62, px * 0.82
    x0, y0 = (px - w) / 2, (px - h) / 2 + px * 0.05
    d.ellipse((x0, y0, x0 + w, y0 + h), fill=(255, 246, 228, 255), outline=(230, 210, 180, 255), width=max(1, px // 60))
    cols = [(245, 142, 166), (196, 176, 255), (47, 179, 163), (255, 209, 102), (88, 166, 78)]
    for _ in range(7):
        cx, cy = x0 + w * rnd.uniform(0.25, 0.75), y0 + h * rnd.uniform(0.2, 0.8); r = px * rnd.uniform(0.035, 0.06)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=rnd.choice(cols) + (255,))
    d.ellipse((x0 + w * 0.22, y0 + h * 0.12, x0 + w * 0.4, y0 + h * 0.3), fill=(255, 255, 255, 170))   # a shine
    return im


def hours_left(egg):
    return max(0.0, HATCH_HOURS - (time.time() - egg.get("found", time.time())) / 3600)


def hatch_name(species, variant):
    return (variant["name"] + " " if variant.get("hue") is not None or variant["name"] != "Natural" else "") + LABEL.get(species, species)
