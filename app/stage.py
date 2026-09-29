"""The stage: a window streamers can capture. Green background, every pet that's out, the house, their
speech bubbles, and a row of buttons to make things happen on stream.

Its own program (Perchlings.exe --stage). It draws copies of the pets from what they announce
(household/here/<pet>.json); the pets themselves stay on the desktop. Buttons write small command files
(household/commands/<pet>.json) that the pets pick up within a quarter of a second. Nothing goes online.
"""
import json, os, sys, time
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
        self.root.report_callback_exception = lambda *exc: P.log_error("stage", exc)
        P.window_icon(self.root)
        w, h = round(1100 * P.SCALE), round(380 * P.SCALE)
        self.root.geometry(f"{w}x{h}")
        self.backdrop = tk.StringVar(value="Green screen")
        bar = tk.Frame(self.root, bg="#23213B"); bar.pack(side="bottom", fill="x")
        self.play_btns = []
        for label, cmd in (("Tickle everyone", "tickle"), ("Wave", "wave"), ("Dance", "dance"), ("Gossip", "gossip"), ("Party", "party"), ("Everyone out", "out")):
            b = tk.Button(bar, text=label, command=lambda c=cmd: self.send_all(c), bg="#5A3FC0", fg="#FFFFFF", activebackground="#4A32A6", activeforeground="#FFFFFF",
                          disabledforeground="#8F86A8", relief="flat", font=("Segoe UI", 9, "bold"), padx=10, pady=3, cursor="hand2"); b.pack(side="left", padx=4, pady=6)
            if cmd != "out": self.play_btns.append(b)
        # quiet time: everyone into the house, the house folds up into a folder, until Let them out (or Everyone out)
        self.quiet_btn = tk.Button(bar, text="Quiet time", command=self.toggle_quiet, bg="#C0473F", fg="#FFFFFF", activebackground="#A33A33", activeforeground="#FFFFFF",
                                   relief="flat", font=("Segoe UI", 9, "bold"), padx=10, pady=3, cursor="hand2"); self.quiet_btn.pack(side="left", padx=(12, 4), pady=6)
        self.clip_btn = tk.Button(bar, text="Clip 8 s", command=self.take_clip, bg="#2FB3A3", fg="#FFFFFF", activebackground="#238C80", activeforeground="#FFFFFF",
                                  relief="flat", font=("Segoe UI", 9, "bold"), padx=10, pady=3, cursor="hand2"); self.clip_btn.pack(side="left", padx=(12, 4), pady=6)
        tk.Label(bar, text="Backdrop", bg="#23213B", fg="#B9AECF", font=("Segoe UI", 9)).pack(side="left", padx=(16, 4))
        tk.OptionMenu(bar, self.backdrop, *BACKDROPS.keys()).pack(side="left")
        tk.Label(bar, text="In OBS: Window Capture this window, add a Chroma Key filter.", bg="#23213B", fg="#B9AECF", font=("Segoe UI", 9)).pack(side="right", padx=10)
        # a second row: tell the whole household something, into every notebook at once
        row = tk.Frame(self.root, bg="#23213B"); row.pack(side="bottom", fill="x")
        tk.Label(row, text="Tell everyone", bg="#23213B", fg="#B9AECF", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(10, 6), pady=(0, 6))
        self.note_in = tk.Entry(row, font=("Segoe UI", 10), width=60); self.note_in.pack(side="left", pady=(0, 6))
        self.note_in.bind("<Return>", lambda e: self.tell_everyone())
        tk.Button(row, text="Tell them", command=self.tell_everyone, bg="#5A3FC0", fg="#FFFFFF", activebackground="#4A32A6", activeforeground="#FFFFFF",
                  relief="flat", font=("Segoe UI", 9, "bold"), padx=10, pady=2, cursor="hand2").pack(side="left", padx=6, pady=(0, 6))
        self.note_status = tk.Label(row, text="Goes into every pet's notebook, the ones at home too. They answer on screen.", bg="#23213B", fg="#B9AECF", font=("Segoe UI", 9))
        self.note_status.pack(side="left", padx=6, pady=(0, 6))
        self.canvas = tk.Label(self.root, bd=0, highlightthickness=0); self.canvas.pack(fill="both", expand=True)
        self.frames = {}; self.cache = {}
        self.house_imgs = {}; self.style = ("cozy", 0.0); self.say_font = F.font(round(15 * P.SCALE), bold=True)   # made once, not ten times a second
        self.img = None
        self.root.after(100, self.tick)

    def take_clip(self):
        """Eight seconds of the stage itself (backdrop and all) as a GIF in Pictures."""
        if getattr(self, "clipping", False): return
        self.clipping = True; self.clip_btn.configure(text="Recording...", state="disabled")
        c = self.canvas
        box = (c.winfo_rootx(), c.winfo_rooty(), c.winfo_rootx() + c.winfo_width(), c.winfo_rooty() + c.winfo_height())   # read here, on
        where = lambda: box                                                                                              # Tk's thread
        def done(path):
            self.clipping = False
            self.root.after(0, lambda: self.clip_btn.configure(text="Clip 8 s", state="normal"))
            if path:
                try: os.startfile(path.parent)
                except OSError: pass
        F.record_clip(where, seconds=8, fps=12, max_w=720, name="Stage", done=done)

    def tell_everyone(self):
        """One note into every pet's notebook. Pets that are out get it by command and answer; pets at home get it written in."""
        text = self.note_in.get().strip()[:240]
        if not text:
            return
        out = {o["pid"] for o in H.others("__stage__", None)} | {pid for pid in P.adopted_ids() if P.instance_running(pid)}   # a running pet writes its own file
        n = 0
        for pid in P.adopted_ids():
            if pid in out:
                command(pid, "note", text=text)
            else:
                st = P.pet_state(pid)
                if not st: continue
                st.setdefault("notes", []).append({"when": time.strftime("%Y-%m-%dT%H:%M"), "text": text}); del st["notes"][:-300]
                try: P.write_json_safely(P.state_path(pid), st)
                except OSError: P.log_error("tell_everyone"); continue
            n += 1
        self.note_in.delete(0, "end")
        self.note_status.configure(text=f"Told {n} pet{'s' if n != 1 else ''}. They'll bring it up later, and gossip about it.")

    def quiet_on(self):
        q = H.quiet()
        return bool(q and q.get("on"))

    def toggle_quiet(self):
        H.set_quiet(not self.quiet_on()); self.show_quiet()

    def show_quiet(self):
        on = self.quiet_on()
        want = "Let them out" if on else "Quiet time"
        if self.quiet_btn.cget("text") != want:
            self.quiet_btn.configure(text=want, bg="#2FB3A3" if on else "#C0473F", activebackground="#238C80" if on else "#A33A33")
            for b in self.play_btns:                                       # the others rest while everyone is in
                b.configure(state="disabled" if on else "normal", cursor="arrow" if on else "hand2")
            self.note_status.configure(text="Quiet time: the buttons wait until you let them out. A note still goes into every notebook." if on else
                                       "Goes into every pet's notebook, the ones at home too. They answer on screen.")

    def send_all(self, cmd):
        if cmd == "out" and self.quiet_on():         # Everyone out ends quiet time: the pets come out by themselves, with a word
            H.set_quiet(False); self.show_quiet(); return
        pets = H.others("__stage__", None)
        if cmd in ("gossip", "party"):               # one pet starts it; the others join through the household
            pets = pets[:1]
        for o in pets:
            command(o["pid"], cmd)

    def pet_image(self, pid, mood, pose, yaw, wearing, px, species=None, variant=None):
        key = (pid, mood, pose, yaw, json.dumps(wearing, sort_keys=True), px)
        if key not in self.cache:
            if pid not in self.frames:
                self.frames[pid] = P.Frames(species or pid, 128, variant=variant)
            self.cache[key] = self.frames[pid].compose(mood, pose, yaw, wearing).resize((px, px), Image.LANCZOS)
            if len(self.cache) > 400: self.cache.clear()
        return self.cache[key]

    def draw(self):
        W = max(200, self.canvas.winfo_width()); Hh = max(120, self.canvas.winfo_height())
        bg = BACKDROPS[self.backdrop.get()]
        im = Image.new("RGBA", (W, Hh), bg); d = ImageDraw.Draw(im)
        pets = [o for o in H.others("__stage__", None) if not o.get("inside") and not o.get("tucked") and o.get("state") != "break"]   # behind the curtain: nobody sees a thing, on stream either
        house = None
        try:
            hj = H.base_dir() / "house.json"
            if hj.exists():
                house = json.loads(hj.read_text(encoding="utf-8"))
                if time.time() - house.get("ts", 0) > 20: house = None
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
            if time.time() - self.style[1] > 1:                            # the style is read once a second, the picture made once per size
                self.style = (P.read_json_safely(P.state_path("antenna").parent / "house.json").get("style", "cozy"), time.time())
            style = self.style[0]
            if (style, hs) not in self.house_imgs:
                self.house_imgs = {(style, hs): Image.open(P.ROOT / "assets" / "house" / ("closed.png" if style == "cozy" else f"closed-{style}.png")).convert("RGBA").resize((hs, hs), Image.LANCZOS)}
            him = self.house_imgs[(style, hs)]
            if house.get("folded"):                                        # quiet time: the house is a folder, on the stage too
                if ("folder", hs) not in self.house_imgs:
                    self.house_imgs[("folder", hs)] = F.folder_art().resize((hs, hs), Image.LANCZOS)
                him = self.house_imgs[("folder", hs)]
            ha = house.get("area") or area; hspan = max(1, ha[2] - ha[0])            # each screen maps onto the whole stage
            hx = round((house["x"] + house["size"] / 2 - ha[0]) / hspan * W - hs / 2)
            im.alpha_composite(him, (hx, floor - round(hs * 0.88)))
        f = self.say_font
        for o in sorted(pets, key=lambda o: o.get("x", 0)):
            oa = o.get("area") or area; ospan = max(1, oa[2] - oa[0])                # a pet on another monitor lands on the stage too
            x = round((o["x"] + o["size"] / 2 - oa[0]) / ospan * W - px / 2)
            if o.get("state") == "hide":                                            # a folder on the desktop, a folder here
                if ("folder", px) not in self.cache:
                    self.cache[("folder", px)] = F.folder_art().resize((px, px), Image.LANCZOS)
                pet = self.cache[("folder", px)]
            else:
                pet = self.pet_image(o["pid"], o.get("mood", "happy"), o.get("pose", "idle"), o.get("yaw", 0), o.get("wearing", {}), px, o.get("species"), o.get("variant"))
            im.alpha_composite(pet, (x, floor - round(px * 0.87)))
            say = o.get("say")
            if say and time.time() < say.get("until", 0):
                text = say["text"]; tw = f.getlength(text) + 20; th = round(26 * P.SCALE)
                bx = max(4, min(W - tw - 4, x + px / 2 - tw / 2)); by = floor - round(px * 0.87) - th - 6
                d.rounded_rectangle((bx, by, bx + tw, by + th), radius=8, fill=(255, 248, 240, 255), outline=(216, 207, 232, 255), width=2)
                d.text((bx + 10, by + 4), text, font=f, fill=(35, 33, 59, 255))
        self.img = ImageTk.PhotoImage(im); self.canvas.configure(image=self.img)

    def tick(self):
        try:
            self.draw()
            if not self.selftest: self.show_quiet()
        except Exception:                               # one bad frame is logged; the stage keeps drawing
            self.root.report_callback_exception(*sys.exc_info())
        if self.selftest:
            print("stage selftest ok"); self.root.destroy(); return
        self.root.after(100, self.tick)


def main(selftest=False):
    if not P.claim_instance("stage"):
        return
    Stage(selftest=selftest).root.mainloop()
