"""Build the generated parts of the shop site in site/.

- site/pets.js            copy of web/pets.js (the site's live 3D pets use the same source as the app)
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
HAT_FOR = {"antenna": "beanie", "ears": "flowers", "leaf": "crown", "horns": "party"}


def stills():
    IMG.mkdir(parents=True, exist_ok=True)
    out = {}
    for pet in PETS:
        fr = Frames(pet, 256)
        plain = fr.compose("happy", "idle", 0)
        plain.save(IMG / f"{pet}.png", optimize=True)
        hat = HAT_FOR[pet] if fr.has_item(HAT_FOR[pet]) else None
        dressed = fr.compose("happy", "idle", 0, {"hat": hat} if hat else None)
        dressed.save(IMG / f"{pet}-hat.png", optimize=True)
        out[pet] = (plain, dressed)
        print(f"{pet}: still{' + ' + hat if hat else ''}")
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
    d.text((74, 190), "A little pet that lives on your desktop.", font=font(38, bold=False), fill=(90, 63, 192, 255))
    d.text((74, 244), "Pick your favorite. Name it, pick 5 things it can do, dress it up.", font=font(26, bold=False), fill=(107, 102, 133, 255))
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


def main():
    SITE.mkdir(exist_ok=True)
    shutil.copyfile(ROOT / "web" / "pets.js", SITE / "pets.js")
    print("pets.js copied")
    images = stills()
    og(images)
    icons(images)


if __name__ == "__main__":
    main()
