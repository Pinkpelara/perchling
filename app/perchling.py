"""Perchlings desktop pet, version 0.

A frameless always-on-top window that plays pre-rendered 3D frames of one pet.
The pet wanders along the taskbar, can be dragged, tickled, told to do tricks,
sulks when ignored, remembers when you usually log in, celebrates birthdays,
and wears what you pick for it in the closet.

Run:   python app/perchling.py            (system Python 3.12 with Pillow)
       python app/perchling.py --pet antenna --selftest
       Perchlings.exe                       (the packaged download; asks which pet you adopted the first time)
Quit:  right-click the pet, Quit.
"""
import argparse, ctypes, json, os, random, statistics, subprocess, sys, time
from ctypes import wintypes
from datetime import date, datetime
from pathlib import Path
import tkinter as tk
from tkinter import simpledialog
from PIL import Image, ImageTk

VERSION = "0.2.0"
FROZEN = bool(getattr(sys, "frozen", False))                   # True inside the PyInstaller build
ROOT = Path(getattr(sys, "_MEIPASS", "")) if FROZEN else Path(__file__).resolve().parent.parent
SPRITES = ROOT / "assets" / "sprites"
SPECIES_DIR = ROOT / "app" / "species"
CLOSET = json.loads((ROOT / "app" / "closet.json").read_text(encoding="utf-8"))
PET_ORDER = ["antenna", "ears", "leaf", "horns"]       # Teal, Pink, Green, Gold, the order used everywhere
COLORKEY = "#ff00ff"
COLORKEY_RGB = (255, 0, 255)
ALPHA_CUT = 110          # alpha at or above this is drawn; below is see-through
TICK_MS = 50


# ---------------------------------------------------------------- state
def state_path(pet_id):
    """One file per pet. The first build kept a single state.json; that one belongs to Teal."""
    base = Path(os.environ.get("APPDATA", str(Path.home()))) / "Perchlings"
    base.mkdir(parents=True, exist_ok=True)
    p = base / f"{pet_id}.json"
    old = base / "state.json"
    if not p.exists() and old.exists() and pet_id == "antenna":
        old.rename(p)
    return p


def load_state(species):
    p = state_path(species["id"])
    st = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    st.setdefault("pet", species["id"])
    st.setdefault("name", species["label"])
    st.setdefault("adopted", date.today().isoformat())
    st.setdefault("picks", list(species.get("default_picks", []))[:5])
    st.setdefault("birthday", None)           # owner's, "MM-DD", optional
    st.setdefault("attention", 70)            # 0..100, drops while ignored
    st.setdefault("last_seen", None)
    st.setdefault("logins", {})               # weekday -> ["HH:MM", ...]
    st.setdefault("x", None)
    st.setdefault("wearing", {})              # shelf -> item id, e.g. {"hat": "beanie"}
    return st


def save_state(st):
    state_path(st["pet"]).write_text(json.dumps(st, indent=1), encoding="utf-8")


def startup_cmd(pet_id):
    """A tiny .cmd in the owner's Startup folder starts the pet with Windows. No admin rights needed."""
    return Path(os.environ.get("APPDATA", str(Path.home()))) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / f"Perchling-{pet_id}.cmd"


def set_starts_with_windows(pet_id, on):
    p = startup_cmd(pet_id)
    if on:
        p.parent.mkdir(parents=True, exist_ok=True)
        nl = chr(10)                      # text mode turns this into a Windows line break
        p.write_text(f'@echo off{nl}start "" {launch_command(pet_id)}{nl}', encoding="utf-8")
    elif p.exists():
        p.unlink()


def launch_command(pet_id):
    """How to start one pet from a shell: the exe itself, or pythonw + this file."""
    if FROZEN:
        return f'"{sys.executable}" --pet {pet_id}'
    pyw = Path(sys.executable).with_name("pythonw.exe")
    if not pyw.exists():
        pyw = Path(sys.executable)
    return f'"{pyw}" "{Path(__file__).resolve()}" --pet {pet_id}'


def species_ids():
    ids = sorted(p.stem for p in SPECIES_DIR.glob("*.json"))
    return [i for i in PET_ORDER if i in ids] + [i for i in ids if i not in PET_ORDER]


def load_species(pet_id):
    return json.loads((SPECIES_DIR / f"{pet_id}.json").read_text(encoding="utf-8"))


