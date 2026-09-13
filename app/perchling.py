"""Perchlings desktop pet, version 0.

A frameless always-on-top window that plays pre-rendered 3D frames of one pet.
The pet wanders along the taskbar, can be dragged, tickled, told to do tricks,
sulks when ignored, remembers when you usually log in, celebrates birthdays,
and wears what you pick for it in the closet.

Run:   python app/perchling.py            (system Python 3.12 with Pillow)
       python app/perchling.py --pet antenna --selftest
Quit:  right-click the pet, Quit.
"""
import argparse, ctypes, json, os, random, statistics, sys, time
from ctypes import wintypes
from datetime import date, datetime
from pathlib import Path
import tkinter as tk
from tkinter import simpledialog
from PIL import Image, ImageTk

ROOT = Path(__file__).resolve().parent.parent
SPRITES = ROOT / "assets" / "sprites"
SPECIES_DIR = ROOT / "app" / "species"
CLOSET = json.loads((ROOT / "app" / "closet.json").read_text(encoding="utf-8"))
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
        pyw = Path(sys.executable).with_name("pythonw.exe")
        if not pyw.exists():
            pyw = Path(sys.executable)
        p.parent.mkdir(parents=True, exist_ok=True)
        nl = chr(10)                      # text mode turns this into a Windows line break
        p.write_text(f'@echo off{nl}start "" "{pyw}" "{Path(__file__).resolve()}" --pet {pet_id}{nl}', encoding="utf-8")
    elif p.exists():
        p.unlink()


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
            lk = f"{'idle' if pose == 'blink' else pose}_{yaw:03d}"     # a blink moves nothing but the eyes
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
        self.size = species.get("display_px", 128)
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
        win = tk.Toplevel(self.root); win.title("Pick five"); win.attributes("-topmost", True)
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
        win = tk.Toplevel(self.root); win.title("Closet"); win.attributes("-topmost", True)
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
            preview.img = ImageTk.PhotoImage(bg.resize((192, 192), Image.LANCZOS))
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
            elif self.state == "sulk":
                self.show("sulky", "idle", 0)
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
            tricks = [t for t in ("bounce", "peekaboo", "zoomies") if t in picks]
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pet", default="antenna"); ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    species = json.loads((SPECIES_DIR / f"{a.pet}.json").read_text(encoding="utf-8"))
    pet = Pet(species, selftest=a.selftest)
    pet.root.mainloop()


if __name__ == "__main__":
    main()
