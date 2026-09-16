"""site/demo.html: everything a Perchling does, built from the real sprites and catalogs so it can't drift from the app.

Pictures land in site/img/demo/. Run from tools/build_site.py (needs the app's sheets, so after any render).
"""
import json, sys, random
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
import perchling as P          # noqa: E402
import menu as M               # noqa: E402
import fun as F                # noqa: E402
import eggs as E               # noqa: E402
import hatmaker as HM          # noqa: E402
import household as H          # noqa: E402

SITE = ROOT / "site"; OUT = SITE / "img" / "demo"; OUT.mkdir(parents=True, exist_ok=True)
PETS = ["antenna", "ears", "leaf", "horns"]
SPECIES = {p: P.load_species(p) for p in PETS}
CLOSET = json.loads((ROOT / "app" / "closet.json").read_text(encoding="utf-8"))
SHOP = json.loads((ROOT / "app" / "shop.json").read_text(encoding="utf-8"))
PLAYS = {"dance": "They line up and dance in step.", "chase": "One chases the other across the taskbar and back.", "wrestle": "A proper tussle, with a winner.",
         "race": "Ready, set, go, to the far end and back.", "nap": "A pile of pets, asleep in a row.", "copycat": "One does a move, the other copies it, badly.",
         "hatswap": "They trade hats. Both need one.", "peekaboo": "Hide, pop out, scare each other.", "gossip": "A round table and a real conversation about you, from the notebook.",
         "parade": "Everyone marches in a line, with three or more out."}


def still(pet, mood, pose, yaw, wearing, px=144, variant=None):
    fr = P.Frames(pet, 128, variant=variant)
    im = fr.compose(mood, pose, yaw, wearing)
    return im.crop((24, 12, 232, 240)).resize((px, px), Image.LANCZOS)


def save(im, name):
    im.save(OUT / name, optimize=True); return f"img/demo/{name}"


def price_of(iid):
    return SHOP["items"].get(iid, {}).get("price")


