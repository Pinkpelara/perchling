"""Fill the front page's skills block from the app itself, so the site never drifts from what the pets can do.

Between <!-- skills --> and <!-- /skills --> in site/index.html: every trick with its own line and picture, the four
habits, the four ways it keeps you company, every game two or more pets play, and everything it notices about you.
The trick, habit and company lines come from the species catalog (the same lines the app shows on hover), the game
lines from menu.PLAY_TIPS, and the notices are written here from what perchling.py does. Run by build_site.py.
"""
import html, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
sys.path.insert(0, str(ROOT / "app"))

NOTICES = [
    ("Type fast", "It hops and cheers you on. Go go go."),
    ("Click like crazy", "It tells you to take it easy."),
    ("Hit undo three times", "Oops. Undo, undo, undo."),
    ("Save three times in a row", "Saved. Again."),
    ("Step away for a few minutes", "It looks around, then sits by the door and waits. Gone a while, and it naps."),
    ("Come back", "It hops up, stretches, and says hi with your name. Every pet at once."),
    ("Lock your computer", "It sleeps till you're back."),
    ("Land your cursor on it", "It looks up. Move the cursor near and it turns its head to follow."),
    ("Ignore it for twenty minutes", "It asks for attention. An hour, and it sulks till you tickle it."),
    ("Midnight", "A yawn, and it tells you."),
    ("Play music", "It dances, and so does everyone else on the screen."),
    ("Pick it up", "Its legs kick. Hold it up for a second and it pulls out a parachute; let go and it floats down."),
    ("Spin your cursor around it", "Two or three fast turns and it gets dizzy: spiral eyes, stars, a stagger, a flop."),
    ("Drop it on the house", "It walks in. Drag it out of an open room and it comes out where you let go."),
]


def card(img, name, what):
    pic = f'<img src="{img}" alt="" width="200" height="200" loading="lazy">' if img else ""
    return f'<div class="skill">{pic}<b>{html.escape(name)}</b><p>{html.escape(what)}</p></div>'


def build():
    import menu as M
    from household import KINDS, NAMES
    cat = json.loads((ROOT / "app" / "species" / "antenna.json").read_text(encoding="utf-8"))["catalog"]
    parts = ['<section id="skills">', '  <div class="wrap">', '    <div class="center">', '      <h2>Every trick it can learn</h2>',
             '      <p class="lede">Your pet picks five of these for free the day it arrives, on top of its signature move. The rest are $0.99 each in the shop. Buy one once and every pet on your computer can do it. '
             'Right-click your pet and choose Tricks to see one right now, or wait and it does them on its own.</p>', '    </div>']
    parts.append('    <div class="skills">' + "".join(card(f"img/demo/trick-{t['id']}.png" if (SITE / "img" / "demo" / f"trick-{t['id']}.png").exists() else "", t["name"], t["what"]) for t in cat["tricks"]) + '</div>')
    parts.append('    <h3 class="skills-head">Habits</h3><p class="lede left">Switch one on and it changes how the day goes.</p>')
    parts.append('    <div class="skills four">' + "".join(card("", t["name"], t["what"]) for t in cat["behaviours"]) + '</div>')
    parts.append('    <h3 class="skills-head">Keeping you company</h3><p class="lede left">Pick one from the menu and it settles in next to you until you click it.</p>')
    parts.append('    <div class="skills four">' + "".join(card(f"img/demo/together-{t['id']}.png" if (SITE / "img" / "demo" / f"together-{t['id']}.png").exists() else "", t["name"], t["what"]) for t in cat["together"]) + '</div>')
    kinds = list(KINDS) + ["parade"]
    parts.append('    <h3 class="skills-head">Games for two or more</h3><p class="lede left">Get a second pet and these show up on the menu. They start them on their own too.</p>')
    parts.append('    <div class="skills five">' + "".join(card("", NAMES.get(k, k.title()), M.PLAY_TIPS.get(k, "")) for k in kinds) + '</div>')
    parts.append('    <h3 class="skills-head">What it notices</h3><p class="lede left">It pays attention to you. This is on from the start, and the switch is on the menu.</p>')
    parts.append('    <div class="skills four">' + "".join(card("", when, what) for when, what in NOTICES) + '</div>')
    parts.append('    <p class="lede left">Four moods, and you get to see all of them: happy, surprised, sleepy and sulky.</p>')
    parts += ['  </div>', '</section>']
    block = "\n".join(parts)
    page = (SITE / "index.html").read_text(encoding="utf-8")
    a, b = "<!-- skills -->", "<!-- /skills -->"
    if a in page and b in page:
        page = page[:page.index(a) + len(a)] + "\n" + block + "\n" + page[page.index(b):]
    else:
        page = page.replace('<section id="more">', f"{a}\n{block}\n{b}\n\n" + '<section id="more">', 1)
    (SITE / "index.html").write_text(page, encoding="utf-8")
    print("index.html skills:", len(cat["tricks"]), "tricks,", len(cat["behaviours"]), "habits,", len(cat["together"]), "company,", len(kinds), "games,", len(NOTICES), "notices")


if __name__ == "__main__":
    build()
