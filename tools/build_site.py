"""Build the generated parts of the shop site in site/.

- site/pets.js            copy of web/pets.js (the site's live 3D pets use the same source as the app)
- site/playground.html    the look test as a public page: pick a pet, a mood and a hat, drag to turn them
- site/img/<pet>.png      still of each pet, happy, facing you, 256 px, see-through background
- site/img/<pet>-hat.png  the same pet with a hat on, for the closet section
- site/img/og.png         1200 x 630 picture for links shared on social media
- site/img/icon-*.png     browser tab and phone home-screen icons

Run:  python tools/build_site.py      (system Python 3.12 with Pillow)
"""
import json, shutil, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
from perchling import Frames  # noqa: E402  (compose() needs no window)

SITE = ROOT / "site"
IMG = SITE / "img"
PETS = ["antenna", "ears", "leaf", "horns"]
# the dressed stills: what each pet wears and what it is doing in the closet picture
DRESSED = {
    "antenna": ("happy", "wave2", {"hat": "beanie", "face": "glasses"}),
    "ears":    ("happy", "idle", {"hat": "flowers", "ears": "headphones"}),
    "leaf":    ("happy", "sit", {"hat": "crown"}),
    "horns":   ("happy", "idle", {"hat": "party", "face": "sunglasses"}),
}


def stills():
    IMG.mkdir(parents=True, exist_ok=True)
    out = {}
    for pet in PETS:
        fr = Frames(pet, 256)
        plain = fr.compose("happy", "idle", 0)
        plain.save(IMG / f"{pet}.png", optimize=True)
        mood, pose, wearing = DRESSED[pet]
        wearing = {k: v for k, v in wearing.items() if fr.has_item(v)}
        dressed = fr.compose(mood, pose, 0, wearing)
        dressed.save(IMG / f"{pet}-hat.png", optimize=True)
        out[pet] = (plain, dressed)
        print(f"{pet}: still + {pose} in {', '.join(wearing.values()) or 'nothing'}")
    return out


def font(size, bold=True):
    for name in (["seguisb.ttf", "segoeuib.ttf"] if bold else ["segoeui.ttf"]):
        p = Path("C:/Windows/Fonts") / name
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def og(images):
    w, h = 1200, 630
    im = Image.new("RGBA", (w, h), (255, 248, 240, 255))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 330, w, h), radius=0, fill=(240, 228, 250, 255))
    d.text((72, 96), "Perchlings", font=font(76), fill=(35, 33, 59, 255))
    d.text((74, 190), "A tiny pet that lives at the bottom of your screen.", font=font(38, bold=False), fill=(90, 63, 192, 255))
    d.text((74, 244), "Pick one of four, name it, and it hangs out while you work.", font=font(26, bold=False), fill=(107, 102, 133, 255))
    x = 120
    for pet in PETS:
        _, dressed = images[pet]
        big = dressed.resize((300, 300), Image.LANCZOS)
        im.alpha_composite(big, (x, 300))
        x += 250
    im.convert("RGB").save(IMG / "og.png", optimize=True)
    print("og.png")


def icons(images):
    plain, _ = images["antenna"]
    head = plain.crop((60, 8, 196, 144))          # the head, roughly
    for size, name in ((32, "icon-32.png"), (180, "icon-180.png"), (512, "icon-512.png")):
        head.resize((size, size), Image.LANCZOS).save(IMG / name, optimize=True)
    print("icons")


def playground():
    """web/look-test.html with pets.js inlined and the copy written for visitors instead of us."""
    src = (ROOT / "web" / "look-test.html").read_text(encoding="utf-8")
    pets = (ROOT / "web" / "pets.js").read_text(encoding="utf-8")
    out = src.replace('<script src="pets.js"></script>', "<script>" + chr(10) + pets + chr(10) + "</script>")
    swaps = {
        "<title>Perchlings Look Test</title>": "<title>Perchlings playground</title>",
        "<h1>Perchlings, look test</h1>": "<h1>Perchlings playground</h1>",
        "<p>Same family, with range. Teal and Pink are baby-cute. Green is a little older. Gold is the cool one: smaller eyes set higher, half-lidded, no blush, taller. Labelled by colour until they have names. Drag to turn them. Click a pet, then pick a mood and a hat.</p>":
        "<p>All four pets, live. Drag to turn them around. Click a pet, then pick a mood and try on a hat. We call them by their colors; you get to name yours.</p>",
        "They blink, breathe and watch your cursor on their own.": "They blink, breathe, and follow your mouse on their own.",
    }
    for a, b in swaps.items():
        assert a in out, a[:40]
        out = out.replace(a, b)
    (SITE / "playground.html").write_text(out, encoding="utf-8")
    print("playground.html")