def effect_sample(kind, px=144):
    """A pet with a trail, drawn the way the app draws it."""
    rnd = random.Random(kind)
    im = Image.new("RGBA", (px, px), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    cols = F.EFFECT_COLOURS[kind]
    for i in range(14):
        x = rnd.uniform(px * 0.05, px * 0.45); y = rnd.uniform(px * 0.25, px * 0.85); r = rnd.uniform(5, 10); c = rnd.choice(cols) + (255,)
        if kind in ("sparkles", "stars"):
            d.polygon([(x, y - r), (x + r * 0.3, y - r * 0.3), (x + r, y), (x + r * 0.3, y + r * 0.3), (x, y + r), (x - r * 0.3, y + r * 0.3), (x - r, y), (x - r * 0.3, y - r * 0.3)], fill=c)
        elif kind == "hearts":
            d.ellipse((x - r, y - r, x, y), fill=c); d.ellipse((x, y - r, x + r, y), fill=c); d.polygon([(x - r, y - r * 0.3), (x + r, y - r * 0.3), (x, y + r)], fill=c)
        elif kind == "notes":
            d.ellipse((x - r * 0.6, y, x + r * 0.4, y + r * 0.7), fill=c); d.line([(x + r * 0.4, y + r * 0.35), (x + r * 0.4, y - r)], fill=c, width=2)
        elif kind == "bubbles":
            d.ellipse((x - r, y - r, x + r, y + r), outline=c, width=2)
        elif kind == "fire":
            d.polygon([(x, y - r * 1.4), (x + r * 0.7, y + r * 0.3), (x, y + r), (x - r * 0.7, y + r * 0.3)], fill=c)
        else:
            d.ellipse((x - r * 0.7, y - r * 0.7, x + r * 0.7, y + r * 0.7), fill=c)
    im.alpha_composite(still("antenna", "happy", "walk1", 60, {}, px))
    return im


def build():
    parts = []
    h = parts.append
    # ---- characters
    h('<section id="who"><div class="wrap"><h2>Four characters. Pick one, or collect them.</h2><div class="cards">')
    for pid in PETS:
        sp = SPECIES[pid]; v = sp.get("voice", {})
        lines = " ".join(f"<q>{l}</q>" for l in (v.get("hi", [""])[0], v.get("sulk", [""])[0], v.get("mine", [""])[0]) if l)
        sig = next((t["name"] for t in sp["catalog"]["tricks"] if t["id"] == sp.get("signature")), "")
        h(f'<article class="card"><img src="img/{pid}.png" alt="{sp["name"]}" width="256" height="256"><h3 class="name">{sp["name"]}<span class="tag">{sp.get("archetype", "")}</span></h3>'
          f'<p>{sp.get("bio", "")}</p><p class="picks">Signature move: <b>{sig}</b>. Says things like {lines}</p></article>')
    h('</div><p class="note">Every pet can be renamed. The names are just how they arrive.</p></div></section>')
    # ---- tricks
    h('<section id="tricks"><div class="wrap"><h2>39 tricks</h2><p class="lede">Five come with the pet. All of them is one purchase, $2.99, for every pet on your computer. Each pet does its own signature move on its own, too.</p><div class="tiles">')
    for i, t in enumerate(SPECIES["antenna"]["catalog"]["tricks"]):
        pid = PETS[i % 4]; mood, pose, yaw = M.PREVIEW.get(t["id"], ("happy", "idle", 0))
        src = save(still(pid, mood, pose, yaw, {}), f"trick-{t['id']}.png")
        h(f'<div class="tile"><img src="{src}" alt="" width="144" height="144" loading="lazy"><b>{t["name"]}</b><span>{t.get("what", "")}</span></div>')
    h('</div></div></section>')
    # ---- together and plays
    h('<section id="together"><div class="wrap"><h2>Together, and with each other</h2><p class="lede">Together picks keep you company until you click the pet. With more than one pet out, they play, and anyone in the house comes out for it.</p><div class="tiles">')
    for i, t in enumerate(SPECIES["antenna"]["catalog"].get("together", [])):
        mood, pose, yaw = M.PREVIEW.get(t["id"], ("happy", "idle", 0))
        src = save(still(PETS[i % 4], mood, pose, yaw, {"ears": "headphones"} if t["id"] == "game" else {}), f"together-{t['id']}.png")
        h(f'<div class="tile"><img src="{src}" alt="" width="144" height="144" loading="lazy"><b>{t["name"]}</b><span>{t.get("what", "")}</span></div>')
    h('</div><div class="plays">')
    for k in list(H.KINDS) + ["parade"]:
        h(f'<div class="play"><b>{H.NAMES[k]}</b><span>{PLAYS.get(k, "")}</span></div>')
    h('</div></div></section>')
    # ---- attitude and reactions
    h('<section id="attitude"><div class="wrap"><h2>Attitude</h2><div class="plays">'
      '<div class="play"><b>Sweet</b><span>No mischief at all.</span></div>'
      '<div class="play"><b>Cheeky</b><span>Muddy footprints that fade, a note dragged across your screen, a look now and then.</span></div>'
      '<div class="play"><b>Menace</b><span>Steals your cursor for a second, spins out, faints when you walk away, lies down right where you are working. Never breaks anything.</span></div>'
      '</div><p class="note">They also react to you: a cheer when you type fast, "Oops." after three undos, a nap while your screen is locked and "Welcome back." after, a yawn at midnight. And they dance to whatever is playing, eight moves, in step with each other.</p></div></section>')
    # ---- closet
    h('<section id="closet"><div class="wrap"><h2>The closet</h2><p class="lede">Some come with the pet. The rest are $0.99 to $2.49, yours forever, for every pet on your computer. Whatever it wears stays on until you change it.</p>')
    n = 0
    for shelf in CLOSET["shelves"]:
        rows = []
        for it in shelf["items"]:
            pid = PETS[n % 4]; n += 1
            fr = P.Frames(pid, 128)
            if shelf["id"] == "effect":
                src = save(effect_sample(it["id"]), f"item-{it['id']}.png")
            elif fr.has_item(it["id"]):
                src = save(still(pid, "happy", "idle", 0, {shelf["id"]: it["id"]}), f"item-{it['id']}.png")
            else:
                continue
            tag = "comes with the pet" if it.get("included") else (price_of(it["id"]) or "in the shop")
            rows.append(f'<div class="tile"><img src="{src}" alt="" width="144" height="144" loading="lazy"><b>{it["name"]}</b><span>{tag}</span></div>')
        if rows:
            h(f'<h3>{shelf["name"]}</h3><div class="tiles">' + "".join(rows) + '</div>')
    # hat maker samples
    hats = [("cap", "#1E1B24", "#F4F1EA", "star", "#F5C242"), ("beanie", "#6C4BD0", "#F5C242", "bolt", "#F4F1EA"), ("bucket", "#2FB3A3", "#1F2A5A", "smile", "#F5C242"),
            ("tophat", "#3A3A46", "#D63B3B", "diamond", "#5AB0F0"), ("cowboy", "#7A4E2D", "#F5C242", "letterP", "#F4F1EA"), ("visor", "#F4F1EA", "#F58EA6", "heart", "#D63B3B")]
    rows = []
    for i, (shape, main, trim, stk, sc) in enumerate(hats):
        pid = PETS[i % 4]; fr = P.Frames(pid, 128)
        if not (fr.folder / "outfits" / f"maker_{shape}_sheet.json").exists(): continue
        hat = HM.normal({"shape": shape, "main": main, "trim": trim, "sticker": stk, "sticker_color": sc})
        im = fr.compose("happy", "idle", 0, {"hat": "maker-preview"}, preview_hat=hat).crop((24, 12, 232, 240)).resize((144, 144), Image.LANCZOS)
        rows.append(f'<div class="tile"><img src="{save(im, f"maker-{shape}.png")}" alt="" width="144" height="144" loading="lazy"><b>{HM.SHAPES[shape]}</b><span>made in the hat maker</span></div>')
    h('<h3>Your own hats</h3><p class="note">Six shapes, any two colors, a sticker, a name. Every hat has a code you can send to a friend, and their pet wears it too. Free, as many as you like.</p><div class="tiles">' + "".join(rows) + '</div>')
    h('</div></section>')
    # ---- eggs and colours
    h('<section id="eggs"><div class="wrap"><h2>Eggs and colors</h2><p class="lede">Play with a pet on seven different days and it finds an egg. A day later it hatches into a new pet in a rolled color. The odds are printed in the app; eggs are earned, never sold.</p><div class="tiles">')
    for tier, (odds, colours) in E.TABLE.items():
        for name, hue, sat, light in colours:
            variant = {"name": name, "hue": hue, "sat": sat, "light": light}
            pid = "ears" if name != "Natural" else "antenna"
            src = save(still(pid, "happy", "idle", 0, {}, variant=variant if name != "Natural" else None), f"egg-{name.lower()}.png")
            h(f'<div class="tile"><img src="{src}" alt="" width="144" height="144" loading="lazy"><b>{name}</b><span>{tier}, {odds}%</span></div>')
    h('</div></div></section>')
    # ---- the house and the rest
    h('<section id="house"><div class="wrap"><h2>The house</h2><p class="lede">It sits on your taskbar. Click it and it opens into rooms; click a room to decorate it. Two styles, Cozy and Loft, eight wall colors, fourteen pieces of furniture, half of them included.</p>'
      '<div class="two"><figure><img src="img/house.png" alt="The open house, Cozy style" loading="lazy"><figcaption>Cozy</figcaption></figure>'
      '<figure><img src="img/house-loft.png" alt="The open house, Loft style" loading="lazy"><figcaption>Loft</figcaption></figure></div></div></section>')
    h('<section id="app"><div class="wrap"><h2>Inside the app</h2><div class="two">'
      '<figure><img src="img/demo/panel.png" alt="The panel that opens on a right click" loading="lazy"><figcaption>Right-click a pet: the panel.</figcaption></figure>'
      '<figure><img src="img/demo/closet.png" alt="The closet, with the pet wearing each item" loading="lazy"><figcaption>The closet shows the pet in everything.</figcaption></figure></div>'
      '<div class="plays">'
      '<div class="play"><b>Notebook</b><span>Tell it about yourself. It remembers, brings it up later, and gossips about you to the others. Nothing leaves your computer.</span></div>'
      '<div class="play"><b>Remind me</b><span>A day, a time, a few words. It hops and holds up the reminder.</span></div>'
      '<div class="play"><b>Signs and photos</b><span>It holds up whatever you type. Photo makes a framed card with stickers.</span></div>'
      '<div class="play"><b>Clip 8 seconds</b><span>One click records the pet on your real desktop as a GIF, ready to post.</span></div>'
      '<div class="play"><b>Streamer stage</b><span>A green-screen window with the whole household, buttons for the stream, and a note box that tells every pet something at once.</span></div>'
      '<div class="play"><b>Three sizes</b><span>Small, medium, large. And a hat maker, a shop with every price shown, and Start with Windows.</span></div>'
      '</div></div></section>')
    body = "\n".join(parts)
    page = (SITE / "demo-template.html").read_text(encoding="utf-8").replace("<!--BODY-->", body)
    (SITE / "demo.html").write_text(page, encoding="utf-8")
    print("demo.html with", len(list(OUT.glob("*.png"))), "pictures")


if __name__ == "__main__":
    build()
