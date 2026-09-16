"""Moving pictures for the shop site's home page, in site/img/show/.

Everything is composed from the real sprite sheets and the real trick routines (Pet.do_trick is run against a
recorder, so a GIF shows exactly the steps the app plays). No screen is grabbed. Scenes stand the pet on a dark
taskbar strip like the one it lives on.

  meet-<pet>.gif   each character doing its signature move, with its line
  tricks.gif       eight tricks in a row, labelled
  dance.gif        two pets dancing in step (bars three to eight of the routine)
  hide.gif         the folder, with the peek
  gossip.gif       three pets at the table, lines from the Notebook
  reacts.gif       the hop for fast typing, the line for three undos
  attitude.gif     Menace: the look, the cursor, the footprints
  closet.gif       one pet trying on ten looks
  together.gif     study, work, game, eat
  friends.gif      a chase, then a hat swap
  hatmaker.png     three hats from the hat maker with their codes
  eggs.png         four eggs and what hatched
  stage.png        the green-screen stage with everyone on it

Run:  python tools/build_showcase.py     (system Python 3.12 with Pillow; build_site.py calls it too)
"""
import json, math, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRATCH = ROOT / ".showcase_state"
os.environ["APPDATA"] = str(SCRATCH)            # hats from the hat maker land here, never in the real data folder
sys.path.insert(0, str(ROOT / "app"))
from PIL import Image, ImageDraw, ImageFont     # noqa: E402
import perchling as P                           # noqa: E402
import hatmaker as HM                           # noqa: E402
import eggs as E                                # noqa: E402

OUT = ROOT / "site" / "img" / "show"
PET_PX = 150
K = PET_PX / 128                                # routine steps move in app pixels, which are drawn at 128
BAR = 40                                        # the taskbar strip
FPS = 10
INK = (35, 33, 59, 255); SOFT = (107, 102, 133, 255); PLUM = (90, 63, 192, 255); LINE = (216, 208, 232, 255)
NAMES = {"antenna": "Ping", "ears": "Tutu", "leaf": "Moss", "horns": "Rocco"}
_frames = {}


def frames(pid, variant=None):
    key = (pid, json.dumps(variant, sort_keys=True) if variant else None)
    if key not in _frames:
        _frames[key] = P.Frames(pid, PET_PX, variant=variant)
    return _frames[key]


def font(size, bold=True, mono=False):
    names = ["consola.ttf"] if mono else (["seguisb.ttf", "segoeuib.ttf"] if bold else ["segoeui.ttf"])
    for name in names:
        p = Path("C:/Windows/Fonts") / name
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def scene(w, h, bar=True, flat=False):
    """A soft desktop with the taskbar strip along the bottom. flat: one colour, for a GIF that has to stay small."""
    im = Image.new("RGBA", (w, h), (255, 248, 240, 255))
    d = ImageDraw.Draw(im)
    for y in range(0 if not flat else h, h, 4):
        t = y / max(1, h - 1)
        d.rectangle((0, y, w, y + 3), fill=(round(255 - 8 * t), round(248 - 14 * t), round(240 + 6 * t), 255))
    if bar:
        d.rectangle((0, h - BAR, w, h), fill=(32, 30, 48, 255))
        d.line((0, h - BAR, w, h - BAR), fill=(70, 66, 96, 255))
        for i in range(5):                                        # a few quiet pinned-app squares
            x = w // 2 - 70 + i * 34
            d.rounded_rectangle((x, h - BAR + 11, x + 18, h - BAR + 29), radius=4, fill=(62, 58, 88, 255))
    return im


def pet_frame(pid, mood, pose, yaw, wearing=None, variant=None):
    return frames(pid, variant).compose(mood, pose, yaw, wearing or {}).resize((PET_PX, PET_PX), Image.LANCZOS)


def place(im, pet, x, y_bottom):
    """Draw a pet frame with its feet at y_bottom, centred on x. Returns the top y."""
    top = y_bottom - PET_PX
    im.alpha_composite(pet, (round(x - PET_PX / 2), round(top)))
    return top


