"""Build site/shop.html, the shop: every outfit, effect, piece of furniture and trick the app sells, with its picture,
its price from app/shop.json, and a Get it button. This is the Roblox model the owner asked for: the pet is the cheap way
in, the items are what people buy. The pictures come from tools/build_demo.py (run it first) plus the furniture art.

Run:  python tools/build_shop.py      (system Python 3.12 with Pillow)
"""
import json, sys, html
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
import house as HOUSE   # noqa: E402  (PIECES: id -> (name, room, included, price))

SITE = ROOT / "site"
OUT = SITE / "img" / "demo"
SHOP = json.loads((ROOT / "app" / "shop.json").read_text(encoding="utf-8"))
CLOSET = json.loads((ROOT / "app" / "closet.json").read_text(encoding="utf-8"))
CATALOG = json.loads((ROOT / "app" / "species" / "antenna.json").read_text(encoding="utf-8"))["catalog"]
STORE = SHOP.get("store_url", "")

SHELF_TITLES = {"hat": "Hats", "face": "Glasses and faces", "ears": "Headphones", "neck": "Around the neck", "body": "Outfits", "back": "Wings, packs and more", "effect": "Effects"}
SHELF_LEDES = {
    "hat": "Every pet can wear every hat. Crowns, beanies, a viking helmet, a wizard hat.",
    "face": "Sunglasses, an eye patch, a monocle, a moustache.",
    "ears": "It wears them to game and to work.",
    "neck": "A chain, a bow tie, a scarf, a bandana.",
    "body": "A hoodie, a jersey, a suit, a sweater.",
    "back": "Angel wings, bat wings, a jetpack, a backpack.",
    "effect": "A trail that follows your pet around the taskbar.",
}


def price_of(iid):
    return SHOP["items"].get(iid, {}).get("price")


def url_of(iid):
    return SHOP["items"].get(iid, {}).get("url") or ""


def furniture_pictures():
    """Small pictures of the furniture, from the house art."""
    for pid in HOUSE.PIECES:
        src = ROOT / "assets" / "house" / "furniture" / f"{pid}.png"
        if not src.exists():
            continue
        im = Image.open(src).convert("RGBA"); bb = im.getbbox()
        if bb:
            im = im.crop(bb)
        w, h = im.size; s = 132 / max(w, h)
        im = im.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)
        card = Image.new("RGBA", (144, 144), (0, 0, 0, 0)); card.alpha_composite(im, ((144 - im.width) // 2, (144 - im.height) // 2))
        card.save(OUT / f"furniture-{pid}.png", optimize=True)


def tile(iid, name, src, included, what=""):
    """One item card. Included items say so; the rest carry the price and a Get it button."""
    name = html.escape(name); what = html.escape(what)
    if included:
        return f'<div class="item"><img src="{src}" alt="" width="144" height="144" loading="lazy"><b>{name}</b>{f"<span>{what}</span>" if what else ""}<i class="tag">comes with the pet</i></div>'
    price = price_of(iid) or "$0.99"
    href = url_of(iid) or STORE or f"adopt.html?item={iid}&name={html.escape(name)}&price={price}"
    demo = "" if url_of(iid) else f' data-item="{iid}" data-item-name="{name}" data-item-price="{price}"'
    return (f'<div class="item"><img src="{src}" alt="" width="144" height="144" loading="lazy"><b>{name}</b>{f"<span>{what}</span>" if what else ""}'
            f'<a class="get" href="{href}"{demo}>Get it <em>{price}</em></a></div>')


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    furniture_pictures()
    parts = []; h = parts.append; chips = []
    # closet shelves
    for shelf in CLOSET["shelves"]:
        rows = []
        for it in shelf["items"]:
            src = OUT / f"item-{it['id']}.png"
            if not src.exists():
                continue
            rows.append(tile(it["id"], it["name"], f"img/demo/item-{it['id']}.png", it.get("included", False)))
        if rows:
            sid = shelf["id"]; chips.append((sid, SHELF_TITLES.get(sid, shelf["name"])))
            h(f'<section id="{sid}"><div class="wrap"><h2>{SHELF_TITLES.get(sid, shelf["name"])}</h2><p class="lede">{SHELF_LEDES.get(sid, "")}</p><div class="items">' + "".join(rows) + '</div></div></section>')
    # furniture
    rows = []
    for pid, (name, room, included, price) in HOUSE.PIECES.items():
        if not (OUT / f"furniture-{pid}.png").exists():
            continue
        rows.append(tile(f"furniture:{pid}", name, f"img/demo/furniture-{pid}.png", included, f"{room} room" if room == "living" else room))
    chips.append(("furniture", "Furniture"))
    h('<section id="furniture"><div class="wrap"><h2>Furniture</h2><p class="lede">For the house. Click a room to put a piece in or take it out.</p><div class="items">' + "".join(rows) + '</div></div></section>')
    # tricks and picks
    rows = []
    for t in CATALOG["tricks"]:
        if not (OUT / f"trick-{t['id']}.png").exists():
            continue
        rows.append(tile(f"pick:{t['id']}", t["name"], f"img/demo/trick-{t['id']}.png", False, t.get("what", "")))
    chips.append(("tricks", "Tricks"))
    h('<section id="tricks"><div class="wrap"><h2>Tricks</h2><p class="lede">Five come with your pet, your pick. Add the rest one at a time. Your pet does them on command and on its own.</p><div class="items">' + "".join(rows) + '</div></div></section>')
    rows = []
    for t in CATALOG.get("together", []):
        if not (OUT / f"together-{t['id']}.png").exists():
            continue
        rows.append(tile(f"pick:{t['id']}", t["name"], f"img/demo/together-{t['id']}.png", False, t.get("what", "")))
    if rows:
        chips.append(("together", "Together"))
        h('<section id="together"><div class="wrap"><h2>Together</h2><p class="lede">Your pet keeps you company with a laptop, headphones or a snack until you click it.</p><div class="items">' + "".join(rows) + '</div></div></section>')
    chipbar = "".join(f'<a href="#{sid}">{title}</a>' for sid, title in chips)
    page = (SITE / "shop-template.html").read_text(encoding="utf-8").replace("<!--CHIPS-->", chipbar).replace("<!--BODY-->", "\n".join(parts))
    (SITE / "shop.html").write_text(page, encoding="utf-8")
    print("shop.html:", sum(p.count('class="item"') for p in parts), "items")


if __name__ == "__main__":
    build()
