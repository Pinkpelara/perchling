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
import argparse, ctypes, json, os, random, statistics, subprocess, sys, threading, time, urllib.parse, urllib.request, webbrowser
from ctypes import wintypes
from datetime import date, datetime, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import simpledialog
from PIL import Image, ImageTk
import household as H
import petnotes as N
import pettalk as T
import fun as F
import stage as S
import eggs as E
import hatmaker as HM
import menu as M

VERSION = "0.26.2"
RELEASES_API = "https://api.github.com/repos/Pinkpelara/perchling/releases/latest"
SETUP_URL = "https://github.com/Pinkpelara/perchling/releases/latest/download/PerchlingsSetup.exe"
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


def species_of(pet_id):
    return str(pet_id).split("#")[0]


def load_state(species, pet_id=None):
    pet_id = pet_id or species["id"]
    p = state_path(pet_id)
    st = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    st.setdefault("pet", pet_id)
    st.setdefault("species", species["id"])
    st.setdefault("name", species.get("name", species["label"]))
    if st["name"] == species["label"] and species.get("name"):        # never named by the owner: takes the character's name
        st["name"] = species["name"]
    st.setdefault("chaos", "cheeky")                                     # sweet | cheeky | menace: how much mischief
    sig = species.get("signature")
    if sig and sig not in st.get("picks", []):
        st.setdefault("picks", []).append(sig)                            # a character always has its own move
    if "mischief" in st.get("picks", []):                                # the old pick becomes the dial
        st["picks"] = [x for x in st["picks"] if x != "mischief"]; st["chaos"] = "menace"
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
    st.setdefault("music", True)              # dances when the speakers are playing something
    st.setdefault("reacts", True)             # cheers you on, notices undo, sleeps when the screen locks
    st.setdefault("variant", None)            # a colour from an egg: {"name", "hue", "sat", "light", "tier"}
    st.setdefault("hatched", False)
    st.setdefault("care", {})                 # "YYYY-MM-DD" -> touches that day
    st.setdefault("egg_baseline", None)       # care days before this date don't count toward the next egg
    return st


def save_state(st):
    state_path(st["pet"]).write_text(json.dumps(st, indent=1), encoding="utf-8")


def owner_path():
    return state_path("antenna").parent / "owner.json"


def load_owner():
    try:
        d = json.loads(owner_path().read_text(encoding="utf-8"))
        return N.Owner(d.get("name"), d.get("pronoun") or "they")
    except (OSError, ValueError):
        return N.Owner()