def adopted_ids():
    base = state_path("antenna").parent
    return [pid for pid in species_ids() if (base / f"{pid}.json").exists()]


def be_dpi_aware():
    """Draw at the screen's real pixel size instead of letting Windows blow up a small window. Returns the scale (1.5 on a 150% screen)."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        pass
    try:
        return ctypes.windll.user32.GetDpiForSystem() / 96.0
    except (AttributeError, OSError):
        return 1.0


SCALE = be_dpi_aware()


def window_icon(root):
    """The Teal head as the title-bar icon of the small windows that have one."""
    try:
        im = Frames("antenna", 64).compose("happy", "idle", 0).crop((60, 8, 196, 144)).resize((64, 64), Image.LANCZOS)
        root.icon_img = ImageTk.PhotoImage(im); root.iconphoto(True, root.icon_img)
    except Exception:
        pass


def work_area():
    """Screen rectangle minus the taskbar (left, top, right, bottom)."""
    rect = wintypes.RECT()
    if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
        return rect.left, rect.top, rect.right, rect.bottom
    return 0, 0, 1280, 720


# ---------------------------------------------------------------- frames
class Frames:
    """Crops frames out of the sprite sheets, lays closet items on top, and keys the result onto the colour-key background.

    Closet items are separate sheets (assets/sprites/<pet>/outfits/<item>_sheet.png) rendered with the pet
    hiding what it should but painting nothing, so laying an item frame over the pet frame looks right.
    """

    def __init__(self, pet_id, display_px):
        self.folder = SPRITES / pet_id
        self.sheet = Image.open(self.folder / f"{pet_id}_sheet.png").convert("RGBA")
        self.index = json.loads((self.folder / f"{pet_id}_sheet.json").read_text())["frames"]
        self.size = display_px
        self.cache = {}
        self.layers = {}

    def has_item(self, item_id):
        return (self.folder / "outfits" / f"{item_id}_sheet.json").exists()

    def _layer(self, item_id):
        if item_id not in self.layers:
            d = self.folder / "outfits"
            sheet = Image.open(d / f"{item_id}_sheet.png").convert("RGBA")
            index = json.loads((d / f"{item_id}_sheet.json").read_text())["frames"]
            self.layers[item_id] = (sheet, index)
        return self.layers[item_id]

    @staticmethod
    def _crop(sheet, index, key):
        f = index[key]
        return sheet.crop((f["x"], f["y"], f["x"] + f["w"], f["y"] + f["h"]))

    def compose(self, mood, pose, yaw, wearing=None):
        """The pet with its outfit on, full sheet size, see-through background."""
        key = f"{mood}_{pose}_{yaw:03d}"
        if key not in self.index:
            key = self._fallback(mood, pose, yaw)
        im = self._crop(self.sheet, self.index, key)
        for item_id in (wearing or {}).values():
            if not item_id or not self.has_item(item_id):
                continue
            sheet, index = self._layer(item_id)
            lk = f"{'idle' if pose in ('blink', 'wave1', 'wave2') else pose}_{yaw:03d}"     # blinks and waves leave the head where it is
            for k in (lk, f"idle_{yaw:03d}", "idle_000"):
                if k in index:
                    im = im.copy(); im.alpha_composite(self._crop(sheet, index, k)); break
        return im

    def get(self, mood, pose, yaw, wearing=None):
        worn = tuple(sorted(v for v in (wearing or {}).values() if v))
        ck = (mood, pose, yaw, worn)
        if ck not in self.cache:
            im = self.compose(mood, pose, yaw, wearing).resize((self.size, self.size), Image.LANCZOS)
            mask = im.getchannel("A").point(lambda a: 255 if a >= ALPHA_CUT else 0)
            out = Image.new("RGB", im.size, COLORKEY_RGB)
            out.paste(im.convert("RGB"), mask=mask)
            self.cache[ck] = ImageTk.PhotoImage(out)
        return self.cache[ck]

    def _fallback(self, mood, pose, yaw):
        for k in (f"{mood}_idle_{yaw:03d}", f"happy_{pose}_{yaw:03d}", f"happy_idle_{yaw:03d}", "happy_idle_000"):
            if k in self.index:
                return k
        return next(iter(self.index))


# ---------------------------------------------------------------- the pet
class Pet:
    def __init__(self, species, selftest=False):
        self.sp = species
        self.st = load_state(species)
        self.size = round(species.get("display_px", 128) * SCALE)
        self.frames = Frames(species["id"], self.size)
        self.selftest = selftest

        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", COLORKEY)
        self.root.configure(bg=COLORKEY)
        self.label = tk.Label(self.root, bg=COLORKEY, bd=0, highlightthickness=0)
        self.label.pack()

        left, top, right, bottom = work_area()
        self.area = (left, top, right, bottom)
        self.floor = bottom - self.size + 8          # feet just above the taskbar
        self.x = self.st["x"] if self.st["x"] is not None else (left + right) // 2 - self.size // 2
        self.y = self.floor
        self.vx = 0.0
        self.facing = 1                                # 1 right, -1 left
        self.mood = "happy"
        self.state = "idle"                            # idle | walk | sleep | sulk | held | routine
        self.until = time.time() + 2
        self.routine = []
        self.anim_t = 0
        self.blink_at = time.time() + random.uniform(2, 5)
        self.blink_until = 0
        self.bubble = None
        self.drag = None
        self.last_frame = ("happy", "idle", 0)
        self.last_attention_tick = time.time()
        self.autostart = tk.BooleanVar(value=startup_cmd(species["id"]).exists())

        self.label.bind("<ButtonPress-1>", self.on_press)
        self.label.bind("<B1-Motion>", self.on_drag)
        self.label.bind("<ButtonRelease-1>", self.on_release)
        self.label.bind("<Button-3>", self.on_menu)

        self.arrive()
        self.place()
        self.root.after(TICK_MS, self.tick)

    # --- arrival: habits, birthdays, sulking carried over
    def arrive(self):
        now = datetime.now()
        wd = str(now.weekday())
        hhmm = now.strftime("%H:%M")
        log = self.st["logins"].setdefault(wd, [])
        usual = self._usual_minutes(log)
        log.append(hhmm); del log[:-10]

        last = self.st.get("last_seen")
        days_away = (now - datetime.fromisoformat(last)).days if last else 0
        self.st["last_seen"] = now.isoformat(timespec="minutes")
        self.st["attention"] = max(0, self.st["attention"] - 8 * max(0, days_away - 1))

        msg = None
        today = now.strftime("%m-%d")
        if self.st.get("birthday") == today:
            msg = "It's your birthday."
            self.queue_routine(self._bounce_steps(10))
        elif self.st["adopted"][5:] == today and self.st["adopted"] != date.today().isoformat():
            msg = "It's my adoption day."
            self.queue_routine(self._bounce_steps(10))
        elif days_away >= 3:
            msg = f"You were gone {days_away} days."
            self.mood = "sulky"; self.state = "sulk"; self.until = time.time() + 20
        elif usual is not None and abs(now.hour * 60 + now.minute - usual) <= 30:
            msg = "Right on time."
        else:
            msg = f"{self.st['name']} is here."
        save_state(self.st)
        self.root.after(600, lambda: self.say(msg))
        if "wave" in self.st["picks"] and self.state != "sulk":
            self.root.after(3400, lambda: self.state == "idle" and self.do_trick("wave"))

    @staticmethod
    def _usual_minutes(log):
        if len(log) < 3:
            return None
        mins = [int(h) * 60 + int(m) for h, m in (s.split(":") for s in log)]
        return statistics.median(mins)

    # --- geometry
    def place(self):
        self.root.geometry(f"{self.size}x{self.size}+{int(self.x)}+{int(self.y)}")

    def show(self, mood, pose, yaw):
        self.last_frame = (mood, pose, yaw)
        self.label.configure(image=self.frames.get(mood, pose, yaw, self.st["wearing"]))

    # --- speech bubble
    def say(self, text, ms=2600):
        self.unsay()
        b = tk.Toplevel(self.root)
        b.overrideredirect(True); b.attributes("-topmost", True)
        lbl = tk.Label(b, text=text, bg="#fff8f0", fg="#23213B", font=("Segoe UI", 10, "bold"), padx=10, pady=5,
                       relief="flat", highlightthickness=1, highlightbackground="#d8cfe8")
        lbl.pack()
        b.update_idletasks()
        bx = int(self.x + self.size // 2 - b.winfo_reqwidth() // 2)
        by = int(self.y - b.winfo_reqheight() - 6)
        b.geometry(f"+{max(self.area[0], bx)}+{max(self.area[1], by)}")
        self.bubble = b
        self.root.after(ms, self.unsay)

    def unsay(self):
        if self.bubble is not None:
            try: self.bubble.destroy()
            except tk.TclError: pass
            self.bubble = None

    # --- input
    def on_press(self, e):
        self.drag = (e.x_root, e.y_root, self.x, self.y, False)
        self.unsay()

    def on_drag(self, e):
        if not self.drag: return
        sx, sy, ox, oy, _ = self.drag
        dx, dy = e.x_root - sx, e.y_root - sy
        if abs(dx) + abs(dy) > 4:
            self.drag = (sx, sy, ox, oy, True)
            self.state = "held"; self.routine = []
            self.x, self.y = ox + dx, oy + dy
            self.place(); self.show("surprised", "idle", 0)

    def on_release(self, e):
        if not self.drag: return
        moved = self.drag[4]; self.drag = None
        if moved:
            # fall to the floor with a little squash
            self.queue_routine([("surprised", "stretch", 0, 0, 0, 60)] + [("surprised", "idle", 0, 0, step, 30) for step in self._fall_steps()]
                               + [("happy", "squash", 0, 0, 0, 120), ("happy", "idle", 0, 0, 0, 80)])
            self.st["x"] = int(self.x)
        else:
            self.tickle()

    def tickle(self):
        self.st["attention"] = min(100, self.st["attention"] + 35)
        self.mood = "happy"
        self.queue_routine([("happy", "squash", 0, 0, 0, 90), ("happy", "stretch", 0, 0, -10, 110), ("happy", "idle", 0, 0, 10, 90),
                            ("happy", "squash", 0, 0, 0, 90), ("happy", "stretch", 0, 0, -8, 110), ("happy", "idle", 0, 0, 8, 200)])
        self.say(random.choice(["Hehe.", "That tickles.", "Again."]))
        save_state(self.st)

    def _fall_steps(self):
        steps, y = [], self.y
        while y < self.floor:
            ny = min(self.floor, y + 14); steps.append(ny - y); y = ny
        return steps or [0]

    # --- menu
    def on_menu(self, e):
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label=self.st["name"], state="disabled")
        m.add_separator()
        m.add_command(label="Tickle", command=self.tickle)
        tricks = tk.Menu(m, tearoff=0)
        picked = set(self.st["picks"])
        for t in self.sp["catalog"]["tricks"]:
            if t["id"] in picked:
                tricks.add_command(label=t["name"], command=lambda tid=t["id"]: self.do_trick(tid))
        m.add_cascade(label="Tricks", menu=tricks)
        m.add_command(label="Pick five...", command=self.pick_dialog)
        m.add_command(label="Closet...", command=self.closet_dialog)
        m.add_command(label="Rename...", command=self.rename)
        m.add_command(label="Set your birthday...", command=self.set_birthday)
        m.add_checkbutton(label="Start with Windows", variable=self.autostart, command=self.toggle_autostart)
        m.add_separator()
        m.add_command(label="Quit", command=self.quit)
        m.add_command(label=f"Perchlings {VERSION}", state="disabled")
        m.tk_popup(e.x_root, e.y_root)

    def toggle_autostart(self):
        try:
            set_starts_with_windows(self.sp["id"], self.autostart.get())
            self.say("See you tomorrow." if self.autostart.get() else "Okay.")
        except OSError:
            self.autostart.set(not self.autostart.get()); self.say("Couldn't change that.")

    def rename(self):
        name = simpledialog.askstring("Name", "What will you call them?", initialvalue=self.st["name"], parent=self.root)
        if name and name.strip():
            self.st["name"] = name.strip()[:24]; save_state(self.st); self.say(f"I'm {self.st['name']}.")

    def set_birthday(self):
        v = simpledialog.askstring("Your birthday", "Month and day, like 03-21 (kept on this computer only):",
                                   initialvalue=self.st.get("birthday") or "", parent=self.root)
        if v is None: return
        v = v.strip()
        if v == "": self.st["birthday"] = None
        elif len(v) == 5 and v[2] == "-" and v[:2].isdigit() and v[3:].isdigit(): self.st["birthday"] = v
        else: self.say("Use MM-DD, like 03-21."); return
        save_state(self.st); self.say("Got it.")

    def pick_dialog(self):
        win = tk.Toplevel(self.root); win.title("Pick five"); win.attributes("-topmost", True); window_icon(win)
        win.geometry(f"+{int(self.x)}+{max(self.area[1], int(self.y) - 320)}")
        tk.Label(win, text=f"Choose up to five things {self.st['name']} can do.", font=("Segoe UI", 10, "bold")).pack(padx=14, pady=(12, 6), anchor="w")
        vars_ = {}
        for group in ("tricks", "behaviours", "gadgets"):
            items = self.sp["catalog"].get(group, [])
            if not items: continue
            tk.Label(win, text=group.capitalize(), fg="#5A3FC0", font=("Segoe UI", 9, "bold")).pack(padx=14, pady=(6, 0), anchor="w")
            for it in items:
                v = tk.BooleanVar(value=it["id"] in self.st["picks"]); vars_[it["id"]] = v
                tk.Checkbutton(win, text=it["name"], variable=v, anchor="w").pack(padx=24, anchor="w")
        note = tk.Label(win, text="", fg="#B4453A"); note.pack(padx=14, pady=(4, 0), anchor="w")

        def ok():
            chosen = [k for k, v in vars_.items() if v.get()]
            if len(chosen) > 5:
                note.configure(text=f"That's {len(chosen)}. Five is the limit."); return
            self.st["picks"] = chosen; save_state(self.st); win.destroy(); self.say("New tricks.")
        tk.Button(win, text="Save", command=ok, padx=14).pack(pady=12)

    def closet_dialog(self):
        """Owned items on the left, the pet trying them on on the right. Every click goes straight onto the desktop pet too."""
        win = tk.Toplevel(self.root); win.title("Closet"); win.attributes("-topmost", True); window_icon(win)
        win.configure(bg="#FFF8F0")
        win.geometry(f"+{max(self.area[0], int(self.x) - 120)}+{max(self.area[1], int(self.y) - 360)}")
        left = tk.Frame(win, bg="#FFF8F0"); left.pack(side="left", fill="y", padx=(16, 8), pady=12, anchor="n")
        right = tk.Frame(win, bg="#FFF8F0"); right.pack(side="left", padx=(8, 16), pady=12, anchor="n")
        tk.Label(left, text=f"{self.st['name']}'s closet", bg="#FFF8F0", fg="#23213B", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 6))
        preview = tk.Label(right, bg="#FFF8F0", bd=0); preview.pack()
        tk.Label(right, text="Click an item and look at your desktop.", bg="#FFF8F0", fg="#6B6685", font=("Segoe UI", 9)).pack(pady=(4, 0))

        def refresh():
            im = self.frames.compose("happy", "idle", 0, self.st["wearing"])
            bg = Image.new("RGBA", im.size, (255, 248, 240, 255)); bg.alpha_composite(im)
            px = round(192 * SCALE)
            preview.img = ImageTk.PhotoImage(bg.resize((px, px), Image.LANCZOS))
            preview.configure(image=preview.img)
            self.show(*self.last_frame)

        choices = {}
        for shelf in CLOSET["shelves"]:
            items = [it for it in shelf["items"] if self.frames.has_item(it["id"])]
            if not items:
                continue
            v = tk.StringVar(value=self.st["wearing"].get(shelf["id"]) or ""); choices[shelf["id"]] = v
            tk.Label(left, text=shelf["name"], bg="#FFF8F0", fg="#5A3FC0", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(6, 0))

            def pick(shelf_id=shelf["id"], var=v):
                self.st["wearing"][shelf_id] = var.get() or None
                save_state(self.st); refresh()
            for text, val in [("Nothing", "")] + [(it["name"], it["id"]) for it in items]:
                tk.Radiobutton(left, text=text, value=val, variable=v, command=pick, bg="#FFF8F0", activebackground="#FFF8F0",
                               anchor="w", font=("Segoe UI", 10)).pack(anchor="w", padx=8)
        if not choices:
            tk.Label(left, text="Nothing here yet.", bg="#FFF8F0", fg="#6B6685").pack(anchor="w")
        tk.Button(left, text="Close", command=win.destroy, padx=14).pack(anchor="w", pady=(14, 0))
        refresh()

    def quit(self):
        self.st["x"] = int(self.x); save_state(self.st); self.unsay(); self.root.destroy()

    # --- tricks (routines are lists of (mood, pose, yaw, dx, dy, ms))
    def queue_routine(self, steps):
        self.routine = list(steps); self.state = "routine"; self.anim_t = 0

    def _bounce_steps(self, n):
        out = []
        for _ in range(n):
            out += [("happy", "squash", 0, 0, 0, 80), ("happy", "stretch", 0, 0, -14, 90), ("happy", "idle", 0, 0, 14, 90)]
        return out

    def do_trick(self, tid):
        if tid == "bounce":
            self.queue_routine(self._bounce_steps(5))
        elif tid == "peekaboo":
            down = [("happy", "idle", 0, 0, 12, 30)] * 10
            up = [("surprised", "idle", 0, 0, -12, 30)] * 10
            self.queue_routine(down + [("happy", "idle", 0, 0, 0, 900)] + up + [("happy", "stretch", 0, 0, 0, 150), ("happy", "idle", 0, 0, 0, 100)])
            self.root.after(1500, lambda: self.say("Peekaboo."))
        elif tid == "zoomies":
            steps = []
            for leg in (1, -1, 1, -1):
                yaw = 60 if leg > 0 else 300
                for i in range(14):
                    steps.append(("happy", "walk1" if i % 2 == 0 else "walk2", yaw, 22 * leg, 0, 45))
            self.queue_routine(steps + [("happy", "squash", 0, 0, 0, 150), ("happy", "idle", 0, 0, 0, 100)])
        elif tid == "nap":
            self.mood = "sleepy"; self.state = "sleep"; self.until = time.time() + 25; self.routine = []
        elif tid == "sit":
            self.queue_routine([("happy", "sit", 0, 0, 0, 1800), ("happy", "sit", 0, 0, 0, 140), ("happy", "sit", 0, 0, 0, 1600),
                                ("happy", "squash", 0, 0, 0, 120), ("happy", "idle", 0, 0, 0, 100)])
        elif tid == "lie":
            self.queue_routine([("happy", "squash", 0, 0, 0, 120), ("happy", "lie", 0, 0, 0, 700), ("sleepy", "lie", 0, 0, 0, 2600),
                                ("happy", "lie", 0, 0, 0, 500), ("happy", "squash", 0, 0, 0, 120), ("happy", "idle", 0, 0, 0, 100)])
        elif tid == "spin":
            turn = [("happy", "idle", y, 0, 0, 70) for y in (0, 60, 120, 180, 240, 300)]
            self.queue_routine(turn * 2 + [("surprised", "idle", 0, 0, 0, 300), ("happy", "squash", 0, 0, 0, 120), ("happy", "idle", 0, 0, 0, 100)])
        elif tid == "wave":
            self.queue_routine([("happy", "wave1", 0, 0, 0, 170), ("happy", "wave2", 0, 0, 0, 170)] * 4 + [("happy", "idle", 0, 0, 0, 100)])
            self.root.after(300, lambda: self.say("Hi."))
        self.st["attention"] = min(100, self.st["attention"] + 10)

    # --- the loop
    def tick(self):
        now = time.time()
        # attention drifts down while the pet is ignored; below 30 it sulks
        if now - self.last_attention_tick > 60:
            self.last_attention_tick = now
            self.st["attention"] = max(0, self.st["attention"] - (2 if "clingy" in self.st["picks"] else 1))
            if self.st["attention"] < 30 and self.state in ("idle", "walk"):
                self.mood = "sulky"; self.state = "sulk"; self.until = now + 40
                self.say(random.choice(["Hmph.", "...", "You forgot me."]))
            save_state(self.st)

        if self.state == "held":
            pass
        elif self.state == "routine":
            self._run_routine()
        else:
            if now > self.until:
                self._choose()
            if self.state == "walk":
                self.x += self.vx
                if self.x < self.area[0]: self.x = self.area[0]; self.facing = 1; self.vx = abs(self.vx)
                if self.x > self.area[2] - self.size: self.x = self.area[2] - self.size; self.facing = -1; self.vx = -abs(self.vx)
                self.y = self.floor
                self.place()
                self.anim_t += 1
                self.show("happy", "walk1" if (self.anim_t // 4) % 2 == 0 else "walk2", 60 if self.facing > 0 else 300)
            elif self.state == "sleep":
                self.anim_t += 1
                self.show("sleepy", "squash" if (self.anim_t // 24) % 2 == 0 else "idle", 0)
            elif self.state == "sulk":            # back turned; a quick look over the shoulder now and then
                self.anim_t += 1
                self.show("sulky", "idle", 0 if (self.anim_t // 20) % 6 == 5 else 180)
            else:  # idle: breathe, blink, glance
                self.anim_t += 1
                if "clingy" in self.st["picks"] and self.anim_t % 3 == 0:
                    px = self.root.winfo_pointerx() - self.size // 2
                    if abs(px - self.x) > 40:
                        self.x += 2 if px > self.x else -2; self.place()
                pose = "idle"
                phase = (self.anim_t // 16) % 4
                if phase == 1: pose = "squash"
                if phase == 3: pose = "stretch"
                if now > self.blink_at:
                    self.blink_until = now + 0.14; self.blink_at = now + random.uniform(2.5, 6)
                if now < self.blink_until: pose = "blink"
                self.show(self.mood, pose, 0)

        if self.selftest:
            self._selftest_ticks = getattr(self, "_selftest_ticks", 0) + 1
            if self._selftest_ticks > 40:
                print("selftest ok: window up, frames drawn, loop running"); self.root.destroy(); return
        self.root.after(TICK_MS, self.tick)

    def _run_routine(self):
        if not self.routine:
            self.state = "idle"; self.until = time.time() + 1.5; self.y = min(self.y, self.floor); self.place(); return
        mood, pose, yaw, dx, dy, ms = self.routine[0]
        if self.anim_t == 0:
            self.x += dx; self.y += dy
            self.x = max(self.area[0], min(self.area[2] - self.size, self.x))
            self.place(); self.show(mood, pose, yaw)
        self.anim_t += TICK_MS
        if self.anim_t >= ms:
            self.routine.pop(0); self.anim_t = 0

    def _choose(self):
        picks = set(self.st["picks"])
        w = {"idle": 40, "walk": 30, "sleep": 8, "trick": 4}
        if "calm" in picks: w["walk"] -= 15; w["idle"] += 15
        if "sleepy" in picks: w["sleep"] += 18
        if "showoff" in picks: w["trick"] += 14
        if self.mood == "sulky" and self.st["attention"] >= 30: self.mood = "happy"
        if self.mood == "sulky": w = {"idle": 60, "walk": 10, "sleep": 10, "trick": 0}
        roll = random.uniform(0, sum(w.values())); pick = "idle"
        for k, v in w.items():
            roll -= v
            if roll <= 0: pick = k; break
        if pick == "trick":
            tricks = [t for t in ("bounce", "peekaboo", "zoomies", "sit", "lie", "spin", "wave") if t in picks]
            if tricks: self.do_trick(random.choice(tricks)); return
            pick = "idle"
        self.state = pick if pick != "trick" else "idle"
        if pick == "walk":
            self.facing = random.choice((1, -1)); self.vx = self.facing * random.uniform(1.2, 2.2)
            self.until = time.time() + random.uniform(2, 6)
        elif pick == "sleep":
            self.mood = "sleepy"; self.until = time.time() + random.uniform(8, 20)
        else:
            if self.mood == "sleepy": self.mood = "happy"
            self.until = time.time() + random.uniform(2, 5)
        self.anim_t = 0


# ---------------------------------------------------------------- first run
CREAM = "#FFF8F0"


def adoption_window():
    """Which pet, what name, which five. Returns the chosen pet id, or None if the window was closed."""
    root = tk.Tk(); root.title("Perchlings"); root.configure(bg=CREAM); root.resizable(False, False)
    root.attributes("-topmost", True); window_icon(root)
    chosen = {"pet": None}
    ids = species_ids()
    species = {pid: load_species(pid) for pid in ids}
    stills = {}
    px = round(112 * SCALE)
    for pid in ids:
        im = Frames(pid, px).compose("happy", "idle", 0)
        bg = Image.new("RGBA", im.size, (255, 248, 240, 255)); bg.alpha_composite(im)
        stills[pid] = ImageTk.PhotoImage(bg.resize((px, px), Image.LANCZOS))

    tk.Label(root, text="Which one did you adopt?", bg=CREAM, fg="#23213B", font=("Segoe UI", 14, "bold")).pack(padx=24, pady=(18, 8), anchor="w")
    row = tk.Frame(root, bg=CREAM); row.pack(padx=20)
    picked = tk.StringVar(value=ids[0])
    cards = {}
    for pid in ids:
        card = tk.Frame(row, bg="#FFFFFF", highlightthickness=2, highlightbackground="#E8DFF3", cursor="hand2")
        card.pack(side="left", padx=4)
        tk.Label(card, image=stills[pid], bg="#FFFFFF", bd=0).pack(padx=6, pady=(6, 0))
        tk.Label(card, text=species[pid]["label"], bg="#FFFFFF", fg="#23213B", font=("Segoe UI", 10, "bold")).pack(pady=(0, 6))
        cards[pid] = card
        for w in (card, *card.winfo_children()):
            w.bind("<Button-1>", lambda e, pid=pid: picked.set(pid))

    form = tk.Frame(root, bg=CREAM); form.pack(padx=24, pady=(14, 0), fill="x")
    tk.Label(form, text="Its name", bg=CREAM, fg="#5A3FC0", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w")
    name = tk.Entry(form, font=("Segoe UI", 11), width=26); name.grid(row=1, column=0, sticky="w", pady=(2, 0))
    tk.Label(form, text="Pick 5 things it can do", bg=CREAM, fg="#5A3FC0", font=("Segoe UI", 9, "bold")).grid(row=0, column=1, sticky="w", padx=(30, 0))
    picks_box = tk.Frame(form, bg=CREAM); picks_box.grid(row=1, column=1, rowspan=6, sticky="nw", padx=(30, 0))
    note = tk.Label(root, text="", bg=CREAM, fg="#B4453A", font=("Segoe UI", 9)); note.pack(padx=24, anchor="w")
    tk.Label(root, text="You can change all of this later from the pet's right-click menu.", bg=CREAM, fg="#6B6685", font=("Segoe UI", 9)).pack(padx=24, pady=(6, 0), anchor="w")
    vars_ = {}

    def fill_picks(*_):
        pid = picked.get()
        for p_, c in cards.items():
            c.configure(highlightbackground="#5A3FC0" if p_ == pid else "#E8DFF3")
        for w in picks_box.winfo_children():
            w.destroy()
        vars_.clear()
        sp = species[pid]
        col = 0
        for group in ("tricks", "behaviours", "gadgets"):
            items = sp["catalog"].get(group, [])
            if not items:
                continue
            f = tk.Frame(picks_box, bg=CREAM); f.grid(row=0, column=col, sticky="nw", padx=(0, 14)); col += 1
            tk.Label(f, text=group.capitalize(), bg=CREAM, fg="#6B6685", font=("Segoe UI", 8, "bold")).pack(anchor="w")
            for it in items:
                v = tk.BooleanVar(value=it["id"] in sp.get("default_picks", [])); vars_[it["id"]] = v
                tk.Checkbutton(f, text=it["name"], variable=v, bg=CREAM, activebackground=CREAM, anchor="w", font=("Segoe UI", 9)).pack(anchor="w")
        if not name.get().strip() or name.get().strip() in (s_["label"] for s_ in species.values()):
            name.delete(0, "end"); name.insert(0, sp["label"])
        note.configure(text="")
    picked.trace_add("write", fill_picks)
    fill_picks()

    def adopt():
        pid = picked.get()
        picks = [k for k, v in vars_.items() if v.get()]
        if len(picks) > 5:
            note.configure(text=f"That's {len(picks)}. Five is the limit."); return
        st = load_state(species[pid])
        st["name"] = (name.get().strip() or species[pid]["label"])[:24]
        st["picks"] = picks
        save_state(st)
        chosen["pet"] = pid
        root.destroy()
    tk.Button(root, text="Adopt", command=adopt, bg="#5A3FC0", fg="#FFFFFF", activebackground="#4A32A6", activeforeground="#FFFFFF",
              font=("Segoe UI", 11, "bold"), relief="flat", padx=26, pady=6, cursor="hand2").pack(pady=(14, 20))
    root.update_idletasks()
    w, h = root.winfo_reqwidth(), root.winfo_reqheight()
    root.geometry(f"+{(root.winfo_screenwidth() - w) // 2}+{(root.winfo_screenheight() - h) // 2 - 40}")
    root.mainloop()
    return chosen["pet"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pet", default=None, help="which pet to start; without it, adopted pets start (or the adoption window opens)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    pet_id = a.pet
    if pet_id is None:
        adopted = adopted_ids()
        if adopted:
            pet_id, others = adopted[0], adopted[1:]
            for other in others:                      # every adopted pet gets its own window and process
                subprocess.Popen(launch_command(other), shell=True)
        else:
            pet_id = adoption_window()
            if pet_id is None:
                return
    pet = Pet(load_species(pet_id), selftest=a.selftest)
    pet.root.mainloop()


if __name__ == "__main__":
    main()
