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
import argparse, ctypes, json, os, random, statistics, subprocess, sys, time, urllib.parse, urllib.request, webbrowser
from ctypes import wintypes
from datetime import date, datetime, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import simpledialog
from PIL import Image, ImageTk
import household as H
import notebook as N

VERSION = "0.10.0"
FROZEN = bool(getattr(sys, "frozen", False))                   # True inside the PyInstaller build
ROOT = Path(getattr(sys, "_MEIPASS", "")) if FROZEN else Path(__file__).resolve().parent.parent
SPRITES = ROOT / "assets" / "sprites"
SPECIES_DIR = ROOT / "app" / "species"
CLOSET = json.loads((ROOT / "app" / "closet.json").read_text(encoding="utf-8"))
SHOP = json.loads((ROOT / "app" / "shop.json").read_text(encoding="utf-8"))
INCLUDED = {it["id"] for sh in CLOSET["shelves"] for it in sh["items"] if it.get("included")}
PET_ORDER = ["antenna", "ears", "leaf", "horns"]       # Teal, Pink, Green, Gold, the order used everywhere
COLORKEY = "#ff00ff"
COLORKEY_RGB = (255, 0, 255)
ALPHA_CUT = 110          # alpha at or above this is drawn; below is see-through
TICK_MS = 50
IGNORED_AFTER = 2 * 60 * 60   # no cursor on the pet for this long and it sulks
LONELY_AFTER = 60 * 60        # half way there it starts asking to play


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
    st.setdefault("reminders", [])            # [{"when": "YYYY-MM-DDTHH:MM", "text": "..."}], kept until delivered
    st.setdefault("last_touch", None)         # epoch seconds of the last time the cursor was on the pet
    st.setdefault("home", False)              # True = stays in; doesn't come out with the others
    st.setdefault("notes", [])                # [{"when": iso, "text": "..."}]: what the owner told the pet
    return st


def save_state(st):
    state_path(st["pet"]).write_text(json.dumps(st, indent=1), encoding="utf-8")


def owned_path():
    return state_path("antenna").parent / "owned.json"


def load_owned():
    p = owned_path()
    try:
        d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except (OSError, ValueError):
        d = {}
    d.setdefault("items", []); d.setdefault("codes", [])
    return d


def save_owned(d):
    owned_path().write_text(json.dumps(d, indent=1), encoding="utf-8")


def owns(item_id):
    return item_id in INCLUDED or item_id in load_owned()["items"]


def redeem_code(code):
    """Turn a purchase code into owned items. Returns (ok, message). One request to the store, nothing else."""
    code = code.strip()
    if not code:
        return False, "Type the code from your email."
    owned = load_owned()
    if code in owned["codes"]:
        return True, "That one is already yours."
    # a local list of test codes, for trying the flow before the store exists; never shipped with the app
    test = owned_path().parent / "test-codes.json"
    if test.exists():
        try:
            items = json.loads(test.read_text(encoding="utf-8")).get(code)
        except (OSError, ValueError):
            items = None
        if items:
            owned["items"] = sorted(set(owned["items"]) | set(items)); owned["codes"].append(code); save_owned(owned)
            return True, "Unlocked."
    url = SHOP.get("license_url")
    if not url or not SHOP.get("variants"):
        return False, "The shop isn't open yet."
    try:
        data = urllib.parse.urlencode({"license_key": code, "instance_name": os.environ.get("COMPUTERNAME", "pc")}).encode()
        req = urllib.request.Request(url, data=data, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=12) as r:
            reply = json.loads(r.read().decode("utf-8"))
    except Exception:
        return False, "Couldn't reach the store. Check the internet and try again."
    if not reply.get("activated") and reply.get("license_key", {}).get("status") != "active":
        return False, reply.get("error") or "That code didn't work."
    variant = str(reply.get("meta", {}).get("variant_id", ""))
    items = SHOP["variants"].get(variant)
    if not items:
        return False, "That code is for something this version doesn't know yet."
    owned["items"] = sorted(set(owned["items"]) | set(items)); owned["codes"].append(code); save_owned(owned)
    return True, "Unlocked."


def startup_folder():
    return Path(os.environ.get("APPDATA", str(Path.home()))) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def startup_cmd(pet_id):
    """A tiny .cmd in the owner's Startup folder starts the pet with Windows. No admin rights needed."""
    return startup_folder() / f"Perchling-{pet_id}.cmd"


def installer_startup_link():
    """The installer can put a shortcut here instead; it starts every adopted pet."""
    return startup_folder() / "Perchlings.lnk"


def starts_with_windows(pet_id):
    return startup_cmd(pet_id).exists() or installer_startup_link().exists()


def set_starts_with_windows(pet_id, on):
    p = startup_cmd(pet_id)
    if on:
        if installer_startup_link().exists():
            return                        # already covered for every pet
        p.parent.mkdir(parents=True, exist_ok=True)
        nl = chr(10)                      # text mode turns this into a Windows line break
        p.write_text(f'@echo off{nl}start "" {launch_command(pet_id)}{nl}', encoding="utf-8")
    else:
        for f in (p, installer_startup_link()):
            if f.exists():
                f.unlink()


def claim_instance(pet_id):
    """One window per pet. A second start of the same pet (desktop icon plus Startup, say) just exits."""
    try:
        home = str(state_path(pet_id).parent).lower()             # one instance per pet per data folder
        ctypes.windll.kernel32.CreateMutexW(None, False, f"Perchlings-{pet_id}-{abs(hash(home)) % 10**8}")
        return ctypes.windll.kernel32.GetLastError() != 183      # ERROR_ALREADY_EXISTS
    except (AttributeError, OSError):
        return True


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


def preset_pet():
    """A per-pet installer leaves a pet.txt next to the exe naming the pet that was bought."""
    f = (Path(sys.executable).parent if FROZEN else ROOT) / "pet.txt"
    try:
        pid = f.read_text(encoding="utf-8").strip()
        return pid if pid in species_ids() else None
    except OSError:
        return None


def adopted_ids():
    base = state_path("antenna").parent
    return [pid for pid in species_ids() if (base / f"{pid}.json").exists()]