def bubble(im, text, cx, y_above, size=15):
    """A speech bubble with its tail pointing down at (cx, y_above)."""
    d = ImageDraw.Draw(im); f = font(size, bold=False)
    tw = d.textlength(text, font=f); pw, ph = 11, 7
    w = round(tw + 2 * pw); h = round(size * 1.35 + 2 * ph)
    x0 = max(4, min(im.width - w - 4, round(cx - w / 2))); y0 = round(y_above - h - 10)
    d.rounded_rectangle((x0, y0, x0 + w, y0 + h), radius=11, fill=(255, 255, 255, 255), outline=LINE, width=1)
    tx = max(x0 + 12, min(x0 + w - 12, round(cx)))
    d.polygon([(tx - 6, y0 + h), (tx + 6, y0 + h), (tx, y0 + h + 8)], fill=(255, 255, 255, 255))
    d.line((tx - 6, y0 + h, tx, y0 + h + 8), fill=LINE); d.line((tx + 6, y0 + h, tx, y0 + h + 8), fill=LINE)
    d.text((x0 + pw, y0 + ph - 1), text, font=f, fill=INK)


def label(im, text, x=14, y=12, size=16, colour=PLUM):
    ImageDraw.Draw(im).text((x, y), text, font=font(size), fill=colour)


