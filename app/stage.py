"""The stage: a window streamers can capture. Green background, every pet that's out, the house, their
speech bubbles, and a row of buttons to make things happen on stream.

Its own program (Perchlings.exe --stage). It draws copies of the pets from what they announce
(household/here/<pet>.json); the pets themselves stay on the desktop. Buttons write small command files
(household/commands/<pet>.json) that the pets pick up within a quarter of a second. Nothing goes online.
"""
import json, os, time
import tkinter as tk
from pathlib import Path
from PIL import Image, ImageDraw, ImageTk

import perchling as P
import household as H
import fun as F

BACKDROPS = {"Green screen": "#00FF00", "Blue screen": "#0000FF", "Magenta": "#FF00FF", "Cream": "#FFF8F0", "Night": "#120820"}


def command(pid, cmd, **kw):
    d = H.base_dir() / "commands"; d.mkdir(parents=True, exist_ok=True)
    try:
        (d / f"{pid}.json").write_text(json.dumps(dict(kw, cmd=cmd, ts=time.time())), encoding="utf-8")
    except OSError:
        pass


def take_command(pid):
    f = H.base_dir() / "commands" / f"{pid}.json"
    if not f.exists():
        return None
    try:
        d = json.loads(f.read_text(encoding="utf-8")); f.unlink()
    except (OSError, ValueError):
        return None
    return d if time.time() - d.get("ts", 0) < 10 else None


class Stage:
    def __init__(self, selftest=False):
        self.selftest = selftest
        self.root = tk.Tk(); self.root.title("Perchlings Stage"); self.root.configure(bg="#23213B")
        P.window_icon(self.root)
        w, h = round(1100 * P.SCALE), round(380 * P.SCALE)
        self.root.geometry(f"{w}x{h}")
        self.backdrop = tk.StringVar(value="Green screen")
        bar = tk.Frame(self.root, bg="#23213B"); bar.pack(side="bottom", fill="x")
        for label, cmd in (("Tickle everyone", "tickle"), ("Wave", "wave"), ("Dance", "dance"), ("Gossip", "gossip"), ("Party", "party"), ("Everyone out", "out")):
            tk.Button(bar, text=label, command=lambda c=cmd: self.send_all(c), bg="#5A3FC0", fg="#FFFFFF", activebackground="#4A32A6", activeforeground="#FFFFFF",
                      relief="flat", font=("Segoe UI", 9, "bold"), padx=10, pady=3, cursor="hand2").pack(side="left", padx=4, pady=6)
        tk.Label(bar, text="Backdrop", bg="#23213B", fg="#B9AECF", font=("Segoe UI", 9)).pack(side="left", padx=(16, 4))
        tk.OptionMenu(bar, self.backdrop, *BACKDROPS.keys()).pack(side="left")
        tk.Label(bar, text="In OBS: Window Capture this window, add a Chroma Key filter.", bg="#23213B", fg="#B9AECF", font=("Segoe UI", 9)).pack(side="right", padx=10)
        self.canvas = tk.Label(self.root, bd=0, highlightthickness=0); self.canvas.pack(fill="both", expand=True)
        self.frames = {}; self.cache = {}
        self.img = None
        self.root.after(100, self.tick)

    def send_all(self, cmd):
        pets = H.others("__stage__", None)
        if cmd in ("gossip", "party"):               # one pet starts it; the others join through the household
            pets = pets[:1]
        for o in pets:
            command(o["pid"], cmd)

    def pet_image(self, pid, mood, pose, yaw, wearing, px):
        key = (pid, mood, pose, yaw, json.dumps(wearing, sort_keys=True), px)
        if key not in self.cache:
            if pid not in self.frames:
                self.frames[pid] = P.Frames(pid, 128)
            self.cache[key] = self.frames[pid].compose(mood, pose, yaw, wearing).resize((px, px), Image.LANCZOS)
            if len(self.cache) > 400: self.cache.clear()
        return self.cache[key]

    def draw(self):
        W = max(200, self.canvas.winfo_width()); Hh = max(120, self.canvas.winfo_height())
        bg = BACKDROPS[self.backdrop.get()]
        im = Image.new("RGBA", (W, Hh), bg); d = ImageDraw.Draw(im)
        pets = [o for o in H.others("__stage__", None) if not o.get("inside")]
        house = None
        try:
            hj = H.base_dir() / "house.json"
            if hj.exists():
                house = json.loads(hj.read_text(encoding="utf-8"))
                if time.time() - house.get("ts", 0) > 8: house = None
        except (OSError, ValueError):
            house = None
        area = None
        for o in pets:
            area = o.get("area"); break
        if area is None and house: area = house.get("area")
        if area is None: area = list(P.work_area())
        span = max(1, area[2] - area[0])
        px = round(Hh * 0.6); floor = Hh - round(Hh * 0.04)
        if house:
            hs = round(Hh * 0.85)
            him = Image.open(P.ROOT / "assets" / "house" / "closed.png").convert("RGBA").resize((hs, hs), Image.LANCZOS)
            hx = round((house["x"] + house["size"] / 2 - area[0]) / span * W - hs / 2)
            im.alpha_composite(him, (hx, floor - round(hs * 0.88)))
        f = F.font(round(15 * P.SCALE), bold=True)
        for o in sorted(pets, key=lambda o: o.get("x", 0)):
            x = round((o["x"] + o["size"] / 2 - area[0]) / span * W - px / 2)
            pet = self.pet_image(o["pid"], o.get("mood", "happy"), o.get("pose", "idle"), o.get("yaw", 0), o.get("wearing", {}), px)
            im.alpha_composite(pet, (x, floor - round(px * 0.87)))
            say = o.get("say")
            if say and time.time() < say.get("until", 0):
                text = say["text"]; tw = f.getlength(text) + 20; th = round(26 * P.SCALE)
                bx = max(4, min(W - tw - 4, x + px / 2 - tw / 2)); by = floor - round(px * 0.87) - th - 6
                d.rounded_rectangle((bx, by, bx + tw, by + th), radius=8, fill=(255, 248, 240, 255), outline=(216, 207, 232, 255), width=2)
                d.text((bx + 10, by + 4), text, font=f, fill=(35, 33, 59, 255))
        self.img = ImageTk.PhotoImage(im); self.canvas.configure(image=self.img)

    def tick(self):
        self.draw()
        if self.selftest:
            print("stage selftest ok"); self.root.destroy(); return
        self.root.after(100, self.tick)


def main(selftest=False):
    if not P.claim_instance("stage"):
        return
    Stage(selftest=selftest).root.mainloop()