def owner_file():
    """The household's owner.json as a dict (name, pronoun, birthday), or {}."""
    try:
        return json.loads(owner_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_owner_file(**changes):
    d = owner_file(); d.update({k: v for k, v in changes.items()})
    try:
        owner_path().write_text(json.dumps(d), encoding="utf-8")
    except OSError:
        pass


def learn_owner(notes):
    """Any pet that learns the owner's name or pronouns tells the household file, so all of them use it."""
    name, pronoun = N.owner_from_notes(notes)
    if not name and not pronoun:
        return
    cur = load_owner()
    save_owner_file(name=name or cur.name, pronoun=pronoun or cur.pronoun)


def owner_birthday():
    """The owner's birthday (MM-DD) is one thing for the whole household, so every pet celebrates the same day."""
    return owner_file().get("birthday")


def react_file():
    return H.base_dir() / "react.json"


def load_react():
    """What the household last reacted to: {"kind", "ts", "by", "last": {kind: ts}}. One pet notices a typing burst and
    writes it here; every other pet that is free joins in, and the cooldown per kind is shared, so they react together."""
    try:
        return json.loads(react_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


REACT_COOLDOWN = {"cheer": 240, "oops": 180, "saved": 300, "easy": 300}


def dance_slot(now):
    """The household's dance schedule, on the wall clock: everyone dances for two and a half minutes, then everyone
    takes a thirty second breather, so no pet is ever dancing alone while the others rest."""
    return (now % 180.0) < 150.0


def house_info():
    """Where the house is right now (door position, monitor, open or closed), or None if there isn't one out."""
    try:
        d = json.loads((H.base_dir() / "house.json").read_text(encoding="utf-8"))
        return d if time.time() - d.get("ts", 0) < 20 else None
    except (OSError, ValueError):
        return None


def house_command():
    if FROZEN:
        return f'"{sys.executable}" --house'
    pyw = Path(sys.executable).with_name("pythonw.exe")
    return f'"{pyw if pyw.exists() else sys.executable}" "{Path(__file__).resolve()}" --house'


def start_house_if_needed():
    if house_info() is None:
        subprocess.Popen(house_command(), shell=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def household_states():
    """Every pet's file, so a gossip can draw on everything the household knows."""
    return {pid: pet_state(pid) for pid in adopted_ids()}


def build_talk(group, seed):
    f = T.facts(household_states(), load_owner())
    return T.conversation(f, group, random.Random(seed))


def owned_path():
    return state_path("antenna").parent / "owned.json"


def load_owned():
    p = owned_path()
    try:
        d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except (OSError, ValueError):
        d = {}
    d.setdefault("items", []); d.setdefault("codes", []); d.setdefault("free_picks", 0)
    return d


def save_owned(d):
    owned_path().write_text(json.dumps(d, indent=1), encoding="utf-8")


def hats_dir():
    return state_path("antenna").parent / "hats"


def owns_pick(pick_id):
    """A trick, habit or Together pick the household owns: chosen with a free pick, bought, or in the all-picks bundle."""
    o = load_owned()
    return f"pick:{pick_id}" in o["items"] or "picks:all" in o["items"]


def free_picks():
    return load_owned().get("free_picks", 0)


def unlock_pick(pick_id, spend=True):
    """Make a pick the household's. spend: take one of the free picks (True) or it was bought (False)."""
    o = load_owned()
    if f"pick:{pick_id}" in o["items"]:
        return True
    if spend:
        if o.get("free_picks", 0) <= 0:
            return False
        o["free_picks"] -= 1
    o["items"] = sorted(set(o["items"]) | {f"pick:{pick_id}"}); save_owned(o)
    return True


def grant_free_picks(n):
    o = load_owned(); o["free_picks"] = o.get("free_picks", 0) + n; save_owned(o)


def owns(item_id):
    if item_id.startswith("my:"):          # hats from the hat maker are free
        return True
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
            new_pets = [i for i in items if i.startswith("pet:") and i not in owned["items"]]
            owned["items"] = sorted(set(owned["items"]) | set(items)); owned["codes"].append(code)
            owned["free_picks"] = owned.get("free_picks", 0) + 5 * len(new_pets); save_owned(owned)
            return True, "Unlocked." + (f" {5 * len(new_pets)} free picks came with it." if new_pets else "")
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
    new_pets = [i for i in items if i.startswith("pet:") and i not in owned["items"]]
    owned["items"] = sorted(set(owned["items"]) | set(items)); owned["codes"].append(code)
    owned["free_picks"] = owned.get("free_picks", 0) + 5 * len(new_pets); save_owned(owned)
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


def version_tuple(v):
    try:
        return tuple(int(x) for x in v.lstrip("v").split(".")[:3])
    except ValueError:
        return (0,)


def newest_version():
    """Ask GitHub which version is newest. Returns the tag, or None if that can't be answered right now."""
    try:
        req = urllib.request.Request(RELEASES_API, headers={"Accept": "application/vnd.github+json", "User-Agent": f"Perchlings/{VERSION}"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8")).get("tag_name")
    except Exception:
        return None


def update_dir():
    d = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Perchlings-update"
    d.mkdir(parents=True, exist_ok=True)
    return d


def instance_running(pet_id):
    """True if a pet (or the house, or the stage) with this id already holds its one-copy lock."""
    try:
        import hashlib
        home = str(state_path(pet_id).parent).lower()
        tag = hashlib.md5(home.encode("utf-8")).hexdigest()[:8]
        k = ctypes.windll.kernel32; k.OpenMutexW.restype = ctypes.c_void_p
        h = k.OpenMutexW(0x00100000, False, f"Perchlings-{pet_id}-{tag}")
        if h:
            k.CloseHandle(ctypes.c_void_p(h)); return True
        return False
    except (AttributeError, OSError):
        return False


def stale_household():
    """Pets that were out and went quiet (a crash, an update's force-close) and whether the house did the same.
    A pet that quit removed its file, and the house that was closed by the owner removed its own, so those stay away."""
    now = time.time(); pets = []
    for pid in adopted_ids():
        f = H.base_dir() / "here" / f"{pid}.json"
        try:
            if f.exists() and now - json.loads(f.read_text(encoding="utf-8")).get("ts", 0) > 45 and not pet_state(pid).get("home", False):
                pets.append(pid)
        except (OSError, ValueError):
            continue
    house = False
    try:
        hj = H.base_dir() / "house.json"
        house = hj.exists() and now - json.loads(hj.read_text(encoding="utf-8")).get("ts", 0) > 45
    except (OSError, ValueError):
        house = False
    return pets, house


def keep_household():
    """Bring back whoever went quiet. The one-copy locks make double starts harmless."""
    pets, house = stale_household()
    for pid in pets:
        if not instance_running(pid):
            subprocess.Popen(launch_command(pid), shell=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if house and not instance_running("house"):
        subprocess.Popen(house_command(), shell=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def claim_instance(pet_id):
    """One window per pet. A second start of the same pet (desktop icon plus Startup, say) just exits."""
    try:
        import hashlib
        home = str(state_path(pet_id).parent).lower()             # one instance per pet per data folder
        tag = hashlib.md5(home.encode("utf-8")).hexdigest()[:8]  # hash() differs per process; this doesn't
        ctypes.windll.kernel32.CreateMutexW(None, False, f"Perchlings-{pet_id}-{tag}")
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
    return json.loads((SPECIES_DIR / f"{species_of(pet_id)}.json").read_text(encoding="utf-8"))


def preset_pet():
    """A per-pet installer leaves a pet.txt next to the exe naming the pet that was bought."""
    f = (Path(sys.executable).parent if FROZEN else ROOT) / "pet.txt"
    try:
        pid = f.read_text(encoding="utf-8").strip()
        return pid if pid in species_ids() else None
    except OSError:
        return None


def adopted_ids():
    """Every pet with a file: the four kinds first in their order, then hatchlings (ids like "ears#2")."""
    base = state_path("antenna").parent
    skip = {"house", "owner", "owned", "state", "test-codes"}
    ids = [p.stem for p in base.glob("*.json") if p.stem not in skip and species_of(p.stem) in species_ids()]
    firsts = [pid for pid in species_ids() if pid in ids]
    return firsts + sorted(pid for pid in ids if "#" in pid)


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

    def __init__(self, pet_id, display_px, variant=None):
        pet_id = species_of(pet_id)
        self.species = pet_id
        self.folder = SPRITES / pet_id
        self.sheet = Image.open(self.folder / f"{pet_id}_sheet.png").convert("RGBA")
        self.index = json.loads((self.folder / f"{pet_id}_sheet.json").read_text())["frames"]
        self.size = display_px
        self.variant = variant
        self.cache = {}
        self.layers = {}
        self.tinted = {}
        self.custom = {}          # painted hat-maker frames, by (hat id, frame key)
        self.hats = {}            # hat dicts by id

    def has_item(self, item_id):
        if item_id in F.EFFECT_COLOURS:
            return True
        if item_id.startswith("my:"):
            hat = self.hat(item_id[3:])
            return bool(hat) and (self.folder / "outfits" / f"maker_{hat['shape']}_sheet.json").exists()
        return (self.folder / "outfits" / f"{item_id}_sheet.json").exists()

    def hat(self, hat_id):
        if hat_id not in self.hats:
            hat = HM.load_hat(hats_dir(), hat_id)
            if not hat: return None            # not cached: it may be made in a moment
            self.hats[hat_id] = hat
        return self.hats[hat_id]

    def forget_custom(self, hat_id=None):
        """After a hat is made or changed: paint it fresh next time."""
        self.hats.pop(hat_id, None) if hat_id else self.hats.clear()
        self.custom = {k: v for k, v in self.custom.items() if hat_id and k[0] != hat_id}
        self.cache.clear()

    def custom_frame(self, hat, key):
        ck = (hat["id"], key)
        if ck not in self.custom:
            sheet, index = self._layer(f"maker_{hat['shape']}")
            self.custom[ck] = HM.paint(self._crop(sheet, index, key), hat)
            if len(self.custom) > 200: self.custom.clear()
        return self.custom[ck]

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

    def compose(self, mood, pose, yaw, wearing=None, preview_hat=None):
        """The pet with its outfit on, full sheet size, see-through background. preview_hat: a hat-maker hat tried on."""
        key = f"{mood}_{pose}_{yaw:03d}"
        if key not in self.index:
            key = self._fallback(mood, pose, yaw)
        if self.variant:
            if key not in self.tinted:
                self.tinted[key] = E.recolor(self._crop(self.sheet, self.index, key), self.species, self.variant)
            im = self.tinted[key]
        else:
            im = self._crop(self.sheet, self.index, key)
        wearing = wearing or {}
        order = ["back", "body", "neck", "face", "ears", "hat"] + [k for k in wearing if k not in ("back", "body", "neck", "face", "ears", "hat")]   # back first, hat last
        for item_id in (wearing.get(k) for k in order):
            if item_id in F.EFFECT_COLOURS:
                continue                                   # effects are drawn live around the pet, not on the frame
            hat = None
            if item_id == "maker-preview" and preview_hat:
                hat = preview_hat
            elif item_id and item_id.startswith("my:") and self.has_item(item_id):
                hat = self.hat(item_id[3:])
            elif not item_id or not self.has_item(item_id):
                continue
            if hat and not (self.folder / "outfits" / f"maker_{hat['shape']}_sheet.json").exists():
                continue
            sheet, index = self._layer(f"maker_{hat['shape']}" if hat else item_id)
            base = {"blink": "idle", "wave1": "idle", "wave2": "idle", "flex": "idle", "study": "sit", "work": "sit", "game": "sit", "eat1": "sit", "eat2": "sit"}.get(pose, pose)
            lk = f"{base}_{yaw:03d}"     # blinks and waves leave the head where it is; the activities are all sitting
            for k in (lk, f"idle_{yaw:03d}", "idle_000"):
                if k in index:
                    layer = self.custom_frame(hat, k) if hat else self._crop(sheet, index, k)
                    im = im.copy(); im.alpha_composite(layer); break
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

    def get_sign(self, text, wearing=None, blink=False):
        ck = ("sign", text, blink, tuple(sorted(v for v in (wearing or {}).values() if v)))
        if ck not in self.cache:
            im = F.sign_frame(self.compose("happy", "blink" if blink else "idle", 0, wearing), text)
            im = im.resize((self.size, self.size), Image.LANCZOS)
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
    def __init__(self, species, selftest=False, pet_id=None):
        self.sp = species
        self.pid = pet_id or species["id"]
        self.st = load_state(species, self.pid)
        self.size = round(species.get("display_px", 128) * SCALE * self.growth() * {"small": 0.75, "medium": 1.0, "large": 1.3}.get(self.st.get("size", "medium"), 1.0))
        self.frames = Frames(species["id"], self.size, variant=self.st.get("variant"))
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
        self.ear = F.AudioEar()
        self.keys = F.KeyWatch()
        self.dance_t = 0
        self.last_cheer = 0; self.last_oops = 0; self.last_easy = 0; self.last_save = 0
        self.locked_sleep = False
        self.midnight_done = None
        self.next_mischief = time.time() + random.uniform(6 * 60, 15 * 60)
        self.mischief_note = None; self.steal_until = 0
        self.sign = None; self.sign_until = 0
        self.saying = None; self.dance_force_until = 0
        self.party_until = 0; self.party_hat_before = None
        self.inside = None                                                     # room name while in the house
        self.inside_until = 0
        self.after_routine = None
        self.update_to = None                                                  # a newer version, once found
        self.updating = False
        if FROZEN and not selftest:
            self.root.after(20000, self.check_update)
        if not selftest:
            self.root.after(1500, start_house_if_needed)
            self.root.after(6000, self.keep_tick)
        self.seen = {}                                                         # other pet -> when I last saw it
        self.next_play = time.time() + 90
        self.autostart = tk.BooleanVar(value=starts_with_windows(self.pid))
        for shelf, item in list(self.st["wearing"].items()):
            if item and not owns(item):
                self.st["wearing"][shelf] = None

        self.label.bind("<ButtonPress-1>", self.on_press)
        self.label.bind("<B1-Motion>", self.on_drag)
        self.label.bind("<ButtonRelease-1>", self.on_release)
        self.label.bind("<Button-3>", self.on_menu)
        self.label.bind("<Enter>", self.on_hover)
        self.label.bind("<Leave>", self.on_leave)
        self.last_hover = 0
        self.next_leave_bit = 0
        self.bit = None
        self.trail = None
        self.chase_until = 0
        self.next_nudge = 0
        self.dance_t0 = 0
        self.dance_rest_until = 0                                              # Stop dancing on the panel: sit the next two minutes out
        self.react_seen = 0                                                    # the last household reaction this pet joined
        self.flags = {}; self.flags_read = 0                                   # household switches, see flag()
        self.play_until = 0                                                    # while a play runs, no reactions
        self.next_house_nap = time.time() + random.uniform(10 * 60, 25 * 60)    # naps in the bedroom, but not so often the desk is empty
        if self.st.get("last_touch") is None:
            self.st["last_touch"] = time.time()          # a new pet starts out fine

        self.arrive()
        self.place()
        self.root.after(TICK_MS, self.tick)

    def growth(self):
        """Hatchlings start small and grow over two weeks."""
        if not self.st.get("hatched"):
            return 1.0
        try:
            days = (date.today() - datetime.fromisoformat(self.st["adopted"]).date()).days
        except (KeyError, ValueError):
            days = 14
        return 0.72 if days < 7 else (0.86 if days < 14 else 1.0)

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
        shared_bday = owner_birthday()
        if shared_bday and not self.st.get("birthday"):
            self.st["birthday"] = shared_bday                          # told to one pet, known to all
        if self.st.get("birthday") == today:
            msg = load_owner().call("Happy birthday.")
            self.queue_routine(self._bounce_steps(10)); self.root.after(900, lambda: self.party("birthday"))
        elif self.st["adopted"][5:] == today and self.st["adopted"] != date.today().isoformat():
            msg = "It's my adoption day."
            self.queue_routine(self._bounce_steps(10)); self.root.after(900, lambda: self.party("adoption"))
        elif days_away >= 3:
            msg = f"You were gone {days_away} days."
            self.mood = "sulky"; self.state = "sulk"; self.until = time.time() + 20
        elif usual is not None and abs(now.hour * 60 + now.minute - usual) <= 30:
            msg = load_owner().call("Right on time.")
        elif last is None and free_picks() > 0:
            msg = f"{self.st['name']} is here."
            self.root.after(4500, lambda: self.say(f"I come with {free_picks()} free picks. Right-click me, then Picks.", ms=7000))
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
        self.saying = {"text": text, "until": time.time() + (ms / 1000 if ms else 600)}
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
            self.root.after(ms, lambda b=b: self.bubble is b and self.unsay())   # only this bubble, never a newer one

    def unsay(self):
        self.saying = None
        if self.bubble is not None:
            try: self.bubble.destroy()
            except tk.TclError: pass
            self.bubble = None

    # --- input
    def on_hover(self, e):
        now = time.time()
        self.hover_since = now
        if now - self.last_hover > 20:                  # the cursor came to visit; that counts
            self.last_hover = now; self.touched(2)

    def on_leave(self, e):
        """The cursor lingered on the pet and left: every character has its own bit, and it happens every time the pet is
        free (a short cooldown keeps it from firing on every twitch of the mouse). The diva faints, the menace gives a
        look, the snoop ducks out of sight and pops back, the slacker flops for a moment."""
        now = time.time()
        stayed = now - getattr(self, "hover_since", now)
        if self.drag or not self.playable() or stayed < 1.5 or now < self.next_leave_bit:
            return
        self.next_leave_bit = now + 90
        self.leave_bit()

    def leave_bit(self):
        sig = self.sp.get("signature")
        if sig in ("faint", "sideeye", "peekaboo"):
            self.do_trick(sig, by_owner=False)
        else:                                                          # the slacker: a flop and a line, two and a half seconds
            self.routine = []; self.mood = "sleepy"
            self.queue_routine([("sleepy", "squash", 0, 0, 0, 2600), ("happy", "idle", 0, 0, 0, 150)])
            self.root.after(300, lambda: self.say(self.line("rot", "Five more minutes."), ms=2200))

    def on_press(self, e):
        self.drag = (e.x_root, e.y_root, self.x, self.y, False)
        self.unsay()

    def on_drag(self, e):
        if not self.drag: return
        sx, sy, ox, oy, _ = self.drag
        dx, dy = e.x_root - sx, e.y_root - sy
        if abs(dx) + abs(dy) > 4:
            self.drag = (sx, sy, ox, oy, True)
            self.x, self.y = ox + dx, oy + dy
            if self.state == "hide":                                    # the folder moves; the pet stays hidden
                self.place(); self.label.configure(image=self.frames.get_folder(self.st["wearing"], False)); return
            self.state = "held"; self.routine = []
            self.place(); self.show("surprised", "idle", 0)

    def on_release(self, e):
        if not self.drag: return
        moved = self.drag[4]; self.drag = None
        if self.state == "hide":                                        # stays hidden: Come out is on the menu
            if moved:
                cx, cy = self.x + self.size // 2, self.y + self.size // 2
                left, top, right, bottom = monitor_work_area(cx, cy)
                self.area = (left, top, right, bottom); self.floor = bottom - self.size + 8
                self.x = max(left, min(right - self.size, self.x)); self.y = self.floor; self.place()
                self.remember_place()
            else:
                self.anim_t = 37 * 20                                   # a click gets a quick peek over the edge
            self.label.configure(image=self.frames.get_folder(self.st["wearing"], not moved)); return
        if self.state == "break":
            self.say("Occupied."); return
        if self.state == "routine" and getattr(self, "bit", None) == "rot" and not moved:     # dragged out of its rot
            self.bit = None; self.routine = []; self.touched(10)
            self.queue_routine([("sulky", "lie", 0, 0, 0, 500), ("happy", "squash", 0, 0, 0, 150), ("happy", "idle", 0, 0, 0, 100)])
            self.say(self.line("rot_up", "Ugh. Fine.")); return
        if self.state == "sign" and not moved:
            self.sign = None; self.state = "idle"; self.until = time.time() + 1; self.touched(5); return
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
        if amount > 0:
            day = date.today().isoformat()
            self.st["care"][day] = self.st["care"].get(day, 0) + 1
            for k in [k for k in self.st["care"] if k < (date.today() - timedelta(days=60)).isoformat()]:
                del self.st["care"][k]

    def good_days(self):
        base = self.st.get("egg_baseline") or ""
        return sum(1 for k, v in self.st["care"].items() if k > base and v >= E.GOOD_DAY_TOUCHES)

    def egg_file(self):
        return H.base_dir() / "egg.json"

    def egg(self):
        try:
            return json.loads(self.egg_file().read_text(encoding="utf-8")) if self.egg_file().exists() else None
        except (OSError, ValueError):
            return None

    def find_egg(self):
        """Enough good days: this pet finds an egg. One egg per household at a time."""
        if self.egg() or len(adopted_ids()) >= E.MAX_PETS:
            return
        species = random.choice(species_ids())
        egg = {"found": time.time(), "by": self.pid, "species": species, "variant": E.roll(), "seed": random.randint(0, 10 ** 6)}
        try:
            self.egg_file().write_text(json.dumps(egg), encoding="utf-8")
        except OSError:
            return
        self.st["egg_baseline"] = date.today().isoformat(); save_state(self.st)
        self.mood = "surprised"; self.queue_routine(self._bounce_steps(4))
        self.root.after(600, lambda: self.say(self.line("egg", "I found an egg."), ms=4000))

    def egg_tick(self, now):
        """Keep the egg by the pet that found it, sit on it now and then, hatch it when it's time."""
        egg = self.egg()
        if not egg or egg.get("by") != self.pid:
            if getattr(self, "egg_win", None): self.egg_win.close(); self.egg_win = None
            return
        px = round(self.size * 0.55)
        if not getattr(self, "egg_win", None):
            self.egg_win = F.Overlay(self.root, F.keyed(E.egg_image(px, egg.get("seed", 0)), COLORKEY_RGB), self.x - px, self.floor + self.size - px, COLORKEY, topmost=True)
            self.egg_win.label.bind("<Button-1>", lambda e: self.say(f"Hatches in about {max(1, round(E.hours_left(egg)))} hours." if E.hours_left(egg) > 0.5 else "Any minute now."))
        if self.state in ("idle", "walk", "sit", "routine", "dance", "sleep"):
            self.egg_win.move(self.x - px, self.floor + self.size - px)
        if E.hours_left(egg) <= 0 and self.state in ("idle", "walk", "sit"):
            self.hatch(egg)

    def hatch(self, egg):
        species = egg["species"]; sp = load_species(species)
        n = 2
        while state_path(f"{species}#{n}").exists(): n += 1
        pid = f"{species}#{n}"
        st = load_state(sp, pid)
        st["name"] = E.hatch_name(species, egg["variant"]); st["variant"] = egg["variant"] if egg["variant"].get("hue") is not None or egg["variant"]["name"] != "Natural" else None
        st["hatched"] = True; st["adopted"] = date.today().isoformat(); st["picks"] = [sp.get("signature")] if sp.get("signature") else []
        grant_free_picks(5)
        st["x"] = int(self.x) + self.size; st["mon"] = self.st.get("mon")
        save_state(st)
        try: self.egg_file().unlink()
        except OSError: pass
        if getattr(self, "egg_win", None): self.egg_win.close(); self.egg_win = None
        self.confetti(); self.mood = "surprised"; self.queue_routine(self._bounce_steps(6))
        self.root.after(500, lambda: self.say(f"It hatched. A {st['name']}.", ms=6000))
        subprocess.Popen(launch_command(pid), shell=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    def ignored(self):
        last = self.st.get("last_touch")
        return last is not None and time.time() - last > IGNORED_AFTER

    def lonely(self):
        last = self.st.get("last_touch")
        return last is not None and time.time() - last > LONELY_AFTER

    def line(self, key, *default):
        """One of this character's lines for the moment, or a plain one."""
        opts = self.sp.get("voice", {}).get(key) or list(default) or ["Okay."]
        return random.choice(opts)

    def tickle(self):
        self.touched(35)
        self.mood = "happy"
        self.queue_routine([("happy", "squash", 0, 0, 0, 90), ("happy", "stretch", 0, 0, -10, 110), ("happy", "idle", 0, 0, 10, 90),
                            ("happy", "squash", 0, 0, 0, 90), ("happy", "stretch", 0, 0, -8, 110), ("happy", "idle", 0, 0, 8, 200)])
        self.say(self.line("tickle", "Hehe.", "That tickles.", "Again."))
        save_state(self.st)

    def _fall_steps(self):
        steps, y = [], self.y
        while y < self.floor:
            ny = min(self.floor, y + 14); steps.append(ny - y); y = ny
        return steps or [0]

    # --- menu
    def on_menu(self, e):
        """The right click: the pet's panel (menu.py)."""
        self.touched(0)
        self.music_var = tk.BooleanVar(value=self.flag("music")); self.reacts_var = tk.BooleanVar(value=self.flag("reacts"))
        M.Panel(self, e.x_root, e.y_root)

    def toggle_autostart(self):
        try:
            set_starts_with_windows(self.pid, self.autostart.get())
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
        cmd = launch_command(self.pid).rsplit(" --pet ", 1)[0] + " --adopt"
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
        self.unsay(); set_starts_with_windows(self.pid, False)
        try:
            state_path(self.pid).unlink()
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
        save_state(self.st); save_owner_file(birthday=self.st["birthday"])
        for pid in adopted_ids():                                        # every pet in the house celebrates the same day
            if pid != self.pid:
                pst = pet_state(pid)
                if pst:
                    pst["birthday"] = self.st["birthday"]; state_path(pid).write_text(json.dumps(pst, indent=1), encoding="utf-8")
        self.say("Got it.")

    def grandfather_picks(self):
        """Picks a pet already had before ownership existed become the household's, once."""
        o = load_owned(); before = set(o["items"])
        o["items"] = sorted(before | {f"pick:{k}" for k in self.st.get("picks", [])} | {f"pick:{self.sp.get('signature')}"} - {"pick:None"})
        if set(o["items"]) != before: save_owned(o)

    def pick_dialog(self):
        """Every trick, habit and Together pick as a picture. Owned ones switch on and off; the rest unlock with a free pick or the shop."""
        self.grandfather_picks()
        win = tk.Toplevel(self.root); win.title("Picks"); win.attributes("-topmost", True); window_icon(win); win.configure(bg=CREAM)
        win.geometry(f"+{max(self.area[0], int(self.x) - 220)}+{max(self.area[1], int(self.y) - 560)}")
        win.keep = []
        chosen = set(self.st["picks"])
        head = tk.Label(win, text="", bg=CREAM, fg="#23213B", font=("Segoe UI", 12, "bold")); head.pack(padx=16, pady=(12, 2), anchor="w")
        sub = tk.Label(win, text="", bg=CREAM, fg="#6B6685", font=("Segoe UI", 9), wraplength=round(480 * SCALE), justify="left"); sub.pack(padx=16, pady=(0, 6), anchor="w")
        body = tk.Frame(win, bg=CREAM); body.pack(padx=12)
        HABIT = {"calm": "🧘", "sleepy": "😴", "clingy": "🫂", "showoff": "🌟"}
        catalog = [(g, it) for g in ("tricks", "together", "behaviours") for it in self.sp["catalog"].get(g, [])]

        def redraw(note=""):
            for c in body.winfo_children(): c.destroy()
            win.keep.clear()
            free = free_picks(); owned = sum(1 for _, it in catalog if owns_pick(it["id"]))
            head.configure(text=f"{self.st['name']}'s picks: {len(chosen)} on, {owned} of {len(catalog)} yours")
            sub.configure(text=note or (f"You have {free} free pick{'s' if free != 1 else ''} left. Click a locked one to make it yours. Click one you own to turn it on or off, and run as many as you like."
                                        if free else "Click one you own to turn it on or off, and run as many as you like. The locked ones are in the shop, one at a time or all at once."))
            for group, title in (("tricks", "Tricks"), ("together", "Together"), ("behaviours", "Habits")):
                items = self.sp["catalog"].get(group, [])
                if not items: continue
                tk.Label(body, text=title.upper(), bg=CREAM, fg="#6B6685", font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(6, 2))
                tiles = []
                for it in items:
                    if group == "behaviours":
                        ic = HABIT.get(it["id"], "⭐")
                    else:
                        m, po, y = M.PREVIEW.get(it["id"], ("happy", "idle", 0))
                        ic = M.pet_still(self.frames, m, po, y, self.st["wearing"], round(40 * SCALE), win.keep)
                    mine = owns_pick(it["id"])
                    tag = None if mine else ("free pick" if free else SHOP["items"].get(f"pick:{it['id']}", {}).get("price", "$0.99"))
                    tiles.append((ic, it["name"], lambda iid=it["id"]: click(iid), it["id"] in chosen and mine, tag))
                M.tile_grid(body, SCALE, tiles, cols=5, keep=win.keep)

        def click(iid):
            if owns_pick(iid):
                if iid in chosen and iid != self.sp.get("signature"):
                    chosen.discard(iid)
                else:
                    chosen.add(iid)
                redraw()
            elif free_picks() > 0:
                unlock_pick(iid, spend=True); chosen.add(iid)
                name = next(it["name"] for _, it in catalog if it["id"] == iid)
                redraw(f"{name} is yours now. {free_picks()} free pick{'s' if free_picks() != 1 else ''} left.")
            else:
                price = SHOP["items"].get(f"pick:{iid}", {}).get("price", "$0.99")
                redraw(f"That one is {price} on the site, or get all the picks for {SHOP['items'].get('picks:all', {}).get('price', '$9.99')}. After you buy, right-click any pet and choose Enter a code.")
                webbrowser.open(SHOP.get("store_url", ""))

        def save():
            self.st["picks"] = [it["id"] for _, it in catalog if it["id"] in chosen and owns_pick(it["id"])]
            save_state(self.st); win.destroy(); self.say("New tricks.")
        row = tk.Frame(win, bg=CREAM); row.pack(padx=16, pady=(10, 12), anchor="w")
        tk.Button(row, text="Save", command=save, padx=14, bg="#5A3FC0", fg="#FFFFFF", activebackground="#4A32A6", activeforeground="#FFFFFF", relief="flat", font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Button(row, text=f"Get all the picks, {SHOP['items'].get('picks:all', {}).get('price', '$9.99')}", command=lambda: webbrowser.open(SHOP.get("store_url", "")), padx=10).pack(side="left", padx=(8, 0))
        tk.Button(row, text="Close", command=win.destroy, padx=10).pack(side="left", padx=(8, 0))
        redraw()

    def closet_dialog(self):
        """Every shelf as pictures of the pet wearing the thing; the big preview on the right. Clicks go straight onto the desktop pet."""
        win = tk.Toplevel(self.root); win.title("Closet"); win.attributes("-topmost", True); window_icon(win); win.configure(bg=CREAM)
        win.geometry(f"+{max(self.area[0], int(self.x) - 300)}+{max(self.area[1], int(self.y) - 560)}")
        win.keep = []
        left = tk.Frame(win, bg=CREAM); left.pack(side="left", fill="y", padx=(16, 8), pady=12, anchor="n")
        right = tk.Frame(win, bg=CREAM); right.pack(side="left", padx=(8, 16), pady=12, anchor="n")
        tk.Label(left, text=f"{self.st['name']}'s closet", bg=CREAM, fg="#23213B", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        tk.Label(left, text="Click a picture. It goes on right away.", bg=CREAM, fg="#6B6685", font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 4))
        preview = tk.Label(right, bg=CREAM, bd=0); preview.pack()
        shelves = tk.Frame(left, bg=CREAM); shelves.pack(anchor="w")            # hats, the big shelf
        small = tk.Frame(right, bg=CREAM); small.pack(anchor="w", pady=(6, 0))  # the other shelves, under the preview

        def refresh():
            im = self.frames.compose("happy", "idle", 0, self.st["wearing"])
            bg = Image.new("RGBA", im.size, (255, 248, 240, 255)); bg.alpha_composite(im)
            px = round(150 * SCALE)
            preview.img = ImageTk.PhotoImage(bg.resize((px, px), Image.LANCZOS)); preview.configure(image=preview.img)
            self.show(*self.last_frame)

        def pick(shelf_id, item_id):
            self.st["wearing"][shelf_id] = item_id or None
            save_state(self.st); refresh(); redraw()

        def redraw():
            for c in list(shelves.winfo_children()) + list(small.winfo_children()): c.destroy()
            win.keep.clear()
            px = round(44 * SCALE); base = dict(self.st["wearing"]); n_small = 0
            for shelf in CLOSET["shelves"]:
                items = [it for it in shelf["items"] if self.frames.has_item(it["id"])]
                mine = [(h["name"], "my:" + h["id"]) for h in HM.load_hats(hats_dir())] if shelf["id"] == "hat" else []
                if not items and not mine: continue
                cur = self.st["wearing"].get(shelf["id"])
                if shelf["id"] == "hat":
                    host = shelves
                else:                                                            # the small shelves sit two by two under the preview
                    host = tk.Frame(small, bg=CREAM); host.grid(row=n_small // 2, column=n_small % 2, sticky="nw", padx=(0, 10)); n_small += 1
                tk.Label(host, text=shelf["name"].upper(), bg=CREAM, fg="#6B6685", font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(6, 2))
                tiles = [(M.pet_still(self.frames, "happy", "idle", 0, dict(base, **{shelf["id"]: None}), px, win.keep), "Nothing", lambda s=shelf["id"]: pick(s, None), not cur)]
                for it in items:
                    on = dict(base, **{shelf["id"]: it["id"]})
                    if owns(it["id"]):
                        tiles.append((M.pet_still(self.frames, "happy", "idle", 0, on, px, win.keep), it["name"], lambda s=shelf["id"], i=it["id"]: pick(s, i), cur == it["id"]))
                    else:
                        price = SHOP["items"].get(it["id"], {}).get("price", "")
                        tiles.append((M.pet_still(self.frames, "happy", "idle", 0, on, px, win.keep), it["name"], lambda: (win.destroy(), self.shop_dialog()), False, f"{price} in the shop"))
                for name, iid in mine:
                    tiles.append((M.pet_still(self.frames, "happy", "idle", 0, dict(base, **{"hat": iid}), px, win.keep), name, lambda s="hat", i=iid: pick(s, i), cur == iid))
                M.tile_grid(host, SCALE, tiles, cols=5 if host is shelves else 3, keep=win.keep)
            hm = tk.Frame(shelves, bg=CREAM); hm.pack(anchor="w", pady=(8, 0))
            tk.Button(hm, text="Hat maker...", command=lambda: (win.destroy(), self.hat_maker()), relief="flat", bg="#EFE7FF", padx=8, font=("Segoe UI", 9)).pack(side="left")
            tk.Button(hm, text="Close", command=win.destroy, padx=14).pack(side="left", padx=(8, 0))
        redraw(); refresh()

    def hat_maker(self):
        self.frames.forget_custom()
        HM.HatMaker(self, hats_dir(), SCALE)

    def save_state(self):
        save_state(self.st)

    def shop_dialog(self):
        """Everything the pet can do or wear, with a line on each. Prices and Buy buttons land here when extras exist."""
        win = tk.Toplevel(self.root); win.title("Shop"); win.attributes("-topmost", True); window_icon(win)
        win.configure(bg=CREAM)
        win.geometry(f"+{max(self.area[0], int(self.x) - 260)}+{max(self.area[1], int(self.y) - 520)}")
        tk.Label(win, text=f"Everything for {self.st['name']}", bg=CREAM, fg="#23213B", font=("Segoe UI", 12, "bold")).pack(padx=18, pady=(14, 2), anchor="w")
        tk.Label(win, text="Buy takes you to the site. You get a code by email and type it in here. Anything you buy works for every pet on this computer, for good.",
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
        tk.Label(right, text="Extras", bg=CREAM, fg="#5A3FC0", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(6, 2))
        for iid in ("picks:all", f"pet:{random.choice([s for s in species_ids() if s != self.sp['id']] or [self.sp['id']])}"):
            it = SHOP["items"].get(iid)
            if not it: continue
            row = tk.Frame(right, bg="#FFFFFF", highlightthickness=1, highlightbackground="#E8DFF3"); row.pack(fill="x", pady=2)
            tk.Label(row, text=it["name"], bg="#FFFFFF", fg="#23213B", font=("Segoe UI", 10, "bold"), anchor="w").grid(row=0, column=0, padx=(10, 4), pady=(5, 0), sticky="w")
            have = owns(iid) or (iid.startswith("picks") and owns("picks:all"))
            tk.Label(row, text="yours" if have else it["price"], bg="#FFFFFF", fg="#5A3FC0", font=("Segoe UI", 9, "bold")).grid(row=0, column=1, padx=(0, 10), pady=(5, 0), sticky="e")
            tk.Label(row, text=it.get("what", ""), bg="#FFFFFF", fg="#6B6685", font=("Segoe UI", 9), anchor="w", justify="left", wraplength=round(220 * SCALE)).grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 6), sticky="w")
            if not have:
                tk.Button(row, text="Buy", command=lambda: webbrowser.open(SHOP.get("store_url", "")), padx=10, font=("Segoe UI", 8)).grid(row=2, column=0, padx=10, pady=(0, 6), sticky="w")
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
        tk.Label(right, text="Eggs", bg=CREAM, fg="#5A3FC0", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(10, 2))
        tk.Label(right, text=f"Play with a pet on {E.GOOD_DAYS_FOR_EGG} different days ({E.GOOD_DAY_TOUCHES} touches a day counts) and it finds an egg. A day later it hatches into a new pet in a random color. Odds: {E.odds_text()}. You can't buy eggs.",
                 bg=CREAM, fg="#6B6685", font=("Segoe UI", 9), wraplength=round(210 * SCALE), justify="left").pack(anchor="w")
        foot = tk.Frame(win, bg=CREAM); foot.pack(pady=(8, 14))
        tk.Button(foot, text="Enter a code...", command=lambda: (win.destroy(), self.code_dialog()), padx=14).pack(side="left", padx=6)
        tk.Button(foot, text="Close", command=win.destroy, padx=14).pack(side="left", padx=6)

    def remember_place(self):
        self.st["x"] = int(self.x)
        self.st["mon"] = [int(self.x + self.size // 2), int(self.floor + self.size // 2)]
        save_state(self.st)

    def quit(self):
        self.remember_place(); self.unsay(); H.leave(self.pid); self.root.destroy()

    # --- other pets on this desktop
    def presence(self):
        mood, pose, yaw = self.last_frame
        return {"name": self.st["name"], "x": int(self.x), "y": int(self.y), "size": self.size, "facing": self.facing,
                "state": self.state, "area": list(self.area), "wearing": self.st["wearing"], "inside": self.inside, "mood": mood,
                "pose": pose, "yaw": yaw, "say": self.saying, "species": self.sp["id"], "variant": self.st.get("variant")}

    def playable(self):
        return self.state in ("idle", "walk", "sit") and self.mood != "sulky" and self.drag is None

    def mind_others(self):
        pid = self.pid
        H.announce(pid, self.presence())
        here = H.others(pid, self.area)
        now = time.time()
        for o in here:                                       # someone came out (or came back after a while): wave
            if now - self.seen.get(o["pid"], 0) > 20 and self.playable() and self.anim_t > 40:
                self.queue_routine([("happy", "wave1", 0, 0, 0, 170), ("happy", "wave2", 0, 0, 0, 170)] * 3 + [("happy", "idle", 0, 0, 0, 100)])
                self.root.after(200, lambda: self.say(self.line("hi", "Hi.")))
            self.seen[o["pid"]] = now
        cmd = S.take_command(pid)
        if cmd:
            self.on_command(cmd.get("cmd"), cmd)
        self.follow_reaction(now)
        plan = H.take_plan(pid)
        if plan and self.state not in ("together", "break", "held"):     # a play is a play: drop what you're doing and join
            other = next((o for o in here if o["pid"] == plan["a"]), None)
            if other:
                if self.state == "inside": self.come_out()
                self.routine = []; self.mood = "happy"
                if self.state == "hide": self.state = "idle"
                self.start_play(plan, "b", other)

    def play_now(self, kind):
        """The owner asked for a play: with everyone if it's a group kind and three or more are out, else with the nearest."""
        pid = self.pid
        here = H.others(pid, self.area)
        if not here:
            self.say("No one's here."); return
        if self.state in ("together", "break", "hide"):
            self.say("In a minute."); return
        self.routine = []; self.state = "idle"; self.mood = "happy"
        lead = 1.5
        for o in here:
            if o.get("inside"):                                           # in the house: called out, and the play waits for them
                self.call_out(o["pid"]); lead = 4.5
                o["x"] = int((self.house_here() or {}).get("door_x", o["x"]))
        other = min(here, key=lambda o: abs(o["x"] - self.x))
        if len(here) >= 2 and kind in H.GROUP_KINDS:
            group = [pid] + [o["pid"] for o in here]
            xs = [self.x] + [o["x"] for o in here]
            meet = int(sum(xs) / len(xs))
            meet = max(self.area[0] + self.size * (len(group) // 2 + 1), min(self.area[2] - self.size * (len(group) // 2 + 2), meet))
            seed = random.randint(0, 10 ** 6)
            plan = H.propose(kind, pid, other["pid"], meet, seed=seed, lead=lead, group=group, talk=build_talk(group, seed) if kind == "gossip" else None)
        else:
            if kind == "parade":
                kind = "chase"
            if kind == "hatswap" and not (self.st["wearing"].get("hat") and other.get("wearing", {}).get("hat")):
                self.say("We both need hats for that."); return
            meet = int((self.x + other["x"]) / 2)
            meet = max(self.area[0] + self.size, min(self.area[2] - self.size * 2, meet))
            seed = random.randint(0, 10 ** 6)
            plan = H.propose(kind, pid, other["pid"], meet, seed=seed, lead=lead, talk=build_talk([pid, other["pid"]], seed) if kind == "gossip" else None)
        if plan:
            self.start_play(plan, "a", other); self.touched(5)

    def call_out(self, pid):
        try:
            (H.base_dir() / "plans" / f"house-out-{pid}.json").write_text(json.dumps({"out": True, "ts": time.time()}), encoding="utf-8")
        except OSError:
            pass

    def maybe_play(self):
        """Now and then, ask another pet on this screen to do something together."""
        pid = self.pid
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
            seed = random.randint(0, 10 ** 6)
            plan = H.propose(kind, pid, other["pid"], meet, seed=seed, group=group, talk=build_talk(group, seed) if kind == "gossip" else None)
        else:
            kinds = list(H.KINDS)
            if not (self.st["wearing"].get("hat") and other.get("wearing", {}).get("hat")):
                kinds.remove("hatswap")
            kind = random.choice(kinds)
            meet = int((self.x + other["x"]) / 2)
            meet = max(self.area[0] + self.size, min(self.area[2] - self.size * 2, meet))
            seed = random.randint(0, 10 ** 6)
            plan = H.propose(kind, pid, other["pid"], meet, seed=seed, talk=build_talk([pid, other["pid"]], seed) if kind == "gossip" else None)
        if plan:
            self.start_play(plan, "a", other)
        return bool(plan)

    def start_play(self, plan, role, other):
        me = dict(self.presence(), pid=self.pid)
        steps, says, intro = H.script(plan["kind"], role, me, other, plan, picks=self.st["picks"])
        delay = max(0, int((plan["t0"] - time.time()) * 1000))
        self.state = "idle"; self.routine = []; self.until = time.time() + delay / 1000 + 5   # hold still until it starts
        self.play_until = time.time() + delay / 1000 + sum(s[5] for s in steps) / 1000 + 1     # no reactions mid-play
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
        elif tid == "dab":
            self.queue_routine([("happy", "squash", 0, 0, 0, 120), ("happy", "dab", 0, 0, 0, 1100), ("happy", "idle", 0, 0, 0, 200)])
        elif tid == "flex":
            self.queue_routine([("happy", "squash", 0, 0, 0, 120), ("happy", "flex", 0, 0, -3, 1400), ("happy", "idle", 0, 0, 3, 200)])
        elif tid == "moonwalk":
            away = -1 if self.x > (self.area[0] + self.area[2]) / 2 else 1
            back = [("happy", "walk1" if i % 2 == 0 else "walk2", 300 if away > 0 else 60, 5 * away, 0, 70) for i in range(22)]   # facing one way, sliding the other
            self.queue_routine(back + [("happy", "idle", 0, 0, 0, 250)] + [("happy", "walk1" if i % 2 == 0 else "walk2", 60 if away > 0 else 300, -5 * away, 0, 70) for i in range(22)] + [("happy", "idle", 0, 0, 0, 200)])
        elif tid == "wave":
            self.queue_routine([("happy", "wave1", 0, 0, 0, 170), ("happy", "wave2", 0, 0, 0, 170)] * 4 + [("happy", "idle", 0, 0, 0, 100)])
            self.root.after(300, lambda: self.say(self.line("hi", "Hi.")))
        elif tid == "rot":                                   # face down, for a good while; a click gets it up
            self.bit = "rot"
            self.queue_routine([("happy", "squash", 0, 0, 0, 120), ("sulky", "lie", 0, 0, 0, random.randint(20000, 40000)),
                                ("sleepy", "lie", 0, 0, 0, 600), ("happy", "squash", 0, 0, 0, 150), ("happy", "idle", 0, 0, 0, 100)])
            self.root.after(900, lambda: self.say(self.line("rot", "Leave me here."), ms=3000))
        elif tid == "spinout":                               # faster and faster, then dizzy, then flat
            yaws = (0, 60, 120, 180, 240, 300)
            steps = []
            for ms in (90, 80, 70, 60, 50, 45, 40, 35, 30, 30, 28, 26, 25, 25, 25, 25):
                steps += [("happy", "idle", y, 0, 0, ms) for y in yaws]
            steps += [("surprised", "idle", 60 if i % 2 == 0 else 300, 5 if i % 2 == 0 else -5, 0, 140) for i in range(8)]
            steps += [("surprised", "stretch", 0, 0, 0, 120), ("surprised", "lie", 0, 0, 0, 1500), ("happy", "squash", 0, 0, 0, 150), ("happy", "idle", 0, 0, 0, 100)]
            self.queue_routine(steps)
            self.root.after(5200, lambda: self.say(self.line("spinout", "Whoa.")))
        elif tid == "faint":                                 # a collapse with a full recovery
            self.queue_routine([("surprised", "idle", 0, 0, 0, 350), ("surprised", "stretch", 0, 0, -4, 220), ("surprised", "squash", 0, 0, 4, 90),
                                ("surprised", "lie", 0, 0, 0, 1800), ("sleepy", "lie", 0, 0, 0, 1500), ("happy", "squash", 0, 0, 0, 150), ("happy", "idle", 0, 0, 0, 100)])
            self.root.after(4300, lambda: self.say(self.line("faint", "I'm fine.")))
        elif tid == "backflip":
            self.queue_routine([("happy", "squash", 0, 0, 0, 110), ("happy", "stretch", 0, 0, -8, 70), ("happy", "idle", 60, 0, -16, 60), ("happy", "idle", 180, 0, -8, 60),
                                ("happy", "idle", 300, 0, 10, 60), ("happy", "squash", 0, 0, 22, 110), ("happy", "idle", 0, 0, 0, 150)])
        elif tid == "sneak":
            away = 1 if self.x < (self.area[0] + self.area[2]) / 2 else -1
            yaw = 60 if away > 0 else 300
            steps = []
            for i in range(8):
                steps += [("surprised", "squash", yaw, 3 * away, 0, 170), ("surprised", "walk1" if i % 2 == 0 else "walk2", yaw, 3 * away, 0, 170)]
            self.queue_routine(steps + [("happy", "idle", 0, 0, 0, 150)])
            self.root.after(500, lambda: self.say("Shh.", ms=1500))
        elif tid == "panic":
            steps = []
            for leg in (1, -1, 1, -1):
                steps += [("surprised", "walk1" if i % 2 == 0 else "walk2", 60 if leg > 0 else 300, 14 * leg, 0, 45) for i in range(8)]
            self.queue_routine(steps + [("surprised", "idle", 0, 0, 0, 300), ("happy", "idle", 0, 0, 0, 100)])
            self.root.after(200, lambda: self.say("AAAAAA.", ms=2400))
        elif tid == "meditate":
            self.queue_routine([("sleepy", "sit", 0, 0, -2, 700), ("sleepy", "sit", 0, 0, 2, 700)] * 5 + [("happy", "sit", 0, 0, 0, 400), ("happy", "idle", 0, 0, 0, 100)])
            self.root.after(1200, lambda: self.say("Ohm.", ms=2000))
        elif tid == "loaf":
            self.queue_routine([("happy", "squash", 0, 0, 0, 14000), ("happy", "idle", 0, 0, 0, 200)])
            self.root.after(600, lambda: self.say("Loaf.", ms=1800))
        elif tid == "wiggle":
            self.queue_routine([("happy", "squash", 60, 0, 0, 90), ("happy", "stretch", 300, 0, 0, 90)] * 8 + [("happy", "idle", 0, 0, 0, 100)])
        elif tid == "bow":
            self.queue_routine([("happy", "stretch", 0, 0, 0, 300), ("happy", "squash", 0, 0, 0, 1100), ("happy", "idle", 0, 0, 0, 200)])
            self.root.after(400, lambda: self.say("Thank you. Thank you.", ms=1800))
        elif tid == "rockout":
            self.queue_routine([("happy", "game", 0, 0, -4, 120), ("happy", "game", 0, 0, 4, 120), ("happy", "wave1", 0, 0, 0, 100), ("happy", "wave2", 0, 0, 0, 100)] * 5 + [("happy", "idle", 0, 0, 0, 100)])
            self.root.after(300, lambda: self.say("Rock on.", ms=1800))
        elif tid == "stare":
            self.queue_routine([("happy", "idle", 0, 0, 0, 9000), ("happy", "idle", 0, 0, 0, 100)])
            self.root.after(3000, lambda: self.say("...", ms=2500))
        elif tid == "jumpscare":
            self.hide()
            def boo():
                if self.state != "hide": return
                self.state = "idle"; self.mood = "surprised"
                self.queue_routine([("surprised", "stretch", 0, 0, -22, 120), ("surprised", "idle", 0, 0, 22, 120), ("surprised", "stretch", 0, 0, -10, 100), ("surprised", "idle", 0, 0, 10, 300), ("happy", "idle", 0, 0, 0, 100)])
                self.say("Boo.", ms=1800)
            self.root.after(2400, boo)
        elif tid == "yoga":
            self.queue_routine([("sleepy", "stretch", 0, 0, 0, 1500), ("sleepy", "sit", 0, 0, 0, 1500), ("sleepy", "lie", 0, 0, 0, 2000), ("happy", "stretch", 0, 0, 0, 600), ("happy", "idle", 0, 0, 0, 200)])
            self.root.after(4500, lambda: self.say("Namaste.", ms=1800))
        elif tid == "shiver":
            self.queue_routine([("surprised", "idle", 0, 2, 0, 40), ("surprised", "idle", 0, -2, 0, 40)] * 22 + [("happy", "idle", 0, 0, 0, 100)])
            self.root.after(300, lambda: self.say("Brr.", ms=1500))
        elif tid == "sneeze":
            self.queue_routine([("happy", "stretch", 0, 0, -4, 600), ("surprised", "stretch", 0, 0, -2, 140), ("surprised", "squash", 0, 6, 6, 140), ("happy", "idle", 0, -6, 0, 300)])
            self.root.after(750, lambda: self.say("Achoo.", ms=1500))
        elif tid == "karate":
            self.queue_routine([("happy", "dab", 0, 8, 0, 220), ("happy", "flex", 0, -8, 0, 220)] * 3 + [("happy", "idle", 0, 0, 0, 150)])
            self.root.after(250, lambda: self.say("Hi-ya.", ms=1500))
        elif tid == "robot":
            self.queue_routine([step for y in (0, 60, 120, 180, 240, 300) for step in (("happy", "idle", y, 0, 0, 230), ("happy", "squash", y if y in (0, 60, 300) else 0, 0, 0, 90))] + [("happy", "idle", 0, 0, 0, 150)])
            self.root.after(500, lambda: self.say("Beep. Boop.", ms=2000))
        elif tid == "hype":
            self.queue_routine([("happy", "wave1", 0, 0, -10, 110), ("happy", "wave2", 0, 0, 10, 110)] * 6 + [("happy", "idle", 0, 0, 0, 100)])
            self.root.after(300, lambda: self.say("Let's go.", ms=1800))
        elif tid == "slowclap":
            self.queue_routine([("happy", "wave1", 0, 0, 0, 600), ("happy", "wave2", 0, 0, 0, 600)] * 3 + [("happy", "idle", 0, 0, 0, 100)])
            self.root.after(1500, lambda: self.say("Wow.", ms=2000))
        elif tid == "kiss":
            self.queue_routine([("happy", "wave2", 0, 0, 0, 450), ("happy", "stretch", 0, 0, -3, 300), ("happy", "idle", 0, 0, 3, 200)])
            self.root.after(500, lambda: self.say("Mwah.", ms=1500))
        elif tid == "parkour":
            away = 1 if self.x < (self.area[0] + self.area[2]) / 2 else -1
            hop = [("happy", "stretch", 60 if away > 0 else 300, 10 * away, -14, 70), ("happy", "idle", 60 if away > 0 else 300, 10 * away, 14, 70)] * 5
            back = [("happy", "stretch", 300 if away > 0 else 60, -10 * away, -14, 70), ("happy", "idle", 300 if away > 0 else 60, -10 * away, 14, 70)] * 5
            self.queue_routine(hop + [("happy", "squash", 0, 0, 0, 120)] + back + [("happy", "squash", 0, 0, 0, 120), ("happy", "idle", 0, 0, 0, 100)])
            self.root.after(300, lambda: self.say("Parkour.", ms=1500))
        elif tid == "chase":
            self.chase_until = time.time() + 7; self.state = "chase"; self.routine = []; self.anim_t = 0
            self.say("Get back here.", ms=1800)
        elif tid == "snack":
            self.queue_routine([("happy", "eat1", 0, 0, 0, 300), ("happy", "eat2", 0, 0, 0, 300)] * 5 + [("happy", "idle", 0, 0, 0, 100)])
            self.root.after(900, lambda: self.say("Crunch.", ms=1500))
        elif tid == "homework":
            self.queue_routine([("happy", "study", 0, 0, 0, 4000), ("sleepy", "study", 0, 0, 0, 2500), ("surprised", "idle", 0, 0, 0, 400), ("happy", "stretch", 0, 0, 0, 400), ("happy", "idle", 0, 0, 0, 100)])
            self.root.after(1500, lambda: self.say("Ugh.", ms=1500))
        elif tid == "scream":
            self.queue_routine([("surprised", "stretch", 0, 0, -3, 1600), ("surprised", "idle", 0, 0, 3, 300), ("happy", "idle", 0, 0, 0, 100)])
            self.root.after(100, lambda: self.say("AAAAAAAAA.", ms=1700))
        elif tid == "statue":
            self.queue_routine([("happy", "stretch", 0, 0, 0, 12000), ("happy", "idle", 0, 0, 0, 200)])
            self.root.after(4000, lambda: self.say("...", ms=2000))
        elif tid == "sideeye":                               # turns away and gives you a look
            px = self.root.winfo_pointerx()
            yaw = 300 if px > self.x + self.size // 2 else 60          # away from the cursor's side
            self.queue_routine([("sulky", "idle", yaw, 0, 0, 1900), ("happy", "idle", 0, 0, 0, 150)])
            self.root.after(700, lambda: self.say(self.line("sideeye", "Mm-hm."), ms=1800))
        if by_owner:
            self.touched(10)

    # --- updates: ask once a day, install on request
    def check_update(self):
        def work():
            tag = newest_version()
            if tag and version_tuple(tag) > version_tuple(VERSION):
                self.update_to = tag
                self.root.after(0, lambda: self.say(f"There's a newer me, {tag.lstrip('v')}. Right-click me to update.", ms=6000))
        threading.Thread(target=work, daemon=True).start()
        self.root.after(6 * 60 * 60 * 1000, self.check_update)

    def do_update(self):
        """Download the installer and run it quietly. It closes every pet, swaps the files, and brings everyone back out."""
        if self.updating:
            return
        self.updating = True
        self.say("Updating. Back in a minute.", ms=None)
        def work():
            setup = update_dir() / "PerchlingsSetup.exe"
            try:
                req = urllib.request.Request(SETUP_URL, headers={"User-Agent": f"Perchlings/{VERSION}"})
                with urllib.request.urlopen(req, timeout=60) as r, open(setup, "wb") as f:
                    while True:
                        chunk = r.read(1 << 16)
                        if not chunk: break
                        f.write(chunk)
                if setup.stat().st_size < 5_000_000:
                    raise OSError("short download")
            except Exception:
                self.root.after(0, lambda: (setattr(self, "updating", False), self.say("Couldn't get it. I'll try again later.")))
                return
            self.root.after(0, lambda: self.remember_place())
            subprocess.Popen([str(setup), "/SILENT", "/FORCECLOSEAPPLICATIONS", "/NORESTART", "/SUPPRESSMSGBOXES"], close_fds=True,
                             creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
        threading.Thread(target=work, daemon=True).start()

    def on_command(self, cmd, data=None):
        """Buttons on the streamer stage, and the test run. data is the whole command file."""
        data = data or {}
        if self.state == "held":
            return
        if self.state == "inside" and cmd not in ("out", "inside"):       # come out first, then do it
            self.come_out(); self.root.after(2200, lambda: self.on_command(cmd, data)); return
        if cmd == "tickle": self.tickle()
        elif cmd == "wave": self.routine = []; self.state = "idle"; self.do_trick("wave")
        elif cmd == "dance": self.dance_force_until = time.time() + 20; self.routine = []; self.state = "idle"; self.until = 0
        elif cmd == "gossip": self.play_now("gossip")
        elif cmd == "party": self.party("stream")
        elif cmd == "out" and self.state == "inside": self.come_out()
        elif cmd == "play": self.play_now(data.get("kind", "dance"))
        elif cmd == "trick": self.routine = []; self.state = "idle"; self.do_trick(data.get("id", "bounce"), by_owner=False)
        elif cmd == "together": self.do_together(data.get("id", "study"), by_owner=False)
        elif cmd == "inside": self.go_inside(data.get("room", "living"), float(data.get("seconds", 15 * 60)))
        elif cmd == "hide": self.hide()
        elif cmd == "unhide": self.unhide()
        elif cmd == "break": self.next_break = 0; self.take_break(data.get("kind"))
        elif cmd == "nap": self.nap_now()
        elif cmd == "clip": self.take_clip()
        elif cmd == "note": self.add_note(str(data.get("text", "")))
        elif cmd == "wear":
            item = data.get("hat"); self.st["wearing"]["hat"] = item or None; save_state(self.st); self.show(*self.last_frame)

    def open_stage(self):
        cmd = launch_command(self.pid).rsplit(" --pet ", 1)[0] + " --stage"
        subprocess.Popen(cmd, shell=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    # --- the fun parts
    def set_flag(self, key, on):
        """Music and reactions are household switches: one setting for every pet, so no pet is quietly left out."""
        self.st[key] = bool(on); save_state(self.st); save_owner_file(**{key: bool(on)}); self.flags_read = 0

    def flag(self, key):
        """A household switch (music, reacts), read from owner.json with a short cache; on unless switched off."""
        if time.time() - self.flags_read > 1.5:
            self.flags = owner_file(); self.flags_read = time.time()
        return bool(self.flags.get(key, True))

    def sign_dialog(self):
        text = simpledialog.askstring("A sign", "What should the sign say?", parent=self.root)
        if text and text.strip():
            self.sign = text.strip()[:90]; self.sign_until = time.time() + 30
            self.routine = []; self.state = "sign"; self.mood = "happy"; self.touched(5)

    def take_clip(self):
        """Eight seconds of this pet on your real desktop, as a GIF, with its own bit in the middle. Opens the folder after."""
        if getattr(self, "clipping", False):
            return
        self.clipping = True
        S = self.size
        def where():                                   # the pet's window is S tall at (x, y); room above for the bubble
            return (self.x - S * 0.6, self.y - S * 0.9, self.x + S * 1.6, self.y + S * 1.05)
        def done(path):
            self.clipping = False
            if path:
                self.root.after(0, lambda: (self.say("Clip saved to Pictures."), self.touched(5)))
                try: os.startfile(path.parent)
                except OSError: pass
            else:
                self.root.after(0, lambda: self.say("Couldn't record that."))
        self.unsay()
        F.record_clip(where, seconds=8, fps=12, name=self.st["name"], done=done)
        sig = self.sp.get("signature")
        if sig and self.state in ("idle", "walk", "sit"):
            self.root.after(700, lambda: (setattr(self, "routine", []), setattr(self, "state", "idle"), self.do_trick(sig, by_owner=False)))

    def take_photo(self):
        try:
            path = F.photo(self.frames.compose(self.mood if self.mood != "sulky" else "happy", "idle", 0, self.st["wearing"]), self.st["name"])
            self.say("Saved to Pictures."); self.touched(5)
            os.startfile(path.parent)
        except Exception:
            self.say("Couldn't save that.")

    def party(self, why):
        """Confetti and a party hat for a few minutes. Everyone in the household gets the memo."""
        self.party_until = time.time() + 180
        if owns("party") and self.st["wearing"].get("hat") != "party":
            self.party_hat_before = self.st["wearing"].get("hat"); self.st["wearing"]["hat"] = "party"
        self.confetti()
        try:
            (H.base_dir() / "party.json").write_text(json.dumps({"ts": time.time(), "why": why}), encoding="utf-8")
        except OSError:
            pass

    def confetti(self):
        w, h = self.size * 2, self.size * 2
        frames = F.confetti_frames(w, h, COLORKEY_RGB, n=18)
        ov = F.Overlay(self.root, frames[0], self.x - self.size // 2, self.y - self.size, COLORKEY)
        def step(i=0):
            if i >= len(frames): ov.close(); return
            ov.set(frames[i]); ov.move(self.x - self.size // 2, self.y - self.size); self.root.after(110, lambda: step(i + 1))
        step()

    def set_chaos(self, level):
        self.st["chaos"] = level; save_state(self.st)
        self.next_mischief = time.time() + (random.uniform(2 * 60, 5 * 60) if level == "menace" else random.uniform(15 * 60, 35 * 60))
        self.say({"sweet": "Okay. I'll be good.", "cheeky": "Hehe.", "menace": self.line("hehe", "Hehe.")}[level])

    def do_mischief(self):
        menace = self.st.get("chaos", "cheeky") == "menace"
        kind = random.choice(("cursor", "footprints", "note", "spinout", "sideeye", "rot") if menace else ("footprints", "note", "sideeye"))
        self.mood = "happy"; self.routine = []
        if kind in ("spinout", "sideeye", "rot"):
            self.do_trick(kind, by_owner=False)
            self.next_mischief = time.time() + (random.uniform(6 * 60, 12 * 60) if menace else random.uniform(20 * 60, 40 * 60)); return
        if kind == "cursor":
            self.steal_until = time.time() + 1.6; self.state = "steal"; self.say(self.line("mine", "Mine."), ms=1400)
        elif kind == "footprints":
            away = 1 if self.x < (self.area[0] + self.area[2]) / 2 else -1
            self.mischief_note = ("prints", away)
            self.queue_routine([("happy", "walk1" if i % 2 == 0 else "walk2", 60 if away > 0 else 300, 7 * away, 0, 60) for i in range(26)] + [("happy", "idle", 0, 0, 0, 200)])
        else:
            away = 1 if self.x < (self.area[0] + self.area[2]) / 2 else -1
            text = random.choice([f"be nice to {self.st['name']}", "tickle me", "back in 5 min", "do not disturb", f"{self.st['name']} was here"])
            img = F.note_image(SCALE, text, COLORKEY_RGB)
            ov = F.Overlay(self.root, img, self.x + (self.size if away > 0 else -140 * SCALE), self.y + self.size * 0.35, COLORKEY, ms=32000)
            self.mischief_note = ("note", away, ov)
            self.queue_routine([("surprised", "walk1" if i % 2 == 0 else "walk2", 60 if away > 0 else 300, 6 * away, 0, 60) for i in range(30)] + [("happy", "squash", 0, 0, 0, 150), ("happy", "idle", 0, 0, 0, 200)])
            self.root.after(200, lambda: self.say(self.line("hehe", "Hehe."), ms=1500))
        self.next_mischief = time.time() + (random.uniform(6 * 60, 12 * 60) if menace else random.uniform(20 * 60, 40 * 60))

    def trail_tick(self):
        """The effect from the closet, drawn behind the pet every other tick."""
        kind = self.st["wearing"].get("effect")
        if not kind or not owns(kind) or self.state in ("inside", "hide", "held"):
            if self.trail is not None: self.trail.close(); self.trail = None
            return
        if self.trail is None or self.trail.kind != kind:
            if self.trail is not None: self.trail.close()
            self.trail = F.Trail(self.root, kind, COLORKEY, COLORKEY_RGB, SCALE); self.root.lift()
        if self.anim_t % 2 == 0:
            if self.state in ("walk", "chase", "dance"): moving = 1 if self.facing > 0 else -1
            elif self.state == "routine" and self.routine and self.routine[0][3] != 0: moving = 1 if self.routine[0][3] > 0 else -1
            else: moving = 0
            self.trail.tick(self.x, self.y, self.size, moving, self.floor)

    def set_size(self, size):
        """Small, medium or large, kept in the state and applied right away."""
        self.st["size"] = size; save_state(self.st)
        self.size = round(self.sp.get("display_px", 128) * SCALE * self.growth() * {"small": 0.75, "medium": 1.0, "large": 1.3}.get(size, 1.0))
        self.frames = Frames(self.sp["id"], self.size, variant=self.st.get("variant"))
        self.floor = self.area[3] - self.size + round(8 * SCALE); self.y = self.floor; self.place(); self.show(*self.last_frame)

    def keep_tick(self):
        try:
            keep_household()
        except Exception:
            pass
        self.root.after(30000, self.keep_tick)

    def mischief_tick(self):
        """Footprints and the note follow the pet while its routine runs."""
        if not self.mischief_note or self.state != "routine":
            if self.mischief_note and self.mischief_note[0] == "note" and self.state != "routine":
                self.mischief_note = None
            return
        if self.mischief_note[0] == "prints":
            if self.anim_t % 60 == 0 or self.anim_t == 0:
                away = self.mischief_note[1]
                img = F.footprint_image(SCALE, away, COLORKEY_RGB)
                F.Overlay(self.root, img, self.x + self.size * 0.4 - away * 10, self.y + self.size * 0.86, COLORKEY, ms=9000, topmost=False)
        elif self.mischief_note[0] == "note":
            _, away, ov = self.mischief_note
            ov.move(self.x + (self.size * 0.9 if away > 0 else -120 * SCALE), self.y + self.size * 0.35)

    def reactive(self):
        """Free to react to the owner: the reactions toggle is on and the pet is idle, walking, sitting, dancing, chasing,
        or in the middle of a trick it started itself. Not in a play, not in your hand, not asleep, hiding, inside or behind
        the curtain."""
        if not self.flag("reacts") or self.drag or time.time() < self.play_until:
            return False
        if self.state == "routine":
            return self.bit is None and self.after_routine is None
        return self.state in ("idle", "walk", "sit", "dance", "chase")

    def react_to(self, kind, now):
        """One reaction, by name. The hop for fast typing needs the pet free to move; otherwise it just says the line."""
        self.react_seen = now
        setattr(self, "last_" + kind, now)
        lines = {"cheer": ("cheer", "Go go go.", "Look at you go.", "Fast fingers."), "oops": ("oops", "Oops.", "Undo, undo, undo.", "That bad?"),
                 "saved": ("saved", "Saved. Again."), "easy": ("easy", "Easy.", "It's not going anywhere.", "Breathe.")}[kind]
        if kind == "cheer" and self.state in ("idle", "walk", "sit"):
            self.queue_routine(self._bounce_steps(2)); self.root.after(300, lambda: self.say(self.line(*lines)))
        else:
            self.say(self.line(*lines))

    def reactions(self, now):
        """Small responses to what the owner is doing right now, shared across the household.

        Every pet counts the keys itself, but the first one to notice a burst writes it to household/react.json and the
        others join in from mind_others(), and the cooldown per kind lives in that file too, so one typing burst gets a
        line from every pet that is free, at the same moment, and none of them fires again until the household's cooldown
        is over. Asleep, in the house, behind the curtain, hiding, in a play or in your hand a pet stays quiet."""
        if not self.flag("reacts"):
            return
        if self.anim_t % 2 == 0:
            self.keys.poll()
        if not self.reactive():
            return
        kind = None
        if len(self.keys.undo_times) >= 3: kind = "oops"
        elif len(self.keys.save_times) >= 3: kind = "saved"
        elif self.keys.typing_rate() >= 4.0: kind = "cheer"                 # a real burst: 16 keys in four seconds
        elif self.keys.click_rate() >= 3: kind = "easy"
        if kind:
            if kind == "oops": self.keys.undo_times.clear()
            if kind == "saved": self.keys.save_times.clear()
            shared = load_react(); last = shared.get("last", {})
            if now - max(last.get(kind, 0), getattr(self, "last_" + kind, 0)) >= REACT_COOLDOWN[kind]:
                last[kind] = now; shared.update(kind=kind, ts=now, by=self.pid, last=last)
                try:
                    react_file().write_text(json.dumps(shared), encoding="utf-8")
                except OSError:
                    pass
                self.react_to(kind, now)
        h, m = datetime.now().hour, datetime.now().minute
        if h == 0 and m == 0 and self.midnight_done != date.today() and self.state in ("idle", "walk", "sit"):
            self.midnight_done = date.today(); self.queue_routine([("sleepy", "stretch", 0, 0, 0, 900), ("happy", "idle", 0, 0, 0, 100)]); self.root.after(200, lambda: self.say("It's midnight."))

    def follow_reaction(self, now):
        """Another pet noticed a burst: react too, once, if free."""
        r = load_react()
        ts = r.get("ts", 0)
        if ts > self.react_seen and now - ts < 4 and r.get("by") != self.pid and r.get("kind") in REACT_COOLDOWN and self.reactive():
            self.react_to(r["kind"], now)

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
                self.say(self.line("meal", "That was good."))
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

    # --- the house
    def house_here(self):
        h = house_info()
        return h if h and list(h.get("area", [])) == list(self.area) else None

    def go_inside(self, room, seconds):
        """Walk to the front door, then be in that room until the time is up or the house calls you out."""
        h = self.house_here()
        if not h or self.state in ("held", "together"):
            return False
        target = int(h["door_x"] - self.size // 2)
        steps, _ = H.walk_to(int(self.x), target, self.size, speed=6)
        steps += [("happy", "idle", 0, 0, 0, 200)]
        self.unsay(); self.mood = "happy"
        def enter():
            self.inside = room; self.inside_until = time.time() + seconds
            self.state = "inside"; self.routine = []; self.root.withdraw()
        self.after_routine = enter
        self.queue_routine(steps)
        return True

    def come_out(self):
        h = self.house_here()
        self.inside = None; self.after_routine = None
        if h:
            self.x = max(self.area[0], min(self.area[2] - self.size, int(h["door_x"] - self.size // 2)))
        self.y = self.floor; self.place(); self.root.deiconify()
        self.state = "idle"; self.mood = "happy"; self.until = time.time() + 1
        away = -1 if self.x > (self.area[0] + self.area[2]) / 2 else 1
        self.queue_routine([("happy", "stretch", 0, 0, 0, 300)] + [("happy", "walk1" if i % 2 == 0 else "walk2", 60 if away > 0 else 300, 6 * away, 0, 45) for i in range(30)] + [("happy", "idle", 0, 0, 0, 100)])

    def called_out(self):
        f = H.base_dir() / "plans" / f"house-out-{self.pid}.json"
        if f.exists():
            try: f.unlink()
            except OSError: pass
            return True
        return False

    # --- a break behind the curtain; we don't watch
    def take_break(self, kind=None):
        """A bathroom or shower break. In the house's bathroom when there is one on this screen, else behind a curtain
        right here. kind: "bath", "shower", or None for its own choice (always the bathroom after a meal). Returns True if it went."""
        if self.state in ("held", "together", "break", "inside"):
            return False
        if self.house_here() and self.go_inside("bathroom", random.uniform(25, 45)):
            self.after_meal = False; self.next_break = time.time() + random.uniform(25 * 60, 60 * 60)
            self.root.after(150, lambda: self.say("Be right back.", ms=1600)); return True
        self.break_kind = kind if kind in ("bath", "shower") else (random.choice(("bath", "bath", "shower")) if not getattr(self, "after_meal", False) else "bath")
        self.after_meal = False
        self.routine = []; self.bit = None; self.state = "break"; self.anim_t = 0
        self.until = time.time() + random.uniform(14, 24)
        self.next_break = time.time() + random.uniform(25 * 60, 60 * 60)
        self.say("Be right back.", ms=1600)
        return True

    # --- hide: turn into a folder until found
    def hide(self):
        self.routine = []; self.state = "hide"; self.anim_t = 0; self.until = float("inf"); self.unsay()

    def unhide(self):
        if self.state != "hide": return
        self.state = "idle"; self.until = time.time() + 2; self.mood = "happy"
        self.queue_routine(self._bounce_steps(3)); self.say(self.line("found", "Found me.")); self.touched(10)

    # --- things the panel asks for
    def busy(self):
        """States the owner has to wait out (or end by clicking the pet) before asking for something else."""
        return self.state in ("held", "together", "break", "inside")

    def nap_now(self):
        """A nap right now: in the bedroom when the house is on this screen, else right where it stands."""
        if self.busy():
            self.say("In a minute."); return
        self.routine = []; self.bit = None; self.touched(5)
        if self.house_here() and self.go_inside("bedroom", random.uniform(120, 240)):
            self.next_house_nap = time.time() + random.uniform(20 * 60, 45 * 60); return
        self.mood = "sleepy"; self.state = "sleep"; self.until = time.time() + random.uniform(25, 45)

    def dance_now(self, seconds=30):
        """Dance for a while, music or not. Every pet on the desktop keeps the same beat, so two of them dance together."""
        if self.busy() or self.state == "hide":
            self.say("In a minute."); return
        self.routine = []; self.bit = None; self.touched(5)
        self.dance_force_until = time.time() + seconds; self.dance_rest_until = 0
        if self.state != "dance":
            self.state = "idle"; self.mood = "happy"; self.until = 0

    def stop_dancing(self):
        self.dance_force_until = 0; self.dance_rest_until = time.time() + 120
        if self.state == "dance":
            self.state = "idle"; self.until = time.time() + 1

    def party_now(self):
        """Confetti and party hats for the whole household, because the owner said so."""
        if self.state in ("held", "inside"):
            self.say("In a minute."); return
        self.touched(5); self.party("owner")
        if self.state not in ("together", "break", "hide"):
            self.mood = "happy"; self.routine = []; self.queue_routine(self._bounce_steps(4))
        self.root.after(300, lambda: self.say(random.choice(["Party.", "Everyone, hats on.", "Confetti."]), ms=2200))

    def egg_status(self):
        """(headline, detail lines) for the panel's Egg page."""
        egg = self.egg()
        if egg:
            by = egg.get("by", "")
            who = pet_state(by).get("name", by) if by != self.pid else None
            left = E.hours_left(egg)
            head = f"{who} found an egg." if who else "I found an egg."
            when = "It hatches any minute now." if left < 0.5 else f"It hatches in about {max(1, round(left))} hour{'s' if round(left) != 1 else ''}."
            return head, [when, "It sits on the taskbar next to whoever found it. Click it for the time left.", f"Odds for its color: {E.odds_text()}."]
        if len(adopted_ids()) >= E.MAX_PETS:
            return "The household is full.", [f"{E.MAX_PETS} pets is the limit. Let one go to make room for an egg."]
        good = self.good_days(); need = E.GOOD_DAYS_FOR_EGG; left = max(0, need - good)
        today = self.st["care"].get(date.today().isoformat(), 0)
        head = f"An egg in {left} more good day{'s' if left != 1 else ''}."
        lines = [f"A good day is {E.GOOD_DAY_TOUCHES} touches: a hover, a click, a drag, or opening this panel.",
                 f"Today so far: {today} touch{'es' if today != 1 else ''}. {good} of {need} good days done.",
                 f"An egg hatches a day later into a new pet in a rolled color. Odds: {E.odds_text()}.",
                 f"Up to {E.MAX_PETS} pets in a household. Eggs are never sold."]
        return head, lines

    # --- the house, from the panel: the house is its own program, so it gets told through a command file
    def house_cmd(self, cmd, **kw):
        S.command("house", cmd, **kw)

    def bring_out_house(self):
        """Start the house if there isn't one, or call it over to this screen."""
        h = house_info()
        if h is None:
            subprocess.Popen(house_command(), shell=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.say("Here comes the house.", ms=2200)
        elif list(h.get("area", [])) != list(self.area):
            self.house_cmd("move", area=list(self.area)); self.say("Over here, house.", ms=2200)
        self.touched(0)

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
    def add_note(self, text):
        """A note for this pet's notebook: remembered, learned from (name, pronouns), and answered right away."""
        text = text.strip()[:240]
        if not text: return
        self.st["notes"].append({"when": datetime.now().isoformat(timespec="minutes"), "text": text})
        del self.st["notes"][:-300]
        save_state(self.st)
        before = load_owner().name; learn_owner(self.st["notes"]); after = load_owner().name
        self.say(f"{after}. Got it." if after and after != before else N.reaction(text)); self.touched(5)
        self.next_recall = min(self.next_recall, time.time() + random.uniform(3 * 60, 8 * 60))

    def notebook_dialog(self):
        win = tk.Toplevel(self.root); win.title("Notebook"); win.attributes("-topmost", True); window_icon(win); win.configure(bg=CREAM)
        win.geometry(f"+{max(self.area[0], int(self.x) - 160)}+{max(self.area[1], int(self.y) - 480)}")
        tk.Label(win, text=f"Tell {self.st['name']} something", bg=CREAM, fg="#23213B", font=("Segoe UI", 12, "bold")).pack(padx=16, pady=(12, 2), anchor="w")
        tk.Label(win, text="Type anything: who you are, who's in your life, what you like, how today went. It remembers and brings it up later. All of it stays on this computer.",
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
            self.add_note(text); box.delete("1.0", "end"); note.configure(text=""); redraw()
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
        who = load_owner().name
        self.root.after(700, lambda: self.say(((f"{who}, you asked me to remind you: " if who else "You asked me to remind you: ") if late else "Reminder: ") + text, ms=None))

    # --- the loop
    def tick(self):
        now = time.time()
        # attention drifts down while the pet is ignored; below 30 it sulks
        if now - self.last_attention_tick > 60:
            self.last_attention_tick = now
            self.st["attention"] = max(0, self.st["attention"] - (2 if "clingy" in self.st["picks"] else 1))
            if self.good_days() >= E.GOOD_DAYS_FOR_EGG and self.state in ("idle", "walk", "sit"):
                self.find_egg()
            if self.ignored() and self.state in ("idle", "walk", "sit"):
                self.mood = "sulky"; self.state = "sulk"; self.until = now + 40
                self.say(self.line("sulk", "Hmph.", "...", "You forgot me."))
            elif self.st["notes"] and now > self.next_recall and self.state in ("idle", "walk", "sit") and not self.lonely():
                self.next_recall = now + random.uniform(15 * 60, 35 * 60)
                self.bring_up_a_note()
            elif self.lonely() and now > self.next_nudge and self.state in ("idle", "walk", "sit"):
                self.next_nudge = now + random.uniform(300, 420)
                self.mood = "happy"; self.queue_routine(self._bounce_steps(3))
                self.root.after(500, lambda: self.say(load_owner().call(self.line("nudge", "Play with me?", "Psst.", "I'm bored."))))
            save_state(self.st)

        if self.anim_t % 5 == 0 and not self.selftest:
            self.mind_others()
        if int(now) % 10 == 0 and int(now) != getattr(self, "_rem_checked", 0):
            self._rem_checked = int(now); self.deliver_reminders()
            if pet_state(self.pid).get("home", False) and not self.selftest:   # sent home from another pet's menu
                self.st["home"] = True; self.remember_place(); self.unsay(); self.root.destroy(); return

        self.reactions(now)
        self.mischief_tick()
        self.trail_tick()
        if self.anim_t % 10 == 0: self.egg_tick(now)
        if self.state in ("idle", "walk", "sit") and self.flag("reacts") and self.anim_t % 20 == 0:
            if F.screen_locked() and not self.locked_sleep:
                self.locked_sleep = True; self.mood = "sleepy"; self.state = "sleep"; self.until = now + 10 ** 9
            elif self.locked_sleep and not F.screen_locked():
                self.locked_sleep = False; self.state = "idle"; self.mood = "happy"; self.until = now + 1
                self.queue_routine([("happy", "stretch", 0, 0, 0, 500), ("happy", "idle", 0, 0, 0, 100)]); self.root.after(300, lambda: self.say(load_owner().call(self.line("welcome", "Welcome back."))))
        elif self.state == "sleep" and self.locked_sleep and self.anim_t % 20 == 0 and not F.screen_locked():
            self.locked_sleep = False; self.state = "idle"; self.mood = "happy"; self.until = now + 1
            self.queue_routine([("happy", "stretch", 0, 0, 0, 500), ("happy", "idle", 0, 0, 0, 100)]); self.root.after(300, lambda: self.say(load_owner().call(self.line("welcome", "Welcome back."))))
        if self.party_until and now > self.party_until:
            self.party_until = 0
            if self.st["wearing"].get("hat") == "party":
                self.st["wearing"]["hat"] = self.party_hat_before; save_state(self.st)
        if self.anim_t % 200 == 0:                                          # someone else's party: join in
            try:
                pj = H.base_dir() / "party.json"
                if pj.exists() and time.time() - json.loads(pj.read_text(encoding="utf-8")).get("ts", 0) < 60 and not self.party_until:
                    self.party_until = time.time() + 180
                    if owns("party") and self.st["wearing"].get("hat") != "party":
                        self.party_hat_before = self.st["wearing"].get("hat"); self.st["wearing"]["hat"] = "party"
                    self.confetti()
            except (OSError, ValueError):
                pass

        if self.state == "held":
            pass
        elif self.state == "steal":                                          # the cursor is mine for a moment
            ctypes.windll.user32.SetCursorPos(int(self.x + self.size // 2), int(self.y + self.size // 2))
            self.show("surprised", "squash" if (self.anim_t // 4) % 2 == 0 else "idle", 0); self.anim_t += 1
            if now > self.steal_until:
                self.state = "idle"; self.until = now + 1; self.touched(0)
        elif self.state == "sign":
            self.anim_t += 1
            if now > self.sign_until:
                self.sign = None; self.state = "idle"; self.until = now + 1
            else:
                self.label.configure(image=self.frames.get_sign(self.sign, self.st["wearing"], blink=(self.anim_t // 60) % 8 == 7))
        elif self.state == "dance":
            self.anim_t += 1
            music_on = (self.flag("music") and self.ear.music and dance_slot(now)) or now < self.dance_force_until
            if not music_on:                                        # the music stopped, or it's the household's shared breather
                self.state = "idle"; self.until = now + 1
            else:
                t = now % 16.0                                     # by the wall clock: every pet on the desktop dances in step
                bar = int(t / 2); b = t % 2.0                       # eight moves, two seconds each
                beat = int(b / 0.25) % 8; fast = int(b / 0.125) % 2
                fl = self.floor; hop = round(10 * SCALE)
                if bar == 0:                                        # arms up, bouncing: wave1/wave2 with a hop on the beat
                    self.y = fl - (hop if beat % 2 == 0 else 0); self.show("happy", "wave1" if fast else "wave2", 0)
                elif bar == 1:                                      # moonwalk slide, facing the wrong way
                    away = 1 if int(now / 16) % 2 == 0 else -1
                    self.x = max(self.area[0], min(self.area[2] - self.size, self.x + 3 * away)); self.y = fl
                    self.show("happy", "walk1" if fast else "walk2", 300 if away > 0 else 60)
                elif bar == 2:                                      # the shimmy: quick turns with a shuffle
                    self.x = max(self.area[0], min(self.area[2] - self.size, self.x + (4 if fast else -4))); self.y = fl
                    self.show("happy", "squash" if beat % 2 == 0 else "stretch", 60 if fast else 300)
                elif bar == 3:                                      # the jump spin: up, all the way round, land in a squash
                    ph = b / 2.0
                    self.y = fl - round(28 * SCALE * (1 - (2 * ph - 1) ** 2))
                    self.show("surprised" if ph > 0.92 else "happy", "squash" if ph > 0.92 else "idle", 0 if ph > 0.92 else (0, 60, 120, 180, 240, 300)[int(ph * 12) % 6])
                elif bar == 4:                                      # the worm: flat, up, flat, sliding along
                    self.x = max(self.area[0], min(self.area[2] - self.size, self.x + 2)); self.y = fl
                    self.show("happy", ("lie", "squash", "stretch", "squash")[beat % 4], 0)
                elif bar == 5:                                      # dab, flex, dab, flex
                    self.y = fl; self.show("happy", "dab" if beat % 2 == 0 else "flex", 0)
                elif bar == 6:                                      # drop it low: a deep squash, then up into a stretch, sit for the beat
                    self.y = fl; self.show("happy", ("squash", "squash", "stretch", "sit")[beat % 4], 0 if beat < 4 else 300)
                else:                                               # big finish: hop turns and a wave at the crowd
                    self.y = fl - (hop if fast else 0)
                    self.show("happy", "wave2" if beat >= 6 else "idle", (0, 60, 0, 300)[beat % 4] if beat < 6 else 0)
                self.place()
        elif self.state == "inside":
            if now > self.inside_until or (self.anim_t % 20 == 0 and self.called_out()) or self.house_here() is None:
                self.come_out()
            self.anim_t += 1
        elif self.state == "routine":
            self._run_routine()
        elif self.state == "hide":                                 # until Come out on the menu
            self.anim_t += 1
            peek = (self.anim_t // 20) % 40 in (37, 38)            # a quick look over the edge now and then
            self.label.configure(image=self.frames.get_folder(self.st["wearing"], peek))
        elif self.state == "break":
            self.anim_t += 1
            if now > self.until:
                self.state = "idle"; self.until = now + 2; self.mood = "happy"
                self.next_break = now + random.uniform(25 * 60, 60 * 60)
                self.queue_routine([("happy", "stretch", 0, 0, 0, 500), ("happy", "idle", 0, 0, 0, 100)])
                self.say(self.line("shower", "Fresh.") if self.break_kind == "shower" else self.line("bath", "Don't ask."))
            else:
                self.label.configure(image=self.frames.get_curtain(self.break_kind, self.anim_t // 6))
        elif self.state == "chase":                     # after the cursor, for a few seconds
            self.anim_t += 1
            px = self.root.winfo_pointerx() - self.size // 2
            if now > self.chase_until or abs(px - self.x) < 6:
                if abs(px - self.x) < 6: self.say("Got you.", ms=1200)
                self.state = "idle"; self.until = now + 1
            else:
                step = 5 if px > self.x else -5
                self.x = max(self.area[0], min(self.area[2] - self.size, self.x + step)); self.y = self.floor; self.place()
                self.show("happy", "walk1" if (self.anim_t // 3) % 2 == 0 else "walk2", 60 if step > 0 else 300)
        elif self.state == "together":                  # ends only when the owner clicks the pet
            self.anim_t += 1
            self.show(*self._together_frame())
        else:
            if ((self.flag("music") and self.ear.music and dance_slot(now) and now > self.dance_rest_until) or now < self.dance_force_until) and self.state in ("idle", "walk", "sit") and self.mood != "sulky":
                self.state = "dance"; self.anim_t = 0; self.mood = "happy"; self.dance_t0 = now
            elif now > self.until:
                if now > self.next_break and self.state in ("idle", "walk", "sit") and self.mood != "sulky":
                    self.take_break()
                elif self.st.get("chaos", "cheeky") != "sweet" and now > self.next_mischief and self.playable():
                    self.do_mischief()
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
            if self._selftest_ticks > 70:
                print(f"selftest ok: window up, frames drawn, loop running; ear {'ok' if self.ear.ok else 'off'}"); self.root.destroy(); return
        self.root.after(TICK_MS, self.tick)

    def _run_routine(self):
        if not self.routine:
            self.bit = None
            self.state = "idle"; self.until = time.time() + 1.5; self.y = min(self.y, self.floor); self.place()
            if self.after_routine:
                fn, self.after_routine = self.after_routine, None; fn()
            return
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
            tricks = [t["id"] for t in self.sp["catalog"]["tricks"] if t["id"] in picks and t["id"] != "nap"]
            sig = self.sp.get("signature")
            if sig in tricks: tricks += [sig, sig]                        # its own bit, three times as often
            if tricks: self.do_trick(random.choice(tricks), by_owner=False); return
            pick = "idle"
        self.state = pick if pick != "trick" else "idle"
        if pick == "walk":
            self.facing = random.choice((1, -1)); self.vx = self.facing * random.uniform(1.2, 2.2)
            self.until = time.time() + (random.uniform(8, 18) if random.random() < 0.3 else random.uniform(2, 6))   # sometimes a real stroll
        elif pick == "sleep":
            if self.house_here() and time.time() > self.next_house_nap and random.random() < 0.6 and self.go_inside("bedroom", random.uniform(90, 200)):
                self.next_house_nap = time.time() + random.uniform(20 * 60, 45 * 60)     # the next bedroom nap is a while off; naps in between happen on the taskbar
                return
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
    """The household window: enter a code, see which pets are yours, name one and adopt it. Returns the pet id or None."""
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
        grey = bg.convert("LA").convert("RGBA"); stills[pid + ":locked"] = ImageTk.PhotoImage(Image.blend(bg, grey, 0.75).resize((px, px), Image.LANCZOS))

    tk.Label(root, text="Your Perchlings household", bg=CREAM, fg="#23213B", font=("Segoe UI", 14, "bold")).pack(padx=24, pady=(18, 2), anchor="w")
    tk.Label(root, text="Every adoption comes with a code. Type it here and that pet is yours. You can add more any time.", bg=CREAM, fg="#6B6685",
             font=("Segoe UI", 9), wraplength=round(560 * SCALE), justify="left").pack(padx=24, pady=(0, 8), anchor="w")
    crow = tk.Frame(root, bg=CREAM); crow.pack(padx=24, anchor="w")
    tk.Label(crow, text="Code", bg=CREAM, fg="#5A3FC0", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 8))
    code_in = tk.Entry(crow, font=("Segoe UI", 11), width=30); code_in.pack(side="left")
    note = tk.Label(root, text="", bg=CREAM, fg="#B4453A", font=("Segoe UI", 9), wraplength=round(560 * SCALE), justify="left")

    row = tk.Frame(root, bg=CREAM); row.pack(padx=20, pady=(10, 0))
    picked = tk.StringVar(value="")
    cards = {}; card_img = {}; card_sub = {}
    for pid in ids:
        card = tk.Frame(row, bg="#FFFFFF", highlightthickness=2, highlightbackground="#E8DFF3", cursor="hand2")
        card.pack(side="left", padx=4)
        card_img[pid] = tk.Label(card, image=stills[pid], bg="#FFFFFF", bd=0); card_img[pid].pack(padx=6, pady=(6, 0))
        sp_ = species[pid]
        tk.Label(card, text=f"{sp_.get('name', sp_['label'])}, {sp_.get('archetype', '').lower()}" if sp_.get("archetype") else sp_["label"],
                 bg="#FFFFFF", fg="#23213B", font=("Segoe UI", 10, "bold")).pack(pady=(0, 2))
        tk.Label(card, text=sp_.get("bio", ""), bg="#FFFFFF", fg="#6B6685", font=("Segoe UI", 8), wraplength=round(150 * SCALE), justify="center").pack(padx=6)
        card_sub[pid] = tk.Label(card, text="", bg="#FFFFFF", fg="#5A3FC0", font=("Segoe UI", 8, "bold")); card_sub[pid].pack(padx=6, pady=(2, 6))
        cards[pid] = card
        for w in (card, *card.winfo_children()):
            w.bind("<Button-1>", lambda e, pid=pid: choose(pid))

    form = tk.Frame(root, bg=CREAM); form.pack(padx=24, pady=(12, 0), fill="x")
    tk.Label(form, text="Its name", bg=CREAM, fg="#5A3FC0", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w")
    name = tk.Entry(form, font=("Segoe UI", 11), width=26); name.grid(row=1, column=0, sticky="w", pady=(2, 0))
    tk.Label(form, text="Five free picks come with each pet. Choose them later: right-click your pet, then Picks.", bg=CREAM, fg="#6B6685", font=("Segoe UI", 9)).grid(row=1, column=1, sticky="w", padx=(24, 0))
    note.pack(padx=24, pady=(8, 0), anchor="w")

    def status(pid):
        if pid in adopted_ids(): return "lives here"
        if owns(f"pet:{pid}"): return "yours, not adopted yet"
        return f"{SHOP['items'].get(f'pet:{pid}', {}).get('price', '$5.99')} on the site"

    def refresh():
        for pid in ids:
            st_ = status(pid); card_sub[pid].configure(text=st_)
            card_img[pid].configure(image=stills[pid] if owns(f"pet:{pid}") or pid in adopted_ids() else stills[pid + ":locked"])
            cards[pid].configure(highlightbackground="#5A3FC0" if picked.get() == pid else "#E8DFF3")
        if not picked.get():
            free = [pid for pid in ids if owns(f"pet:{pid}") and pid not in adopted_ids()]
            if free: choose(free[0])

    def choose(pid):
        if pid in adopted_ids():
            note.configure(text=f"{species[pid].get('name', species[pid]['label'])} already lives here."); return
        if not owns(f"pet:{pid}"):
            note.configure(text=f"{species[pid].get('name', species[pid]['label'])} isn't yours yet. Adopt it on the site, then type the code above.")
            picked.set(""); refresh(); return
        picked.set(pid); note.configure(text="")
        if not name.get().strip() or name.get().strip() in (s_.get("name", s_["label"]) for s_ in species.values()):
            name.delete(0, "end"); name.insert(0, species[pid].get("name", species[pid]["label"]))
        refresh()

    def unlock(*_):
        okk, msg = redeem_code(code_in.get())
        note.configure(text=msg, fg="#176B4E" if okk else "#B4453A")
        if okk: code_in.delete(0, "end"); refresh()
        return "break"
    code_in.bind("<Return>", unlock)
    tk.Button(crow, text="Use the code", command=unlock, padx=12, bg="#5A3FC0", fg="#FFFFFF", activebackground="#4A32A6", activeforeground="#FFFFFF",
              relief="flat", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(8, 0))
    tk.Button(crow, text="Get a pet on the site", command=lambda: webbrowser.open(SHOP.get("store_url", "https://pinkpelara.github.io/perchling/#price")), padx=10).pack(side="left", padx=(8, 0))

    def adopt():
        pid = picked.get()
        if not pid:
            note.configure(text="Pick a pet that's yours, or type a code."); return
        if pid in adopted_ids() or not owns(f"pet:{pid}"):
            choose(pid); return
        st = load_state(species[pid])
        st["name"] = (name.get().strip() or species[pid].get("name", species[pid]["label"]))[:24]
        st["picks"] = [species[pid].get("signature")] if species[pid].get("signature") else []
        save_state(st)
        chosen["pet"] = pid
        root.destroy()
    brow = tk.Frame(root, bg=CREAM); brow.pack(pady=(10, 20))
    tk.Button(brow, text="Adopt", command=adopt, bg="#5A3FC0", fg="#FFFFFF", activebackground="#4A32A6", activeforeground="#FFFFFF",
              font=("Segoe UI", 11, "bold"), relief="flat", padx=26, pady=6, cursor="hand2").pack(side="left")
    tk.Button(brow, text="Not now", command=root.destroy, padx=12).pack(side="left", padx=(10, 0))
    refresh()
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
    ap.add_argument("--house", action="store_true", help="run the house instead of a pet")
    ap.add_argument("--stage", action="store_true", help="run the streamer stage")
    a = ap.parse_args()
    if a.house:
        import house
        house.main(selftest=a.selftest); return
    if a.stage:
        S.main(selftest=a.selftest); return
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
            out = [pid for pid in out if not instance_running(pid)] or out[:1]
            pet_id, others = out[0], out[1:]
            for other in others:
                subprocess.Popen(launch_command(other), shell=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if not instance_running("house") and adopted:
                subprocess.Popen(house_command(), shell=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            pet_id = adoption_window()
            if pet_id is None:
                return
    set_home(pet_id, False)
    if not claim_instance(pet_id):
        return
    pet = Pet(load_species(pet_id), selftest=a.selftest, pet_id=pet_id)
    pet.root.mainloop()


if __name__ == "__main__":
    main()