def house_still(style="cozy"):
    """The open house with a pet in every room, for the site."""
    import json
    art = ROOT / "assets" / "house"
    layout = json.loads((art / "layout.json").read_text(encoding="utf-8"))
    from PIL import ImageChops
    base = Image.open(art / ("open.png" if style == "cozy" else f"open-{style}.png")).convert("RGBA")
    paint = {"living": "#FFD98F", "kitchen": "#A9DDA0", "bedroom": "#C9B3F2", "bathroom": "#93CFE3"} if style == "cozy" else {"living": "#4A4860", "kitchen": "#3B4B6E", "bedroom": "#8FA58A", "bathroom": "#B8735A"}
    for room, r in layout["rooms"].items():
        x0, y0, x1, y1 = r["wall"]; region = base.crop((x0, y0, x1, y1))
        painted = ImageChops.multiply(region.convert("RGB"), Image.new("RGB", region.size, paint[room])).convert("RGBA"); painted.putalpha(region.getchannel("A"))
        base.paste(painted, (x0, y0))
    for piece in ("bed", "lamp", "poster", "couch", "tv", "rug", "plant", "table", "stove", "fridge", "fishtank", "tub", "sink"):
        base.alpha_composite(Image.open(art / "furniture" / f"{piece}.png").convert("RGBA"))
    for pid, room, mood, pose, dy, wearing in (("antenna", "bedroom", "sleepy", "squash", -0.45, {"hat": "beanie"}), ("ears", "living", "happy", "sit", -0.42, {"ears": "headphones"}),
                                              ("leaf", "kitchen", "happy", "eat1", 0, {"hat": "crown"})):
        r = layout["rooms"][room]; ppu = r["petPx"] / 1.5; px = round(r["petPx"] * 1.25)
        im = Frames(pid, 128).compose(mood, pose, 0, wearing).resize((px, px), Image.LANCZOS)
        base.alpha_composite(im, (round(r["spot"] - px / 2), round(r["floor"] - px * 0.86 + dy * ppu)))
    base.alpha_composite(Image.open(art / "furniture" / "curtain.png").convert("RGBA"))
    bb = base.getbbox(); base = base.crop((bb[0] - 10, bb[1] - 10, bb[2] + 10, bb[3] + 10))
    base.resize((960, round(base.height * 960 / base.width)), Image.LANCZOS).save(IMG / ("house.png" if style == "cozy" else f"house-{style}.png"), optimize=True)
    if style == "cozy":
        closed = Image.open(art / "closed.png").convert("RGBA"); bb = closed.getbbox(); closed.crop(bb).save(IMG / "house-closed.png", optimize=True)
    print(f"house {style}")


def main():
    SITE.mkdir(exist_ok=True)
    house_still(); house_still("loft")
    shutil.copyfile(ROOT / "web" / "pets.js", SITE / "pets.js")
    print("pets.js copied")
    playground()
    images = stills()
    og(images)
    icons(images)
    import build_demo; build_demo.build()
    import build_showcase; build_showcase.build()
    for name, out in (("_menu_home.png", "panel.png"), ("_closet.png", "closet.png"), ("_decorate.png", "decorate.png"), ("_menu_house.png", "panel-house.png")):
        src = ROOT / "assets" / "sprites" / "_fit" / name          # the app's own screens, from a test pet
        if src.exists():
            im = Image.open(src).convert("RGB"); im.save(IMG / "demo" / out, optimize=True)


if __name__ == "__main__":
    main()
