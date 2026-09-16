"""The egg, end to end, on the real app code in a scratch data folder.

One pet (Ping) runs in this process on a plain backdrop window of its own. The demo walks it from six good days
to the seventh touch, the egg it finds, the wait, the hatch (time warped) and the new pet that starts as a real
second process, and captures pictures of the demo's own windows only (a backdrop window covers the desktop
behind them). Outputs in .demo/egg/: A..G .png stills, egg-demo.png (the storyboard with captions) and
egg-demo.gif (the two moving moments). Run it with the system Python 3.12; it takes about forty seconds and
the two pets show up on the taskbar while it runs. --compose rebuilds the storyboard from the saved stills.
"""
import os, sys, time, json, shutil, subprocess
from pathlib import Path
from datetime import date, timedelta

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / ".demo" / "egg"                            # the pictures land here; .demo/ is not committed
HERE.mkdir(parents=True, exist_ok=True)
DATA = HERE / "appdata"
if DATA.exists():
    shutil.rmtree(DATA, ignore_errors=True)
DATA.mkdir(parents=True, exist_ok=True)
os.environ["APPDATA"] = str(DATA)                      # the demo pets keep their files here, not with the real ones
sys.path.insert(0, str(ROOT / "app"))
import tkinter as tk                                    # noqa: E402
from PIL import Image, ImageGrab, ImageDraw, ImageFont  # noqa: E402
import perchling as P, eggs as E, household as H, stage as S   # noqa: E402

procs = []
real_popen = subprocess.Popen
def popen(*a, **k):
    p = real_popen(*a, **k); procs.append(p); return p
subprocess.Popen = popen                                # the hatchling really starts; we keep its handle to stop it after