def save_gif(path, ims, ms):
    """One global palette from a few frames, so the pet's colours don't shimmer between frames."""
    sample = Image.new("RGB", (ims[0].width, ims[0].height * 3))
    for i, k in enumerate((0, len(ims) // 2, len(ims) - 1)):
        sample.paste(ims[k].convert("RGB"), (0, i * ims[0].height))
    pal = sample.quantize(colors=255, method=Image.MEDIANCUT)
    q = [im.convert("RGB").quantize(palette=pal, dither=Image.NONE) for im in ims]
    q[0].save(path, save_all=True, append_images=q[1:], duration=ms, loop=0, optimize=True)
    print(f"{path.name}: {len(ims)} frames, {path.stat().st_size // 1024} KB")


class Recorder:
    """Stands in for a Pet so Pet.do_trick can be run for its steps and lines without a window."""
    def __init__(self, pid, x, w):
        self.sp = P.load_species(pid); self.st = {"name": NAMES[pid]}
        self.x = x; self.y = 0; self.size = PET_PX; self.area = (0, 0, w, 0); self.floor = 0
        self.bit = None; self.mood = "happy"; self.state = "idle"; self.until = 0; self.routine = []; self.anim_t = 0
        self.steps = []; self.says = []; self._t = 0; self.root = self; self.after_routine = None
    def queue_routine(self, steps): self.steps = list(steps)
    def after(self, ms, fn): self._t = ms; fn()
    def say(self, text, ms=2500, **kw): self.says.append((self._t, text, ms))
    def line(self, key, *default): return P.Pet.line(self, key, *default)
    def touched(self, n): pass
    def hide(self): pass
    def winfo_pointerx(self): return 0


def trick_steps(pid, tid, x, w, cap=None, seed=1):
    import random; random.seed(seed)
    r = Recorder(pid, x, w); P.Pet.do_trick(r, tid)
    steps = [(m, p, y, dx, dy, min(ms, cap) if cap else ms) for m, p, y, dx, dy, ms in r.steps]
    return steps, r.says


def play(im_w, im_h, pid, steps, says, x0, wearing=None, tail_ms=600, label_text=None):
    """Frames of one pet playing a routine on the taskbar scene."""
    total = sum(s[5] for s in steps) + tail_ms
    out = []; t = 0
    while t < total:
        # the step at time t, and where the pet has got to by then
        acc = 0; x = x0; y = 0; cur = ("happy", "idle", 0)
        for m, p, yaw, dx, dy, ms in steps:
            if acc > t: break
            x += dx * K; y += dy * K; cur = (m, p, yaw); acc += ms
        x = max(PET_PX / 2, min(im_w - PET_PX / 2, x))
        im = scene(im_w, im_h)
        top = place(im, pet_frame(pid, *cur, wearing), x, im_h - BAR + y)
        ImageDraw.Draw(im).rectangle((0, im_h - BAR, im_w, im_h), fill=(32, 30, 48, 255))   # the bar covers a pet that ducks below it
        for at, text, ms in says:
            if at <= t < at + ms:
                bubble(im, text, x, min(top, im_h - BAR - PET_PX) + 6)
        if label_text:
            label(im, label_text)
        out.append(im); t += 1000 // FPS
    return out


def meet():
    for pid, tid, cap in (("antenna", "peekaboo", None), ("ears", "faint", None), ("leaf", "rot", 2600), ("horns", "sideeye", None)):
        steps, says = trick_steps(pid, tid, 130, 260, cap=cap)
        if tid == "rot":
            says = [(600, "This is the plan.", 2400)]
        if tid == "sideeye":
            says = [(500, "Bold.", 2000)]
        ims = play(260, 250, pid, steps, says, 130, tail_ms=900)
        save_gif(OUT / f"meet-{pid}.gif", ims, 1000 // FPS)


def tricks():
    ims = []
    for pid, tid in (("antenna", "backflip"), ("horns", "moonwalk"), ("ears", "karate"), ("leaf", "robot"),
                     ("ears", "spinout"), ("antenna", "parkour"), ("leaf", "yoga"), ("horns", "panic")):
        steps, says = trick_steps(pid, tid, 240, 480, cap=1800)
        name = next(t["name"] for t in P.load_species(pid)["catalog"]["tricks"] if t["id"] == tid)
        ims += play(480, 250, pid, steps, says, 240, tail_ms=500, label_text=name)
    save_gif(OUT / "tricks.gif", ims, 1000 // FPS)


def dance_pose(t, x0, hop=10):
    """Where a pet is and what frame it shows at second t of the 16 s routine: the same maths as Pet.tick."""
    bar = int(t / 2) % 8; b = t % 2.0; beat = int(b / 0.25) % 8; fast = int(b / 0.125) % 2
    x, y = x0, 0
    if bar == 0:
        y = -(hop if beat % 2 == 0 else 0); fr = ("happy", "wave1" if fast else "wave2", 0)
    elif bar == 1:
        away = 1 if int(t / 16) % 2 == 0 else -1; x = x0 + round(b * 18 * away); fr = ("happy", "walk1" if fast else "walk2", 300 if away > 0 else 60)
    elif bar == 2:
        x = x0 + (6 if fast else -6); fr = ("happy", "squash" if beat % 2 == 0 else "stretch", 60 if fast else 300)
    elif bar == 3:
        ph = b / 2.0; y = -round(28 * (1 - (2 * ph - 1) ** 2))
        fr = ("surprised" if ph > 0.92 else "happy", "squash" if ph > 0.92 else "idle", 0 if ph > 0.92 else (0, 60, 120, 180, 240, 300)[int(ph * 12) % 6])
    elif bar == 4:
        x = x0 + round(b * 12); fr = ("happy", ("lie", "squash", "stretch", "squash")[beat % 4], 0)
    elif bar == 5:
        fr = ("happy", "dab" if beat % 2 == 0 else "flex", 0)
    elif bar == 6:
        fr = ("happy", ("squash", "squash", "stretch", "sit")[beat % 4], 0 if beat < 4 else 300)
    else:
        y = -(hop if fast else 0); fr = ("happy", "wave2" if beat >= 6 else "idle", (0, 60, 0, 300)[beat % 4] if beat < 6 else 0)
    return x, y, fr


def notes(im, t):
    d = ImageDraw.Draw(im)
    for j in range(3):                                         # notes drifting up from the bar
        ph = ((t * 0.7) + j * 0.33) % 1.0; a = round(255 * (1 - ph)); nx = 50 + j * 60 + round(6 * math.sin(ph * 6.3)); ny = 170 - round(ph * 120)
        d.ellipse((nx - 6, ny - 4, nx + 4, ny + 4), fill=(90, 63, 192, a)); d.line((nx + 3, ny, nx + 3, ny - 22), fill=(90, 63, 192, a), width=3)
        d.line((nx + 3, ny - 22, nx + 12, ny - 17), fill=(90, 63, 192, a), width=3)


def dance():
    """Bars three to eight of the routine, two pets side by side."""
    ims = []
    for i in range(6 * 2 * FPS):
        t = 6.0 + i / FPS; im = scene(480, 250)
        for pid, x0 in (("ears", 150), ("horns", 330)):
            x, y, fr = dance_pose(t, x0); place(im, pet_frame(pid, *fr), x, 250 - BAR + y)
        notes(im, t); ims.append(im)
    save_gif(OUT / "dance.gif", ims, 1000 // FPS)


def hero():
    """The first picture on the page: all four dancing in step, most of the routine. Overwrites site/img/hero.gif."""
    ims = []; fps = 8                                          # four bars at 8 fps keeps the first picture under a megabyte
    for bar in (0, 3, 5, 7):
        for i in range(2 * fps):
            t = bar * 2 + i / fps; im = scene(560, 250, flat=True)
            for pid, x0 in (("antenna", 85), ("ears", 215), ("leaf", 345), ("horns", 475)):
                x, y, fr = dance_pose(t, x0); place(im, pet_frame(pid, *fr), x, 250 - BAR + y)
            ims.append(im)
    save_gif(OUT.parent / "hero.gif", ims, 1000 // fps)


def hide():
    fr = frames("antenna"); ims = []
    plan = [(False, 24), (True, 4), (False, 16), (True, 3), (False, 12)]
    for peek, n in plan:
        f = fr.folder_frame({}, peek).resize((PET_PX, PET_PX), Image.LANCZOS)
        for _ in range(n):
            im = scene(480, 250); place(im, f, 240, 250 - BAR); ims.append(im)
    save_gif(OUT / "hide.gif", ims, 1000 // FPS)


def gossip():
    seats = (("antenna", 90, 60), ("ears", 240, 0), ("leaf", 390, 300))
    lines = [(0, "Sam has a test on Friday."), (1, "In three days."), (2, "Let's be quiet that morning."), (0, "Sam's cat is called Biscuit."), (1, "Biscuit again.")]
    ims = []
    for i in range(len(lines) * 2 * FPS + FPS):
        t = i / FPS; im = scene(480, 250); tops = {}
        for k, (pid, x, yaw) in enumerate(seats):
            tops[k] = place(im, pet_frame(pid, "happy", "sit", yaw), x, 250 - BAR)
        k = int(t / 2)
        if k < len(lines) and (t % 2) < 1.8:
            who, text = lines[k]; bubble(im, text, seats[who][1], tops[who] + 10)
        ims.append(im)
    save_gif(OUT / "gossip.gif", ims, 1000 // FPS)


def reacts():
    ims = []; pid = "ears"
    plan = []                                                    # (mood, pose, dy, bubble, caption) per frame
    plan += [("happy", "idle", 0, None, None)] * 8
    for _ in range(3):
        plan += [("happy", "squash", 0, "Go go go.", "typing fast"), ("happy", "stretch", -14, "Go go go.", "typing fast"), ("happy", "idle", -6, "Go go go.", "typing fast"), ("happy", "idle", 0, "Go go go.", "typing fast")]
    plan += [("happy", "idle", 0, "Go go go.", "typing fast")] * 6
    plan += [("happy", "idle", 0, None, None)] * 8
    plan += [("surprised", "idle", 0, "Undo, undo, undo.", "Ctrl+Z three times")] * 22
    plan += [("happy", "idle", 0, None, None)] * 6
    for mood, pose, dy, text, cap in plan:
        im = scene(480, 250); top = place(im, pet_frame(pid, mood, pose, 0), 240, 250 - BAR + dy)
        if text: bubble(im, text, 240, top + 6)
        if cap: label(im, cap, size=14, colour=SOFT)
        ims.append(im)
    save_gif(OUT / "reacts.gif", ims, 1000 // FPS)


def attitude():
    ims = []; pid = "horns"; w = 480
    for i in range(20):                                          # the look
        im = scene(w, 250); top = place(im, pet_frame(pid, "sulky", "idle", 300), 200, 250 - BAR)
        if 4 <= i < 18: bubble(im, "Bold.", 200, top + 6)
        label(im, "Menace"); ims.append(im)
    for i in range(26):                                          # the cursor
        im = scene(w, 250); top = place(im, pet_frame(pid, "happy", "wave1" if i % 6 < 3 else "wave2", 0), 200, 250 - BAR)
        d = ImageDraw.Draw(im); cx, cy = 250, 250 - BAR - 62
        d.polygon([(cx, cy), (cx, cy + 22), (cx + 6, cy + 17), (cx + 10, cy + 26), (cx + 14, cy + 24), (cx + 10, cy + 15), (cx + 17, cy + 15)], fill=(255, 255, 255, 255), outline=(20, 20, 30, 255))
        if 3 <= i < 24: bubble(im, "Mine now. Cry about it.", 200, top + 6)
        label(im, "Menace"); ims.append(im)
    prints = []
    for i in range(26):                                          # the footprints
        x = 200 + i * 7
        if i % 4 == 0: prints.append(x - 30)
        im = scene(w, 250); d = ImageDraw.Draw(im)
        for px in prints:
            d.ellipse((px - 7, 250 - BAR + 6, px + 7, 250 - BAR + 16), fill=(120, 84, 48, 255))
            d.ellipse((px + 8, 250 - BAR + 18, px + 22, 250 - BAR + 28), fill=(120, 84, 48, 255))
        place(im, pet_frame(pid, "happy", "walk1" if i % 2 == 0 else "walk2", 60), x, 250 - BAR)
        label(im, "Menace"); ims.append(im)
    save_gif(OUT / "attitude.gif", ims, 1000 // FPS)


def closet():
    fr = frames("ears"); ims = []
    looks = [("Crown", {"hat": "crown"}), ("Sunglasses and a chain", {"face": "sunglasses", "neck": "chain"}), ("Hoodie and a beanie", {"body": "hoodie", "hat": "beanie"}),
             ("Headphones", {"ears": "headphones"}), ("Wizard", {"hat": "wizard"}), ("Angel wings and a halo", {"back": "angelwings", "hat": "halo"}),
             ("Pirate", {"hat": "pirate", "face": "eyepatch"}), ("Suit and a monocle", {"body": "suit", "face": "monocle"}), ("Jetpack", {"back": "jetpack", "hat": "cap"}),
             ("Party", {"hat": "party", "face": "glasses3d"})]
    for name, wearing in looks:
        wearing = {k: v for k, v in wearing.items() if fr.has_item(v)}
        f = pet_frame("ears", "happy", "idle", 0, wearing)
        for i in range(12):
            im = scene(480, 250); place(im, f, 240, 250 - BAR); label(im, name, size=15); ims.append(im)
    save_gif(OUT / "closet.gif", ims, 1000 // FPS)


def together():
    ims = []; pid = "leaf"
    for pose, text, name in (("study", "Let's study.", "Study with me"), ("work", "Let's get to work.", "Work with me"), ("game", "Game on.", "Game with me"), ("eat", "Yum.", "Eat with me")):
        for i in range(18):
            p = ("eat1" if i % 6 < 3 else "eat2") if pose == "eat" else pose
            mood = "sleepy" if pose == "study" and i > 12 else "happy"
            im = scene(480, 250); top = place(im, pet_frame(pid, mood, p, 0), 240, 250 - BAR)
            if i < 12: bubble(im, text, 240, top + 6)
            label(im, name, size=15); ims.append(im)
    save_gif(OUT / "together.gif", ims, 1000 // FPS)


def friends():
    ims = []; w = 480
    for i in range(30):                                          # the chase
        im = scene(w, 250); x = 90 + i * 9
        place(im, pet_frame("antenna", "surprised", "walk1" if i % 2 == 0 else "walk2", 60, {"hat": "crown"}), x, 250 - BAR)
        place(im, pet_frame("horns", "happy", "walk1" if i % 2 else "walk2", 60, {"hat": "beanie"}), x - 100, 250 - BAR)
        label(im, "Chase"); ims.append(im)
    for i in range(24):                                          # the hat swap
        im = scene(w, 250); swap = i >= 10; hop = -12 if 8 <= i < 12 else 0
        place(im, pet_frame("antenna", "happy", "idle", 300, {"hat": "beanie" if swap else "crown"}), 360, 250 - BAR + hop)
        place(im, pet_frame("horns", "happy", "idle", 60, {"hat": "crown" if swap else "beanie"}), 260, 250 - BAR + hop)
        label(im, "Hat swap"); ims.append(im)
    save_gif(OUT / "friends.gif", ims, 1000 // FPS)


def hatmaker():
    hats = [("antenna", "PH1-cap-1E1B24-F4F1EA-star-F5C242-Night Star"), ("leaf", "PH1-bucket-1F2A5A-F4F1EA-bolt-F4F1EA-Storm"), ("ears", "PH1-cowboy-8B5A2B-F4F1EA-heart-EE8FA4-Ranch")]
    im = Image.new("RGBA", (3 * 300, 300), (255, 255, 255, 0)); d = ImageDraw.Draw(im)
    for i, (pid, code) in enumerate(hats):
        hat = HM.save_hat(P.hats_dir(), HM.from_code(code)); fr = frames(pid); fr.forget_custom()
        f = fr.compose("happy", "idle", 0, {"hat": "my:" + hat["id"]}).resize((200, 200), Image.LANCZOS)
        im.alpha_composite(f, (i * 300 + 50, 20))
        d.text((i * 300 + 150, 232), hat["name"], font=font(18), fill=INK, anchor="mt")
        d.text((i * 300 + 150, 260), code, font=font(11, mono=True), fill=SOFT, anchor="mt")
    im.save(OUT / "hatmaker.png", optimize=True); print("hatmaker.png")


def eggs_png():
    demo = ROOT / "site" / "img" / "demo"
    picks = [("antenna", "Mint", "egg-mint.png"), ("ears", "Lilac", "egg-lilac.png"), ("leaf", "Midnight", "egg-midnight.png"), ("horns", "Golden", "egg-golden.png")]
    im = Image.new("RGBA", (2 * 270, 2 * 200), (255, 255, 255, 0)); d = ImageDraw.Draw(im)
    for i, (pid, name, egg) in enumerate(picks):
        v = next((dict(tier=tier, name=n, hue=h, sat=s, light=l) for tier, (_, cols) in E.TABLE.items() for n, h, s, l in cols if n == name))
        x = (i % 2) * 270; dy = (i // 2) * 200
        e = E.egg_image(84, seed=i); im.alpha_composite(e.convert("RGBA"), (x + 10, dy + 60))
        d.text((x + 115, dy + 100), "→", font=font(26), fill=SOFT, anchor="mm")
        f = frames(pid, v).compose("happy", "idle", 0).resize((150, 150), Image.LANCZOS); im.alpha_composite(f, (x + 120, dy + 10))
        d.text((x + 135, dy + 172), f"{name} {NAMES[pid]}", font=font(15), fill=INK, anchor="mt")
        d.text((x + 52, dy + 156), v["tier"], font=font(12, bold=False), fill=SOFT, anchor="mt")
    im.save(OUT / "eggs.png", optimize=True); print("eggs.png")


def stage():
    w, h = 960, 400
    im = Image.new("RGBA", (w, h), (0, 177, 64, 255)); d = ImageDraw.Draw(im)
    house = ROOT / "site" / "img" / "house-closed.png"
    if house.exists():
        hs = Image.open(house).convert("RGBA"); hs.thumbnail((190, 190)); im.alpha_composite(hs, (60, h - hs.height - 8))
    for pid, x, fr, wearing in (("ears", 330, ("happy", "wave2", 0), {"hat": "crown"}), ("horns", 520, ("happy", "idle", 300), {"face": "sunglasses"}),
                                 ("antenna", 700, ("happy", "dab", 0), {"ears": "headphones"}), ("leaf", 860, ("sleepy", "lie", 0), {})):
        f = frames(pid).compose(*fr, wearing).resize((170, 170), Image.LANCZOS); im.alpha_composite(f, (x - 85, h - 170))
    bubble(im, "Hi chat.", 330, h - 172, size=18)
    d.text((w - 16, 14), "Perchlings Stage", font=font(15), fill=(255, 255, 255, 230), anchor="rt")
    im.convert("RGB").save(OUT / "stage.png", optimize=True); print("stage.png")


def build():
    OUT.mkdir(parents=True, exist_ok=True); (SCRATCH / "Perchlings").mkdir(parents=True, exist_ok=True)
    hero(); meet(); tricks(); dance(); hide(); gossip(); reacts(); attitude(); closet(); together(); friends()
    hatmaker(); eggs_png(); stage()
    import shutil; shutil.rmtree(SCRATCH, ignore_errors=True)


if __name__ == "__main__":
    build()