def pet_state(pid):
    try:
        return json.loads(state_path(pid).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def set_home(pid, home):
    st = pet_state(pid)
    if st:
        st["home"] = bool(home); state_path(pid).write_text(json.dumps(st, indent=1), encoding="utf-8")


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
    """Main screen minus the taskbar (left, top, right, bottom)."""
    rect = wintypes.RECT()
    if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
        return rect.left, rect.top, rect.right, rect.bottom
    return 0, 0, 1280, 720


class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


def monitor_work_area(x, y):
    """The work area (screen minus taskbar) of whichever monitor holds the point x, y. Falls back to the main screen."""
    try:
        pt = wintypes.POINT(int(x), int(y))
        hmon = ctypes.windll.user32.MonitorFromPoint(pt, 2)          # MONITOR_DEFAULTTONEAREST
        info = _MONITORINFO(); info.cbSize = ctypes.sizeof(_MONITORINFO)
        if hmon and ctypes.windll.user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
            r = info.rcWork
            return r.left, r.top, r.right, r.bottom
    except (AttributeError, OSError, ValueError):
        pass
    return work_area()


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
        wearing = wearing or {}
        order = ["face", "ears", "hat"] + [k for k in wearing if k not in ("face", "ears", "hat")]   # hat drawn last, on top
        for item_id in (wearing.get(k) for k in order):
            if not item_id or not self.has_item(item_id):
                continue
            sheet, index = self._layer(item_id)
            base = {"blink": "idle", "wave1": "idle", "wave2": "idle", "study": "sit", "work": "sit", "game": "sit", "eat1": "sit", "eat2": "sit"}.get(pose, pose)
            lk = f"{base}_{yaw:03d}"     # blinks and waves leave the head where it is; the activities are all sitting
            for k in (lk, f"idle_{yaw:03d}", "idle_000"):
                if k in index:
                    im = im.copy(); im.alpha_composite(self._crop(sheet, index, k)); break
        return im

    def folder_frame(self, wearing=None, peek=False):
        """A plain desktop-style folder the pet hides behind. With peek, the top of its head shows over the edge."""
        from PIL import ImageDraw
        first = next(iter(self.index.values()))
        w, h = first["w"], first["h"]
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        if peek:
            pet = self.compose("happy", "idle", 0, wearing)
            im.alpha_composite(pet.crop((0, 6, w, h)), (0, 0))       # nudged up so the eyes clear the folder edge
        d = ImageDraw.Draw(im)
        back, front, lip = (233, 178, 66, 255), (250, 210, 96, 255), (255, 228, 140, 255)
        d.rounded_rectangle((44, 104, 214, 232), radius=14, fill=back)
        d.rounded_rectangle((44, 104, 120, 130), radius=10, fill=back)
        d.rounded_rectangle((40, 128, 218, 236), radius=14, fill=front)
        d.rounded_rectangle((40, 128, 218, 142), radius=6, fill=lip)
        return im

    def curtain_frame(self, kind="bath", phase=0):
        """A shower curtain on a rod, the pet somewhere behind it. Shower breaks blow soap bubbles over the top."""
        from PIL import ImageDraw
        import math
        first = next(iter(self.index.values()))
        w, h = first["w"], first["h"]
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        wob = math.sin(phase * 1.6) * 5                          # the curtain sways a little
        left, right, top, bottom = 46, 212, 52, 236
        d.rounded_rectangle((left - 14, top - 8, right + 14, top - 2), radius=3, fill=(120, 110, 140, 255))   # rod
        for i in range(8):                                          # rings
            x = left + 4 + i * (right - left - 8) / 7
            d.ellipse((x - 5, top - 12, x + 5, top - 2), outline=(90, 80, 110, 255), width=2)
        stripes = [(191, 227, 240, 255), (255, 255, 255, 255)]
        n = 10; sw = (right - left) / n
        for i in range(n):
            x0 = left + i * sw + wob * (i % 2 * 2 - 1) * 0.3
            d.rectangle((x0, top, x0 + sw + 1, bottom), fill=stripes[i % 2])
        d.rectangle((left, top, right, top + 4), fill=(160, 205, 225, 255))
        for i in range(n):                                          # wavy hem
            x0 = left + i * sw
            d.ellipse((x0, bottom - 8, x0 + sw, bottom + 8), fill=stripes[i % 2])
        d.line((left, top, left, bottom), fill=(150, 190, 210, 255), width=2)
        d.line((right, top, right, bottom), fill=(150, 190, 210, 255), width=2)
        if kind == "shower":
            for k, (bx, by, r) in enumerate(((70, 30, 9), (110, 18, 6), (150, 34, 11), (190, 22, 7), (130, 6, 5))):
                by = by - int((phase * 3 + k * 7) % 28)
                if by > -10:
                    d.ellipse((bx - r, by - r, bx + r, by + r), outline=(190, 220, 240, 230), width=2, fill=(230, 245, 255, 90))
                    d.ellipse((bx - r * 0.5, by - r * 0.6, bx - r * 0.1, by - r * 0.2), fill=(255, 255, 255, 220))
        elif phase % 6 < 3:                                         # a roll of paper set down outside, just so it's clear
            d.ellipse((216, 214, 240, 236), fill=(255, 255, 255, 255), outline=(200, 195, 215, 255), width=2)
            d.ellipse((224, 222, 232, 228), fill=(200, 195, 215, 255))
        return im

    def get_curtain(self, kind, phase):
        ck = ("curtain", kind, phase)
        if ck not in self.cache:
            im = self.curtain_frame(kind, phase).resize((self.size, self.size), Image.LANCZOS)
            mask = im.getchannel("A").point(lambda a: 255 if a >= ALPHA_CUT else 0)
            out = Image.new("RGB", im.size, COLORKEY_RGB); out.paste(im.convert("RGB"), mask=mask)
            self.cache[ck] = ImageTk.PhotoImage(out)
        return self.cache[ck]

    def get_folder(self, wearing=None, peek=False):
        ck = ("folder", peek, tuple(sorted(v for v in (wearing or {}).values() if v)))
        if ck not in self.cache:
            im = self.folder_frame(wearing, peek).resize((self.size, self.size), Image.LANCZOS)
            mask = im.getchannel("A").point(lambda a: 255 if a >= ALPHA_CUT else 0)
            out = Image.new("RGB", im.size, COLORKEY_RGB); out.paste(im.convert("RGB"), mask=mask)
            self.cache[ck] = ImageTk.PhotoImage(out)
        return self.cache[ck]

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

        mon = self.st.get("mon")                     # where it was last time: a point on the monitor it lived on
        left, top, right, bottom = monitor_work_area(*mon) if mon else work_area()
        self.area = (left, top, right, bottom)
        self.floor = bottom - self.size + 8          # feet just above the taskbar
        self.x = self.st["x"] if self.st["x"] is not None else (left + right) // 2 - self.size // 2
        self.x = max(left, min(right - self.size, self.x))
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
        self.next_break = time.time() + random.uniform(20 * 60, 50 * 60)      # bathroom or shower, now and then
        self.next_recall = time.time() + random.uniform(8 * 60, 20 * 60)       # brings up something you told it
        self.seen = {}                                                         # other pet -> when I last saw it
        self.next_play = time.time() + 90
        self.autostart = tk.BooleanVar(value=starts_with_windows(species["id"]))
        for shelf, item in list(self.st["wearing"].items()):
            if item and not owns(item):
                self.st["wearing"][shelf] = None

        self.label.bind("<ButtonPress-1>", self.on_press)
        self.label.bind("<B1-Motion>", self.on_drag)
        self.label.bind("<ButtonRelease-1>", self.on_release)
        self.label.bind("<Button-3>", self.on_menu)
        self.label.bind("<Enter>", self.on_hover)
        self.last_hover = 0
        self.next_nudge = 0
        if self.st.get("last_touch") is None:
            self.st["last_touch"] = time.time()          # a new pet starts out fine

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
        elif last is None and self.st["name"] == self.sp["label"]:
            msg = "Hi. Right-click me to name me."
        else:
            msg = f"{self.st['name']} is here."
        save_state(self.st)
        self.root.after(600, lambda: self.say(msg))
        self.root.after(4000, lambda: self.deliver_reminders(late=True))
        if self.st["notes"] and random.random() < 0.5:
            latest = self.st["notes"][-1]
            self.root.after(7000, lambda: not self.bubble and self.say("Last time you told me: " + (latest["text"] if len(latest["text"]) <= 70 else latest["text"][:67] + "..."), ms=5200))
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
        """A speech bubble above the pet. ms=None keeps it up until the pet is clicked."""
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
        if ms is not None:
            self.root.after(ms, self.unsay)

    def unsay(self):
        if self.bubble is not None:
            try: self.bubble.destroy()
            except tk.TclError: pass
            self.bubble = None

    # --- input
    def on_hover(self, e):
        now = time.time()
        if now - self.last_hover > 20:                  # the cursor came to visit; that counts
            self.last_hover = now; self.touched(2)

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
        if self.state == "hide" and not moved:
            self.state = "idle"; self.until = time.time() + 2; self.mood = "happy"
            self.queue_routine(self._bounce_steps(3)); self.say("Found me."); return
        if self.state == "break":
            self.say("Occupied."); return
        if self.state == "together" and not moved:      # a click ends the activity
            self.touched(10); self.stop_together(); return
        if moved:
            # dropped on another monitor? that one's taskbar is the floor from now on
            cx, cy = self.x + self.size // 2, self.y + self.size // 2
            left, top, right, bottom = monitor_work_area(cx, cy)
            self.area = (left, top, right, bottom); self.floor = bottom - self.size + 8
            self.x = max(left, min(right - self.size, self.x))
            # fall to the floor with a little squash
            self.queue_routine([("surprised", "stretch", 0, 0, 0, 60)] + [("surprised", "idle", 0, 0, step, 30) for step in self._fall_steps()]
                               + [("happy", "squash", 0, 0, 0, 120), ("happy", "idle", 0, 0, 0, 80)])
            self.remember_place()
            self.touched(20)
        else:
            self.tickle()

    def touched(self, amount):
        """The cursor was on the pet: a hover, a click, a drag, the menu. That is what "not ignored" means."""
        self.st["attention"] = min(100, self.st["attention"] + amount)
        self.st["last_touch"] = time.time()

    def ignored(self):
        last = self.st.get("last_touch")
        return last is not None and time.time() - last > IGNORED_AFTER

    def lonely(self):
        last = self.st.get("last_touch")
        return last is not None and time.time() - last > LONELY_AFTER

    def tickle(self):
        self.touched(35)
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
        self.touched(0)
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
        together = [t for t in self.sp["catalog"].get("together", []) if t["id"] in picked]
        if together:
            tg = tk.Menu(m, tearoff=0)
            for t in together:
                tg.add_command(label=t["name"], command=lambda tid=t["id"]: self.do_together(tid))
            m.add_cascade(label="Together", menu=tg)
        pets_menu = tk.Menu(m, tearoff=0)
        for pid in adopted_ids():
            pst = pet_state(pid)
            if pid == self.sp["id"]:
                pets_menu.add_command(label=f"{self.st['name']} (that's me)", state="disabled")
            else:
                out = not pst.get("home", False)
                pets_menu.add_command(label=f"{pst.get('name', pid)}: {'out' if out else 'at home'}, " + ("send home" if out else "bring out"),
                                      command=lambda pid=pid, out=out: self.toggle_pet(pid, out))
        pets_menu.add_separator()
        pets_menu.add_command(label="Adopt another...", command=self.adopt_another)
        m.add_cascade(label="Pets", menu=pets_menu)
        here = H.others(self.sp["id"], self.area)
        play = tk.Menu(m, tearoff=0)
        if here:
            kinds = list(H.KINDS) + (["parade"] if len(here) >= 2 else [])
            for k in kinds:
                play.add_command(label=H.NAMES[k], command=lambda k=k: self.play_now(k))
        else:
            play.add_command(label="No one else is out", state="disabled")
        m.add_cascade(label="Play with the others", menu=play)
        m.add_command(label="Hide", command=self.hide)
        m.add_command(label="Remind me...", command=self.remind_dialog)
        m.add_command(label="Notebook...", command=self.notebook_dialog)
        m.add_command(label="Pick five...", command=self.pick_dialog)
        m.add_command(label="Closet...", command=self.closet_dialog)
        m.add_command(label="Shop...", command=self.shop_dialog)
        m.add_command(label="Enter a code...", command=self.code_dialog)
        m.add_command(label="Rename...", command=self.rename)
        m.add_command(label=f"Let {self.st['name']} go...", command=self.let_go)
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

    def toggle_pet(self, pid, currently_out):
        """Send another pet home (it quits and won't come out next time) or bring it out now."""
        set_home(pid, currently_out)
        if currently_out:
            self.say("See you later.")               # the other pet checks its own file every 10 s and goes in by itself
        else:
            subprocess.Popen(launch_command(pid), shell=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    def adopt_another(self):
        cmd = launch_command(self.sp["id"]).rsplit(" --pet ", 1)[0] + " --adopt"
        subprocess.Popen(cmd, shell=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    def code_dialog(self):
        win = tk.Toplevel(self.root); win.title("Enter a code"); win.attributes("-topmost", True); window_icon(win); win.configure(bg=CREAM)
        win.geometry(f"+{max(self.area[0], int(self.x) - 100)}+{max(self.area[1], int(self.y) - 220)}")
        tk.Label(win, text="The code from your email", bg=CREAM, fg="#23213B", font=("Segoe UI", 11, "bold")).pack(padx=16, pady=(12, 6), anchor="w")
        e = tk.Entry(win, font=("Segoe UI", 12), width=34); e.pack(padx=16, anchor="w"); e.focus_set()
        note = tk.Label(win, text="It's checked once with the store. Nothing else leaves this computer.", bg=CREAM, fg="#6B6685", font=("Segoe UI", 9), wraplength=round(320 * SCALE), justify="left")
        note.pack(padx=16, pady=(6, 0), anchor="w")

        def go(*_):
            ok, msg = redeem_code(e.get())
            note.configure(text=msg, fg="#2E7D4F" if ok else "#B4453A")
            if ok:
                self.say(random.choice(["Ooh.", "New stuff.", "Thank you."]))
                win.after(1200, win.destroy)
        e.bind("<Return>", go)
        tk.Button(win, text="Unlock", command=go, padx=14).pack(padx=16, pady=12, anchor="w")

    def let_go(self):
        """Give the pet back. Its file goes, so it won't come out next time."""
        from tkinter import messagebox
        if not messagebox.askyesno("Let go", f"Let {self.st['name']} go? It forgets everything, and it won't come back next time.", parent=self.root):
            return
        self.unsay(); set_starts_with_windows(self.sp["id"], False)
        try:
            state_path(self.sp["id"]).unlink()
        except OSError:
            pass
        self.root.destroy()

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
        for group in ("tricks", "behaviours", "together", "gadgets"):
            items = self.sp["catalog"].get(group, [])
            if not items: continue
            tk.Label(win, text={"behaviours": "Habits"}.get(group, group.capitalize()), fg="#5A3FC0", font=("Segoe UI", 9, "bold")).pack(padx=14, pady=(6, 0), anchor="w")
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
            items = [it for it in shelf["items"] if self.frames.has_item(it["id"]) and owns(it["id"])]
            locked = [it for it in shelf["items"] if self.frames.has_item(it["id"]) and not owns(it["id"])]
            if not items and not locked:
                continue
            v = tk.StringVar(value=self.st["wearing"].get(shelf["id"]) or ""); choices[shelf["id"]] = v
            tk.Label(left, text=shelf["name"], bg="#FFF8F0", fg="#5A3FC0", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(6, 0))

            def pick(shelf_id=shelf["id"], var=v):
                self.st["wearing"][shelf_id] = var.get() or None
                save_state(self.st); refresh()
            for text, val in [("Nothing", "")] + [(it["name"], it["id"]) for it in items]:
                tk.Radiobutton(left, text=text, value=val, variable=v, command=pick, bg="#FFF8F0", activebackground="#FFF8F0",
                               anchor="w", font=("Segoe UI", 10)).pack(anchor="w", padx=8)
            for it in locked:
                price = SHOP["items"].get(it["id"], {}).get("price", "")
                tk.Label(left, text=f"{it['name']}, {price} in the shop", bg="#FFF8F0", fg="#A29DB8", font=("Segoe UI", 9)).pack(anchor="w", padx=26)
        if not choices:
            tk.Label(left, text="Nothing here yet.", bg="#FFF8F0", fg="#6B6685").pack(anchor="w")
        tk.Button(left, text="Close", command=win.destroy, padx=14).pack(anchor="w", pady=(14, 0))
        refresh()

    def shop_dialog(self):
        """Everything the pet can do or wear, with a line on each. Prices and Buy buttons land here when extras exist."""
        win = tk.Toplevel(self.root); win.title("Shop"); win.attributes("-topmost", True); window_icon(win)
        win.configure(bg=CREAM)
        win.geometry(f"+{max(self.area[0], int(self.x) - 260)}+{max(self.area[1], int(self.y) - 520)}")
        tk.Label(win, text=f"Everything for {self.st['name']}", bg=CREAM, fg="#23213B", font=("Segoe UI", 12, "bold")).pack(padx=18, pady=(14, 2), anchor="w")
        tk.Label(win, text="Tricks and habits all come with your pet. Closet extras are yours forever once bought; Buy opens the store, and the code from your email unlocks it here.",
                 bg=CREAM, fg="#6B6685", font=("Segoe UI", 9), wraplength=round(520 * SCALE), justify="left").pack(padx=18, pady=(0, 8), anchor="w")
        # everything below scrolls, so the window never runs off the bottom of a small screen
        outer = tk.Frame(win, bg=CREAM); outer.pack(fill="both", expand=True)
        canvas = tk.Canvas(outer, bg=CREAM, bd=0, highlightthickness=0, width=round(540 * SCALE), height=min(round(560 * SCALE), self.area[3] - self.area[1] - round(260 * SCALE)))
        bar = tk.Scrollbar(outer, orient="vertical", command=canvas.yview); canvas.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y"); canvas.pack(side="left", fill="both", expand=True)
        cols = tk.Frame(canvas, bg=CREAM); cols_id = canvas.create_window((0, 0), window=cols, anchor="nw")
        cols.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(cols_id, width=e.width))
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        win.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>") if e.widget is win else None)
        picked = set(self.st["picks"])

        left = tk.Frame(cols, bg=CREAM); left.pack(side="left", anchor="n", padx=6)
        for group, title in (("tricks", "Tricks"), ("behaviours", "Habits"), ("together", "Together"), ("gadgets", "Gadgets")):
            items = self.sp["catalog"].get(group, [])
            if not items:
                continue
            tk.Label(left, text=title, bg=CREAM, fg="#5A3FC0", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(6, 2))
            for it in items:
                row = tk.Frame(left, bg="#FFFFFF", highlightthickness=1, highlightbackground="#E8DFF3"); row.pack(fill="x", pady=2)
                tk.Label(row, text=it["name"], bg="#FFFFFF", fg="#23213B", font=("Segoe UI", 10, "bold"), width=14, anchor="w").grid(row=0, column=0, padx=(10, 4), pady=(5, 0), sticky="w")
                tk.Label(row, text="picked" if it["id"] in picked else "included", bg="#FFFFFF", fg="#5A3FC0" if it["id"] in picked else "#6B6685",
                         font=("Segoe UI", 8, "bold")).grid(row=0, column=1, padx=(0, 10), pady=(5, 0), sticky="e")
                tk.Label(row, text=it.get("what", ""), bg="#FFFFFF", fg="#6B6685", font=("Segoe UI", 9), anchor="w", justify="left", wraplength=round(220 * SCALE)).grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 6), sticky="w")

        right = tk.Frame(cols, bg=CREAM); right.pack(side="left", anchor="n", padx=6)
        px = round(64 * SCALE)
        win.thumbs = []
        for shelf in CLOSET["shelves"]:
            items = [it for it in shelf["items"] if self.frames.has_item(it["id"])]
            if not items:
                continue
            tk.Label(right, text=shelf["name"], bg=CREAM, fg="#5A3FC0", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(6, 2))
            grid = tk.Frame(right, bg=CREAM); grid.pack(anchor="w")
            for i, it in enumerate(items):
                im = self.frames.compose("happy", "idle", 0, {shelf["id"]: it["id"]}).crop((48, 0, 208, 160))
                bg = Image.new("RGBA", im.size, (255, 255, 255, 255)); bg.alpha_composite(im)
                ph = ImageTk.PhotoImage(bg.resize((px, px), Image.LANCZOS)); win.thumbs.append(ph)
                cell = tk.Frame(grid, bg="#FFFFFF", highlightthickness=1, highlightbackground="#E8DFF3"); cell.grid(row=i // 3, column=i % 3, padx=3, pady=3)
                tk.Label(cell, image=ph, bg="#FFFFFF", bd=0).pack(padx=6, pady=(6, 0))
                tk.Label(cell, text=it["name"], bg="#FFFFFF", fg="#23213B", font=("Segoe UI", 9, "bold")).pack()
                worn = self.st["wearing"].get(shelf["id"]) == it["id"]
                if owns(it["id"]):
                    tag = "wearing" if worn else ("included" if it["id"] in INCLUDED else "yours")
                    tk.Label(cell, text=tag, bg="#FFFFFF", fg="#5A3FC0" if worn else "#6B6685", font=("Segoe UI", 8, "bold")).pack(pady=(0, 6))
                else:
                    info = SHOP["items"].get(it["id"], {})
                    tk.Button(cell, text=f"Buy, {info.get('price', '')}", command=lambda u=info.get("url") or SHOP.get("store_url", ""): u and webbrowser.open(u),
                              bg="#5A3FC0", fg="#FFFFFF", activebackground="#4A32A6", activeforeground="#FFFFFF", relief="flat", font=("Segoe UI", 8, "bold"), padx=8, pady=1, cursor="hand2").pack(pady=(2, 6))
        second = SHOP["items"].get("second_pet", {})
        tk.Label(right, text="Another pet", bg=CREAM, fg="#5A3FC0", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(10, 2))
        row2 = tk.Frame(right, bg="#FFFFFF", highlightthickness=1, highlightbackground="#E8DFF3"); row2.pack(anchor="w", fill="x")
        tk.Label(row2, text=f"A second pet for this computer, {second.get('price', '')}. Teal, Pink, Green or Gold.", bg="#FFFFFF", fg="#6B6685", font=("Segoe UI", 9), wraplength=round(200 * SCALE), justify="left").pack(padx=10, pady=(6, 2), anchor="w")
        tk.Button(row2, text=f"Buy, {second.get('price', '')}", command=lambda u=second.get("url") or SHOP.get("store_url", ""): u and webbrowser.open(u),
                  bg="#5A3FC0", fg="#FFFFFF", activebackground="#4A32A6", activeforeground="#FFFFFF", relief="flat", font=("Segoe UI", 8, "bold"), padx=8, pady=1, cursor="hand2").pack(padx=10, pady=(0, 8), anchor="w")
        foot = tk.Frame(win, bg=CREAM); foot.pack(pady=(8, 14))
        tk.Button(foot, text="Enter a code...", command=lambda: (win.destroy(), self.code_dialog()), padx=14).pack(side="left", padx=6)
        tk.Button(foot, text="Close", command=win.destroy, padx=14).pack(side="left", padx=6)

    def remember_place(self):
        self.st["x"] = int(self.x)
        self.st["mon"] = [int(self.x + self.size // 2), int(self.floor + self.size // 2)]
        save_state(self.st)

    def quit(self):
        self.remember_place(); self.unsay(); H.leave(self.sp["id"]); self.root.destroy()

    # --- other pets on this desktop
    def presence(self):
        return {"name": self.st["name"], "x": int(self.x), "y": int(self.y), "size": self.size, "facing": self.facing,
                "state": self.state, "area": list(self.area), "wearing": self.st["wearing"]}

    def playable(self):
        return self.state in ("idle", "walk", "sit") and self.mood != "sulky" and self.drag is None

    def mind_others(self):
        pid = self.sp["id"]
        H.announce(pid, self.presence())
        here = H.others(pid, self.area)
        now = time.time()
        for o in here:                                       # someone came out (or came back after a while): wave
            if now - self.seen.get(o["pid"], 0) > 20 and self.playable() and self.anim_t > 40:
                self.queue_routine([("happy", "wave1", 0, 0, 0, 170), ("happy", "wave2", 0, 0, 0, 170)] * 3 + [("happy", "idle", 0, 0, 0, 100)])
                self.root.after(200, lambda: self.say("Hi."))
            self.seen[o["pid"]] = now
        plan = H.take_plan(pid)
        if plan and self.state not in ("together", "break", "held"):     # a play is a play: drop what you're doing and join
            other = next((o for o in here if o["pid"] == plan["a"]), None)
            if other:
                self.routine = []; self.mood = "happy"
                if self.state == "hide": self.state = "idle"
                self.start_play(plan, "b", other)

    def play_now(self, kind):
        """The owner asked for a play: with everyone if it's a group kind and three or more are out, else with the nearest."""
        pid = self.sp["id"]
        here = H.others(pid, self.area)
        if not here:
            self.say("No one's here."); return
        if self.state in ("together", "break", "hide"):
            self.say("In a minute."); return
        self.routine = []; self.state = "idle"; self.mood = "happy"
        other = min(here, key=lambda o: abs(o["x"] - self.x))
        if len(here) >= 2 and kind in H.GROUP_KINDS:
            group = [pid] + [o["pid"] for o in here]
            xs = [self.x] + [o["x"] for o in here]
            meet = int(sum(xs) / len(xs))
            meet = max(self.area[0] + self.size * (len(group) // 2 + 1), min(self.area[2] - self.size * (len(group) // 2 + 2), meet))
            plan = H.propose(kind, pid, other["pid"], meet, group=group)
        else:
            if kind == "parade":
                kind = "chase"
            if kind == "hatswap" and not (self.st["wearing"].get("hat") and other.get("wearing", {}).get("hat")):
                self.say("We both need hats for that."); return
            meet = int((self.x + other["x"]) / 2)
            meet = max(self.area[0] + self.size, min(self.area[2] - self.size * 2, meet))
            plan = H.propose(kind, pid, other["pid"], meet)
        if plan:
            self.start_play(plan, "a", other); self.touched(5)

    def maybe_play(self):
        """Now and then, ask another pet on this screen to do something together."""
        pid = self.sp["id"]
        here = [o for o in H.others(pid, self.area) if o.get("state") in ("idle", "walk", "sit")]
        if not here or time.time() < self.next_play:
            return False
        other = random.choice(here)
        if len(here) >= 2 and random.random() < 0.6:                 # three or more out: everyone joins
            kind = random.choice(H.GROUP_KINDS)
            group = [pid] + [o["pid"] for o in here]; random.shuffle(group)
            xs = [self.x] + [o["x"] for o in here]
            meet = int(sum(xs) / len(xs))
            meet = max(self.area[0] + self.size * (len(group) // 2 + 1), min(self.area[2] - self.size * (len(group) // 2 + 2), meet))
            plan = H.propose(kind, pid, other["pid"], meet, group=group)
        else:
            kinds = list(H.KINDS)
            if not (self.st["wearing"].get("hat") and other.get("wearing", {}).get("hat")):
                kinds.remove("hatswap")
            kind = random.choice(kinds)
            meet = int((self.x + other["x"]) / 2)
            meet = max(self.area[0] + self.size, min(self.area[2] - self.size * 2, meet))
            plan = H.propose(kind, pid, other["pid"], meet)
        if plan:
            self.start_play(plan, "a", other)
        return bool(plan)

    def start_play(self, plan, role, other):
        me = dict(self.presence(), pid=self.sp["id"])
        lines = (H.gossip_lines(self.st, other) + N.gossip_bits(self.st["notes"])) if plan["kind"] == "gossip" else None
        steps, says, intro = H.script(plan["kind"], role, me, other, plan, picks=self.st["picks"], lines=lines)
        delay = max(0, int((plan["t0"] - time.time()) * 1000))
        self.state = "idle"; self.routine = []; self.until = time.time() + delay / 1000 + 5   # hold still until it starts
        fast = os.environ.get("PERCH_FAST_PLAY")            # for testing: plays every 20-40 s instead of every 4-12 min
        self.next_play = time.time() + (random.uniform(20, 40) if fast else random.uniform(4 * 60, 12 * 60))
        def go():
            if self.state in ("together", "break", "held"):
                return
            self.mood = "happy"; self.queue_routine(steps)
            for at, text in says:
                self.root.after(at, lambda t=text: self.say(t))
            if plan["kind"] == "hatswap":
                theirs = other.get("wearing", {}).get("hat")
                def off():
                    self.st["wearing"]["hat"] = None
                def on():
                    self.st["wearing"]["hat"] = theirs; save_state(self.st)
                self.root.after(intro + 900, off); self.root.after(intro + 2300, on)
        self.root.after(delay, go)

    # --- tricks (routines are lists of (mood, pose, yaw, dx, dy, ms))
    def queue_routine(self, steps):
        self.routine = list(steps); self.state = "routine"; self.anim_t = 0

    def _bounce_steps(self, n):
        out = []
        for _ in range(n):
            out += [("happy", "squash", 0, 0, 0, 80), ("happy", "stretch", 0, 0, -14, 90), ("happy", "idle", 0, 0, 14, 90)]
        return out

    def do_trick(self, tid, by_owner=True):
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
        if by_owner:
            self.touched(10)

    # --- together: the pet keeps you company until you say so
    def do_together(self, tid, by_owner=True):
        self.routine = []; self.mood = "happy"; self.state = "together"; self.together = tid; self.anim_t = 0
        self.together_started = time.time()
        self.until = float("inf")                       # runs until the owner clicks the pet
        self.say({"study": "Let's study.", "work": "Let's get to work.", "game": "Game on.", "eat": "Yum."}.get(tid, "Okay."))
        if by_owner:
            self.touched(10)

    def stop_together(self):
        if self.state == "together":
            self.state = "idle"; self.until = time.time() + 1
            if self.together == "eat":
                self.say("That was good.")
                if time.time() - self.together_started >= 15:
                    self._after_meal()
            else:
                self.say("Okay.")

    def _after_meal(self):
        self.next_break = time.time() + random.uniform(30, 90); self.after_meal = True   # a meal has consequences

    def _together_frame(self):
        t = self.anim_t
        if self.together == "eat":
            return ("happy", "eat1" if (t // 7) % 2 == 0 else "eat2", 0)
        if self.together == "game":
            return ("surprised" if (t // 30) % 5 == 4 else "happy", "game", 0)
        pose = self.together                                    # study, work
        doze = (t // 20) % 60 >= 56                             # nods off for a moment every minute or so
        if (t // 20) % 25 == 24:
            return ("happy", "stretch", 0)
        return ("sleepy" if doze else "happy", pose, 0)

    # --- a break behind the curtain; we don't watch
    def take_break(self):
        self.break_kind = random.choice(("bath", "bath", "shower")) if not getattr(self, "after_meal", False) else "bath"
        self.after_meal = False
        self.routine = []; self.state = "break"; self.anim_t = 0
        self.until = time.time() + random.uniform(14, 24)
        self.say("Be right back.", ms=1600)

    # --- hide: turn into a folder until found
    def hide(self):
        self.routine = []; self.state = "hide"; self.anim_t = 0; self.until = time.time() + 5 * 60; self.unsay()

    # --- reminders the owner asked for
    def remind_dialog(self):
        win = tk.Toplevel(self.root); win.title("Remind me"); win.attributes("-topmost", True); window_icon(win); win.configure(bg=CREAM)
        win.geometry(f"+{max(self.area[0], int(self.x) - 120)}+{max(self.area[1], int(self.y) - 300)}")
        tk.Label(win, text=f"{self.st['name']} will remind you.", bg=CREAM, fg="#23213B", font=("Segoe UI", 11, "bold")).pack(padx=16, pady=(12, 8), anchor="w")
        f = tk.Frame(win, bg=CREAM); f.pack(padx=16, anchor="w")
        now = datetime.now()
        fields = {}
        for i, (key, label, init, width) in enumerate((("date", "Day (YYYY-MM-DD)", now.strftime("%Y-%m-%d"), 12),
                                                        ("time", "Time (HH:MM, 24 hour)", (now.replace(second=0) + timedelta(minutes=60)).strftime("%H:%M"), 7),
                                                        ("text", "What for", "", 32))):
            tk.Label(f, text=label, bg=CREAM, fg="#5A3FC0", font=("Segoe UI", 9, "bold")).grid(row=0, column=i, sticky="w", padx=(0, 12))
            e = tk.Entry(f, font=("Segoe UI", 11), width=width); e.insert(0, init); e.grid(row=1, column=i, sticky="w", padx=(0, 12)); fields[key] = e
        note = tk.Label(win, text="", bg=CREAM, fg="#B4453A", font=("Segoe UI", 9)); note.pack(padx=16, pady=(6, 0), anchor="w")
        upcoming = tk.Frame(win, bg=CREAM); upcoming.pack(padx=16, pady=(6, 0), anchor="w")

        def redraw():
            for w in upcoming.winfo_children(): w.destroy()
            rems = sorted(self.st["reminders"], key=lambda r: r["when"])
            if rems:
                tk.Label(upcoming, text="Coming up", bg=CREAM, fg="#6B6685", font=("Segoe UI", 9, "bold")).pack(anchor="w")
            for r in rems:
                row = tk.Frame(upcoming, bg=CREAM); row.pack(anchor="w", fill="x")
                tk.Label(row, text=f"{r['when'].replace('T', ' at ')}: {r['text']}", bg=CREAM, fg="#23213B", font=("Segoe UI", 9)).pack(side="left")
                tk.Button(row, text="Forget it", command=lambda r=r: (self.st["reminders"].remove(r), save_state(self.st), redraw()), padx=6, pady=0, font=("Segoe UI", 8)).pack(side="left", padx=8)

        def add():
            try:
                when = datetime.strptime(fields["date"].get().strip() + " " + fields["time"].get().strip(), "%Y-%m-%d %H:%M")
            except ValueError:
                note.configure(text="Use a day like 2026-09-20 and a time like 15:30."); return
            text = fields["text"].get().strip()
            if not text:
                note.configure(text="What should I remind you of?"); return
            if when < datetime.now():
                note.configure(text="That time has already passed."); return
            self.st["reminders"].append({"when": when.strftime("%Y-%m-%dT%H:%M"), "text": text[:80]}); save_state(self.st)
            fields["text"].delete(0, "end"); note.configure(text=""); redraw()
            self.say("I'll remind you.")
        tk.Button(win, text="Add", command=add, padx=14).pack(pady=(10, 4), anchor="w", padx=16)
        tk.Button(win, text="Close", command=win.destroy, padx=14).pack(pady=(0, 12), anchor="w", padx=16)
        redraw()

    # --- the notebook: what the owner tells the pet
    def notebook_dialog(self):
        win = tk.Toplevel(self.root); win.title("Notebook"); win.attributes("-topmost", True); window_icon(win); win.configure(bg=CREAM)
        win.geometry(f"+{max(self.area[0], int(self.x) - 160)}+{max(self.area[1], int(self.y) - 480)}")
        tk.Label(win, text=f"Tell {self.st['name']} something", bg=CREAM, fg="#23213B", font=("Segoe UI", 12, "bold")).pack(padx=16, pady=(12, 2), anchor="w")
        tk.Label(win, text="Anything. Who you are, who's in your life, what you like, how today went. It remembers, and brings things up later. Stays on this computer.",
                 bg=CREAM, fg="#6B6685", font=("Segoe UI", 9), wraplength=round(420 * SCALE), justify="left").pack(padx=16, pady=(0, 8), anchor="w")
        box = tk.Text(win, font=("Segoe UI", 11), width=48, height=3, wrap="word", relief="flat", highlightthickness=1, highlightbackground="#E8DFF3")
        box.pack(padx=16, anchor="w"); box.focus_set()
        note = tk.Label(win, text="", bg=CREAM, fg="#6B6685", font=("Segoe UI", 9)); note.pack(padx=16, pady=(4, 0), anchor="w")
        outer = tk.Frame(win, bg=CREAM); outer.pack(padx=16, pady=(8, 0), fill="both")
        canvas = tk.Canvas(outer, bg=CREAM, bd=0, highlightthickness=0, width=round(440 * SCALE), height=round(220 * SCALE))
        bar = tk.Scrollbar(outer, orient="vertical", command=canvas.yview); canvas.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y"); canvas.pack(side="left", fill="both", expand=True)
        lst = tk.Frame(canvas, bg=CREAM); lst_id = canvas.create_window((0, 0), window=lst, anchor="nw")
        lst.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(lst_id, width=e.width))

        def redraw():
            for w in lst.winfo_children(): w.destroy()
            notes = self.st["notes"]
            if not notes:
                tk.Label(lst, text="Nothing yet.", bg=CREAM, fg="#A29DB8", font=("Segoe UI", 9)).pack(anchor="w")
            for n in reversed(notes):
                row = tk.Frame(lst, bg="#FFFFFF", highlightthickness=1, highlightbackground="#E8DFF3"); row.pack(fill="x", pady=2)
                when = n["when"][:10]
                tk.Label(row, text=when, bg="#FFFFFF", fg="#A29DB8", font=("Segoe UI", 8)).pack(anchor="w", padx=8, pady=(4, 0))
                tk.Label(row, text=n["text"], bg="#FFFFFF", fg="#23213B", font=("Segoe UI", 10), wraplength=round(360 * SCALE), justify="left").pack(anchor="w", padx=8)
                tk.Button(row, text="Forget", command=lambda n=n: (self.st["notes"].remove(n), save_state(self.st), redraw()), padx=6, pady=0, font=("Segoe UI", 8)).pack(anchor="e", padx=6, pady=(0, 4))

        def save(*_):
            text = box.get("1.0", "end").strip()
            if not text:
                note.configure(text="Type something first."); return "break"
            self.st["notes"].append({"when": datetime.now().isoformat(timespec="minutes"), "text": text[:240]})
            del self.st["notes"][:-300]
            save_state(self.st); box.delete("1.0", "end"); note.configure(text=""); redraw()
            self.say(N.reaction(text)); self.touched(5)
            self.next_recall = min(self.next_recall, time.time() + random.uniform(3 * 60, 8 * 60))
            return "break"
        box.bind("<Return>", save)
        tk.Button(win, text="Save", command=save, padx=14).pack(padx=16, pady=(10, 4), anchor="w")
        tk.Button(win, text="Close", command=win.destroy, padx=14).pack(padx=16, pady=(0, 12), anchor="w")
        redraw()

    def bring_up_a_note(self):
        line = N.recall(self.st["notes"])
        if line:
            self.mood = "happy"; self.queue_routine([("happy", "squash", 0, 0, 0, 120), ("happy", "stretch", 0, 0, -8, 140), ("happy", "idle", 0, 0, 8, 100)])
            self.root.after(350, lambda: self.say(line, ms=5200))

    def deliver_reminders(self, late=False):
        now = datetime.now().strftime("%Y-%m-%dT%H:%M")
        due = [r for r in self.st["reminders"] if r["when"] <= now]
        if not due:
            return
        for r in due:
            self.st["reminders"].remove(r)
        save_state(self.st)
        text = "; ".join(r["text"] for r in due)
        if self.state in ("hide", "together", "sleep", "sulk"):
            self.state = "idle"
        self.mood = "surprised"; self.routine = []
        self.queue_routine(self._bounce_steps(4))
        self.root.after(700, lambda: self.say(("You asked me to remind you: " if late else "Reminder: ") + text, ms=None))

    # --- the loop
    def tick(self):
        now = time.time()
        # attention drifts down while the pet is ignored; below 30 it sulks
        if now - self.last_attention_tick > 60:
            self.last_attention_tick = now
            self.st["attention"] = max(0, self.st["attention"] - (2 if "clingy" in self.st["picks"] else 1))
            if self.ignored() and self.state in ("idle", "walk", "sit"):
                self.mood = "sulky"; self.state = "sulk"; self.until = now + 40
                self.say(random.choice(["Hmph.", "...", "You forgot me."]))
            elif self.st["notes"] and now > self.next_recall and self.state in ("idle", "walk", "sit") and not self.lonely():
                self.next_recall = now + random.uniform(15 * 60, 35 * 60)
                self.bring_up_a_note()
            elif self.lonely() and now > self.next_nudge and self.state in ("idle", "walk", "sit"):
                self.next_nudge = now + random.uniform(300, 420)
                self.mood = "happy"; self.queue_routine(self._bounce_steps(3))
                self.root.after(500, lambda: self.say(random.choice(["Play with me?", "Psst.", "I'm bored."])))
            save_state(self.st)

        if self.anim_t % 5 == 0 and not self.selftest:
            self.mind_others()
        if int(now) % 10 == 0 and int(now) != getattr(self, "_rem_checked", 0):
            self._rem_checked = int(now); self.deliver_reminders()
            if pet_state(self.sp["id"]).get("home", False) and not self.selftest:   # sent home from another pet's menu
                self.st["home"] = True; self.remember_place(); self.unsay(); self.root.destroy(); return

        if self.state == "held":
            pass
        elif self.state == "routine":
            self._run_routine()
        elif self.state == "hide":
            self.anim_t += 1
            if now > self.until:                                   # nobody came; come out on your own
                self.state = "idle"; self.until = now + 2
            peek = (self.anim_t // 20) % 40 in (37, 38)            # a quick look over the edge now and then
            self.label.configure(image=self.frames.get_folder(self.st["wearing"], peek))
        elif self.state == "break":
            self.anim_t += 1
            if now > self.until:
                self.state = "idle"; self.until = now + 2; self.mood = "happy"
                self.next_break = now + random.uniform(25 * 60, 60 * 60)
                self.queue_routine([("happy", "stretch", 0, 0, 0, 500), ("happy", "idle", 0, 0, 0, 100)])
                self.say("Fresh." if self.break_kind == "shower" else "Don't ask.")
            else:
                self.label.configure(image=self.frames.get_curtain(self.break_kind, self.anim_t // 6))
        elif self.state == "together":                  # ends only when the owner clicks the pet
            self.anim_t += 1
            self.show(*self._together_frame())
        else:
            if now > self.until:
                if now > self.next_break and self.state in ("idle", "walk", "sit") and self.mood != "sulky":
                    self.take_break()
                elif self.playable() and random.random() < 0.25 and self.maybe_play():
                    pass
                else:
                    self._choose()
            if self.state in ("break", "together", "hide"):
                pass                                               # just switched; drawn from the next tick on
            elif self.state == "walk":
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
            elif self.state == "sit":             # sits down for a bit, looks around
                self.anim_t += 1
                self.show(self.mood, "sit", 0)
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
        w = {"idle": 40, "walk": 30, "sleep": 8, "sit": 6, "trick": 4}
        if "calm" in picks: w["walk"] -= 15; w["idle"] += 9; w["sit"] += 6
        if "sleepy" in picks: w["sleep"] += 18
        if "showoff" in picks: w["trick"] += 14
        if self.mood == "sulky" and not self.ignored(): self.mood = "happy"
        if self.mood == "sulky": w = {"idle": 60, "walk": 10, "sleep": 10, "sit": 0, "trick": 0}
        roll = random.uniform(0, sum(w.values())); pick = "idle"
        for k, v in w.items():
            roll -= v
            if roll <= 0: pick = k; break
        if pick == "trick":
            tricks = [t for t in ("bounce", "peekaboo", "zoomies", "sit", "lie", "spin", "wave") if t in picks]
            if tricks: self.do_trick(random.choice(tricks), by_owner=False); return
            pick = "idle"
        self.state = pick if pick != "trick" else "idle"
        if pick == "walk":
            self.facing = random.choice((1, -1)); self.vx = self.facing * random.uniform(1.2, 2.2)
            self.until = time.time() + (random.uniform(8, 18) if random.random() < 0.3 else random.uniform(2, 6))   # sometimes a real stroll
        elif pick == "sleep":
            self.mood = "sleepy"; self.until = time.time() + random.uniform(8, 20)
        elif pick == "sit":
            self.mood = "happy"; self.until = time.time() + random.uniform(6, 14)
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
        if pid in adopted_ids():
            note.configure(text=f"{species[pid]['label']} already lives here. Pick another."); return
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
    ap.add_argument("--adopt", action="store_true", help="open the adoption window even if pets exist (Adopt another)")
    a = ap.parse_args()
    pet_id = a.pet
    if a.adopt:
        pet_id = adoption_window()
        if pet_id is None:
            return
    elif pet_id is None:
        preset = preset_pet()
        if preset and preset not in adopted_ids():    # a per-pet installer: no questions, the bought pet joins
            save_state(load_state(load_species(preset)))
        adopted = adopted_ids()
        if adopted:
            out = [pid for pid in adopted if not pet_state(pid).get("home", False)] or adopted[:1]
            if preset in adopted and preset not in out:
                out.insert(0, preset)
            if preset in out:                         # the newest one gets this window; the others get their own
                out.remove(preset); out.insert(0, preset)
            pet_id, others = out[0], out[1:]
            for other in others:
                subprocess.Popen(launch_command(other), shell=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            pet_id = adoption_window()
            if pet_id is None:
                return
    set_home(pet_id, False)
    if not claim_instance(pet_id):
        return
    pet = Pet(load_species(pet_id), selftest=a.selftest)
    pet.root.mainloop()


if __name__ == "__main__":
    main()