if "--compose" not in sys.argv:
    P.save_owner_file(reacts=False, music=False)            # the real keyboard and speakers stay out of the demo
    pet = P.Pet(P.load_species("antenna"), selftest=True)
    pet.flags_read = 0
    log = []


    def tick():
        pet._selftest_ticks = 0                              # a self-test pet quits after 70 ticks unless the driver resets this
        pet.root.update()


    def run(sec, until=None):
        t0 = time.time()
        while time.time() - t0 < sec:
            tick()
            if until and until():
                return True
            time.sleep(0.02)
        return False


    def settle(timeout=10):
        return run(timeout, lambda: pet.state in ("idle", "walk", "sit") and not pet.routine)


    def quiet():
        """Nothing scheduled gets in the way for the next hour: no wander, break, mischief, play or self trick."""
        pet.state = "idle"; pet.routine = []; pet.until = time.time() + 3600
        for k in list(vars(pet)):
            if k.startswith("next_"):
                setattr(pet, k, time.time() + 3600)


    run(0.6)
    SZ = pet.size
    left, top, right, bottom = pet.area
    quiet()
    pet.x = left + 520; pet.y = pet.floor; pet.place(); pet.show(*pet.last_frame)

    # a house far away on the other screen, so the hatchling doesn't bring one out and nobody walks to it
    fake_house = {"door_x": 5200, "door_y": pet.floor, "x": 5100, "y": pet.floor - 100, "size": 200,
                  "area": [3840, 0, 5760, bottom], "open": False}
    def keep_house():
        (H.base_dir() / "house.json").write_text(json.dumps(dict(fake_house, ts=time.time())), encoding="utf-8")
    keep_house()

    # the capture region and the demo's own backdrop: a plain sheet with a dark strip where the taskbar is
    X0, X1 = int(pet.x - SZ - 30), int(pet.x + SZ + round(SZ * 0.72) + 230)
    Y0, Y1 = int(pet.floor - round(SZ * 1.4)), int(bottom + 48)
    bd = tk.Toplevel(pet.root); bd.overrideredirect(True); bd.attributes("-topmost", True)
    cv = tk.Canvas(bd, width=X1 - X0, height=Y1 - Y0, bg="#FFF6EC", bd=0, highlightthickness=0); cv.pack()
    cv.create_rectangle(0, bottom - Y0, X1 - X0, Y1 - Y0, fill="#201E30", outline="")
    for i in range(5):                                       # a few quiet pinned-app squares, like the site pictures
        x = (X1 - X0) // 2 - 70 + i * 34
        cv.create_rectangle(x, bottom - Y0 + 14, x + 20, bottom - Y0 + 34, fill="#3E3A58", outline="")
    bd.geometry(f"{X1 - X0}x{Y1 - Y0}+{X0}+{Y0}")
    bd.update()
    pet.root.attributes("-topmost", True); pet.root.lift()
    run(0.4)


    import ctypes
    from ctypes import wintypes
    _u, _g = ctypes.windll.user32, ctypes.windll.gdi32


    def grab_region(x0, y0, x1, y1):
        """Just this rectangle of the screen, by BitBlt, so a capture takes a few milliseconds instead of a whole-screen copy."""
        w, h = x1 - x0, y1 - y0
        sdc = _u.GetDC(0); mdc = _g.CreateCompatibleDC(sdc); bmp = _g.CreateCompatibleBitmap(sdc, w, h)
        old = _g.SelectObject(mdc, bmp)
        _g.BitBlt(mdc, 0, 0, w, h, sdc, x0, y0, 0x00CC0020)          # SRCCOPY
        class BMI(ctypes.Structure):
            _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                        ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
                        ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]
        bmi = BMI(ctypes.sizeof(BMI), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        buf = ctypes.create_string_buffer(w * h * 4)
        _g.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bmi), 0)
        _g.SelectObject(mdc, old); _g.DeleteObject(bmp); _g.DeleteDC(mdc); _u.ReleaseDC(0, sdc)
        return Image.frombuffer("RGB", (w, h), buf.raw, "raw", "BGRX", 0, 1).copy()


    def grab():
        return grab_region(X0, Y0, X1, Y1)


    def grab_win(w):
        w.update_idletasks()
        x, y, ww, hh = w.winfo_rootx(), w.winfo_rooty(), w.winfo_width(), w.winfo_height()
        return ImageGrab.grab(bbox=(x, y, x + ww, y + hh), all_screens=True)


    class Ev:
        pass


    def panel_page(page):
        ev = Ev(); ev.x_root, ev.y_root = int(pet.x + 40), int(pet.y)
        pet.on_menu(ev); run(0.5)
        pet.panel.show(page); run(0.7)
        im = grab_win(pet.panel.win)
        head = None
        pet.panel.close(); run(0.3)
        return im


    stills = {}

    # A: six good days done, two touches today. The panel's Egg page says what's left.
    today = date.today()
    pet.st["care"] = {(today - timedelta(days=i)).isoformat(): 4 for i in range(1, 7)}
    pet.st["care"][today.isoformat()] = 2
    pet.st["egg_baseline"] = ""
    P.save_state(pet.st)
    log.append(("A", pet.egg_status()))
    stills["A"] = panel_page("egg")
    quiet()

    # B: the third touch of the day makes it seven good days; on the next minute check the pet finds an egg
    frames_found = []
    pet.touched(2)
    pet.last_attention_tick = time.time() - 61
    t0 = time.time(); patched = False
    while time.time() - t0 < 4.6:
        tick()
        egg = pet.egg()
        if egg and not patched:                              # the demo picks the kind and colour so the change shows
            egg["species"] = "ears"; egg["variant"] = {"tier": "uncommon", "name": "Lilac", "hue": 270, "sat": 1.0, "light": 1.02}
            pet.egg_file().write_text(json.dumps(egg), encoding="utf-8"); patched = True
        frames_found.append((time.time() - t0, grab())); time.sleep(0.05)
    log.append(("B", pet.egg(), pet.saying))
    stills["C"] = min(frames_found, key=lambda f: abs(f[0] - 3.4))[1]     # the moment with the bubble up and the egg down
    frames_found = [f for _, f in frames_found]
    settle(8); quiet()

    # C2: a click on the egg says how long is left
    run(1.6)
    if getattr(pet, "egg_win", None):
        pet.egg_win.label.event_generate("<Button-1>")
    run(0.5)
    if not pet.saying:
        pet.say("Hatches in about 24 hours."); run(0.3)
    stills["C2"] = grab()
    log.append(("C", pet.saying))

    # D: the Egg page while the egg is out
    log.append(("D", pet.egg_status()))
    stills["D"] = panel_page("egg")
    quiet()

    # E: time warped a day ahead; the egg hatches, and the new pet starts as its own program next to it
    egg = pet.egg(); egg["found"] = time.time() - E.HATCH_HOURS * 3600 - 10
    pet.egg_file().write_text(json.dumps(egg), encoding="utf-8")
    frames_hatch = []
    t0 = time.time()
    while time.time() - t0 < 9.0:
        tick(); keep_house()
        frames_hatch.append(grab()); time.sleep(0.05)
    new = [p for p in P.adopted_ids() if "#" in p]
    log.append(("E", new, [P.pet_state(p).get("name") for p in new], len(procs)))

    # F: the two of them; the hatchling is asked to wave through the household's command file
    run(1.5, lambda: (keep_house(), False)[1])
    if new:
        S.command(new[0], "wave")
    t0 = time.time()
    while time.time() - t0 < 1.4:
        tick(); keep_house(); time.sleep(0.03)
    stills["F"] = grab()

    # G: the Pets page lists the household, hatchling included
    stills["G"] = panel_page("pets")
    log.append(("G", P.adopted_ids(), sorted(p.name for p in (H.base_dir() / "here").glob("*.json"))))

    # stop the hatchling and close the demo
    for p in list(procs):
        real_popen(["taskkill", "/PID", str(p.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).wait()
    time.sleep(0.5)
    try:
        bd.destroy(); pet.root.destroy()
    except tk.TclError:
        pass

# ---- pictures
def font(size, bold=True):
    for name in (["seguisb.ttf", "segoeuib.ttf"] if bold else ["segoeui.ttf"]):
        p = Path("C:/Windows/Fonts") / name
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


INK, SOFT, CREAM, LINE = (35, 33, 59), (107, 102, 133), (255, 251, 246), (216, 208, 232)
CAPTIONS = [
    ("A", "1. Play with a pet on seven different days. Three touches a day (a hover, a click, a drag, or opening its panel) make a good day. The Egg page keeps count."),
    ("C", "2. The seventh good day: the pet bounces, says it found an egg, and the egg sits next to it on the taskbar. One egg per household at a time."),
    ("C2", "3. Click the egg and the pet tells you how long is left. It hatches 24 hours after it was found."),
    ("D", "4. While the egg is out, the Egg page says who found it, when it hatches and the odds for its color."),
    ("F", "5. The hatch: confetti, a bounce and the news. The new pet starts on its own next to the one that found the egg, drawn smaller for its first two weeks. This one rolled Lilac, on the Pink kind."),
    ("G", "6. The Pets page lists the household, hatchling included, with its own name and color. Up to six pets. Eggs are never sold."),
]
CELL_W = 760; PAD = 26; CAP_F = font(21, bold=False)


def wrap(text, f, width):
    words = text.split(); lines = []; cur = ""
    d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= width:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


def storyboard(stills):
    cells = []
    for key, cap in CAPTIONS:
        im = stills[key].convert("RGB")
        if im.width > CELL_W - 2 * PAD:
            r = (CELL_W - 2 * PAD) / im.width; im = im.resize((CELL_W - 2 * PAD, round(im.height * r)), Image.LANCZOS)
        lines = wrap(cap, CAP_F, CELL_W - 2 * PAD)
        h = PAD + im.height + 14 + len(lines) * 30 + PAD
        cell = Image.new("RGB", (CELL_W, h), CREAM); d = ImageDraw.Draw(cell)
        cell.paste(im, (PAD, PAD)); d.rectangle((PAD - 1, PAD - 1, PAD + im.width, PAD + im.height), outline=LINE)
        y = PAD + im.height + 14
        for ln in lines:
            d.text((PAD, y), ln, font=CAP_F, fill=INK); y += 30
        cells.append(cell)
    TITLE_F = font(34); SUB_F = font(22, bold=False)
    head_h = 120
    H_total = head_h + 28 + sum(c.height + 12 for c in cells) + 20
    board = Image.new("RGB", (CELL_W + 20, H_total), (246, 240, 250)); d = ImageDraw.Draw(board)
    d.text((PAD, 30), "How the egg works", font=TITLE_F, fill=INK)
    sub = wrap("Captured from the real app in a scratch folder. The 24-hour wait is skipped ahead.", SUB_F, CELL_W - 2 * PAD)
    for i, ln in enumerate(sub):
        d.text((PAD, 74 + i * 28), ln, font=SUB_F, fill=SOFT)
    y = head_h + max(0, len(sub) - 1) * 28
    for c in cells:
        board.paste(c, (10, y)); y += c.height + 12
    board.save(HERE / "egg-demo.png", optimize=True)


def movie(frames_found, frames_hatch):
    def title_card(text, sub=""):
        im = Image.new("RGB", (X1 - X0, Y1 - Y0), (255, 246, 236)); d = ImageDraw.Draw(im)
        f = font(30); f2 = font(20, bold=False)
        for i, ln in enumerate(wrap(text, f, im.width - 60)):
            d.text((30, 40 + i * 40), ln, font=f, fill=INK)
        for i, ln in enumerate(wrap(sub, f2, im.width - 60)):
            d.text((30, 150 + i * 28), ln, font=f2, fill=SOFT)
        return im


    seq = [(title_card("The seventh good day", "Three touches today. On its next check the pet finds an egg."), 1600)]
    seq += [(f, 90) for f in frames_found[::1]]
    seq += [(title_card("A day later", "The wait is skipped ahead here. The new pet starts on its own next to Ping."), 1600)]
    seq += [(f, 90) for f in frames_hatch[::1]]
    scale = 0.6
    gif = []; durs = []
    for im, ms in seq:
        im = im.convert("RGB").resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
        gif.append(im.quantize(colors=128, method=Image.Quantize.MEDIANCUT)); durs.append(ms)
    gif[0].save(HERE / "egg-demo.gif", save_all=True, append_images=gif[1:], duration=durs, loop=0, optimize=True)


if __name__ == "__main__" and "--compose" not in sys.argv:
    for k, im in stills.items():
        im.save(HERE / f"{k}.png")
    storyboard(stills); movie(frames_found, frames_hatch)
    for entry in log:
        print(entry)
    print("found frames", len(frames_found), "hatch frames", len(frames_hatch), "procs", len(procs))
    print("region", (X0, Y0, X1, Y1), "size", SZ)
elif __name__ == "__main__":
    storyboard({k: Image.open(HERE / f"{k}.png") for k, _ in CAPTIONS}); print("storyboard rebuilt from the saved stills")
