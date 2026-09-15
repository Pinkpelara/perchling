"""The house: a small house on the taskbar that opens into a dollhouse with four rooms.

Its own program (Perchlings.exe --house), so it stays up whatever the pets do. Pets are separate programs;
they go "inside" by hiding their window and saying which room they're in (household/here/<pet>.json), and
the house draws them in that room from their own sprite sheets. The house tells the pets where its door is
(household/house.json). Furniture and wall colours are the owner's; pieces come from assets/house.
"""
import json, os, random, time
import tkinter as tk
from pathlib import Path
from PIL import Image, ImageTk

import perchling as P
import household as H

ART = P.ROOT / "assets" / "house"
LAYOUT = json.loads((ART / "layout.json").read_text(encoding="utf-8"))
PIECES = {   # id -> (name, room, included, price)
    "bed": ("Bed", "bedroom", True, ""), "lamp": ("Lamp", "bedroom", True, ""), "poster": ("Poster", "bedroom", False, "$0.99"),
    "couch": ("Couch", "living", True, ""), "tv": ("TV", "living", False, "$1.99"), "rug": ("Rug", "living", True, ""), "plant": ("Plant", "living", False, "$0.99"),
    "table": ("Table", "kitchen", True, ""), "stove": ("Stove", "kitchen", True, ""), "fridge": ("Fridge", "kitchen", False, "$1.49"), "fishtank": ("Fish tank", "kitchen", False, "$1.99"),
    "tub": ("Bathtub", "bathroom", True, ""), "curtain": ("Shower curtain", "bathroom", True, ""), "sink": ("Sink", "bathroom", False, "$0.99"),
}
ROOM_NAMES = {"living": "Living room", "kitchen": "Kitchen", "bedroom": "Bedroom", "bathroom": "Bathroom"}
DARK = ["#4A4860", "#3B4B6E", "#8FA58A", "#B8735A"]           # charcoal, navy, sage, terracotta
WALL_CHOICES = {
    "living": ["#FFD98F", "#FFC9A8", "#F5E6C8", "#CFE3E8"] + DARK, "kitchen": ["#A9DDA0", "#FFE9A8", "#BFE3F0", "#F6D2E0"] + DARK,
    "bedroom": ["#C9B3F2", "#F6D2E0", "#BFE3F0", "#FFE9A8"] + DARK, "bathroom": ["#93CFE3", "#C9E8D8", "#E9E2F8", "#FFFFFF"] + DARK,
}
STYLES = {"cozy": "Cozy", "loft": "Loft"}
STYLE_WALLS = {"cozy": {}, "loft": {"living": "#4A4860", "kitchen": "#3B4B6E", "bedroom": "#8FA58A", "bathroom": "#B8735A"}}
CLOSED_PX = 300          # logical size of the closed house window (scaled by the screen)
OPEN_W = 760             # logical width of the open house


def house_state_path():
    return P.state_path("antenna").parent / "house.json"


def load_house():
    p = house_state_path()
    try:
        st = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except (OSError, ValueError):
        st = {}
    st.setdefault("x", None); st.setdefault("mon", None)
    st.setdefault("furniture", {k: v[2] for k, v in PIECES.items()})          # on/off per piece
    st.setdefault("walls", {})                                                 # room -> hex, else the default paint
    st.setdefault("style", "cozy")                                             # cozy or loft
    return st


def save_house(st):
    house_state_path().write_text(json.dumps(st, indent=1), encoding="utf-8")


def owns_piece(pid):
    return PIECES[pid][2] or ("house:" + pid) in P.load_owned()["items"]


def door_file():
    return H.base_dir() / "house.json"


def tell_pets(info):
    try:
        door_file().write_text(json.dumps(dict(info, ts=time.time())), encoding="utf-8")
    except OSError:
        pass


class House:
    def __init__(self, selftest=False):
        self.st = load_house()
        self.selftest = selftest
        self.root = tk.Tk()
        self.root.overrideredirect(True); self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", P.COLORKEY); self.root.configure(bg=P.COLORKEY)
        self.label = tk.Label(self.root, bg=P.COLORKEY, bd=0, highlightthickness=0); self.label.pack()
        self.size = round(CLOSED_PX * P.SCALE)
        mon = self.st.get("mon")
        left, top, right, bottom = P.monitor_work_area(*mon) if mon else P.work_area()
        self.area = (left, top, right, bottom)
        self.floor = bottom - self.size + round(8 * P.SCALE)
        self.x = self.st["x"] if self.st["x"] is not None else right - self.size - round(30 * P.SCALE)
        self.x = max(left, min(right - self.size, self.x))
        self.y = self.floor
        self.open = False
        self.drag = None
        self.frames = {}
        self.pet_frames = {}
        self.anim = 0
        self.closed_img = self._closed_image()
        self.label.configure(image=self.closed_img)
        self.label.bind("<ButtonPress-1>", self.on_press); self.label.bind("<B1-Motion>", self.on_drag); self.label.bind("<ButtonRelease-1>", self.on_release)
        self.label.bind("<Button-3>", self.on_menu)
        self.place()
        self.open_win = None
        self.tell()
        self.root.after(300, self.tick)

    # ---- art
    def _closed_image(self):
        name = "closed.png" if self.st.get("style", "cozy") == "cozy" else f"closed-{self.st['style']}.png"
        im = Image.open(ART / name).convert("RGBA").resize((self.size, self.size), Image.LANCZOS)
        return self._keyed(im)

    def _keyed(self, im):
        mask = im.getchannel("A").point(lambda a: 255 if a >= P.ALPHA_CUT else 0)
        out = Image.new("RGB", im.size, P.COLORKEY_RGB); out.paste(im.convert("RGB"), mask=mask)
        return ImageTk.PhotoImage(out)

    def open_scale(self):
        return (OPEN_W * P.SCALE) / LAYOUT["w"]

    def _open_base(self):
        """The open house with the furniture that's on, at display size. Cached until the furniture changes."""
        style = self.st.get("style", "cozy")
        key = json.dumps([sorted(k for k, v in self.st["furniture"].items() if v and owns_piece(k)), self.st["walls"], style])
        if self.frames.get("open_key") == key:
            return self.frames["open"]
        base = Image.open(ART / ("open.png" if style == "cozy" else f"open-{style}.png")).convert("RGBA")
        from PIL import ImageChops
        for room, r in LAYOUT["rooms"].items():                       # paint the walls
            colour = self.st["walls"].get(room) or STYLE_WALLS.get(style, {}).get(room) or WALL_CHOICES[room][0]
            x0, y0, x1, y1 = r["wall"]
            region = base.crop((x0, y0, x1, y1))
            tint = Image.new("RGBA", region.size, colour)
            painted = ImageChops.multiply(region.convert("RGB"), tint.convert("RGB")).convert("RGBA"); painted.putalpha(region.getchannel("A"))
            base.paste(painted, (x0, y0))
        for pid, (name, room, inc, price) in PIECES.items():
            if pid != "curtain" and self.st["furniture"].get(pid) and owns_piece(pid) and (ART / "furniture" / f"{pid}.png").exists():
                base.alpha_composite(Image.open(ART / "furniture" / f"{pid}.png").convert("RGBA"))
        curtain = Image.open(ART / "furniture" / "curtain.png").convert("RGBA") if (self.st["furniture"].get("curtain") and owns_piece("curtain")) else None
        s = self.open_scale()
        size = (round(LAYOUT["w"] * s), round(LAYOUT["h"] * s))
        self.frames["open"] = (base.resize(size, Image.LANCZOS), curtain.resize(size, Image.LANCZOS) if curtain else None)
        self.frames["open_key"] = key
        return self.frames["open"]

    def pet_image(self, pid, mood, pose, yaw, wearing, px, species=None, variant=None):
        key = (pid, mood, pose, yaw, json.dumps(wearing, sort_keys=True), px)
        if key not in self.pet_frames:
            if pid not in self.frames:
                self.frames[pid] = P.Frames(pid, 128)
            im = self.frames[pid].compose(mood, pose, yaw, wearing)
            self.pet_frames[key] = im.resize((px, px), Image.LANCZOS)
        return self.pet_frames[key]

    # ---- where things are
    def place(self):
        self.root.geometry(f"{self.size}x{self.size}+{int(self.x)}+{int(self.y)}")

    def door_screen(self):
        """Where the front door is, in screen pixels: the x of its centre and the y of the ground."""
        c = LAYOUT["closed"]; k = self.size / c["w"]
        return int(self.x + c["door"][0] * k), int(self.y + c["ground"] * k)

    def tell(self):
        dx, dy = self.door_screen()
        tell_pets({"door_x": dx, "door_y": dy, "x": int(self.x), "y": int(self.y), "size": self.size, "area": list(self.area), "open": self.open})

    def remember(self):
        self.st["x"] = int(self.x); self.st["mon"] = [int(self.x + self.size // 2), int(self.floor + self.size // 2)]
        save_house(self.st)

    # ---- input on the closed house
    def on_press(self, e):
        self.drag = (e.x_root, e.y_root, self.x, self.y, False)

    def on_drag(self, e):
        if not self.drag: return
        sx, sy, ox, oy, _ = self.drag
        dx, dy = e.x_root - sx, e.y_root - sy
        if abs(dx) + abs(dy) > 4:
            self.drag = (sx, sy, ox, oy, True)
            self.x, self.y = ox + dx, oy + dy; self.place()

    def on_release(self, e):
        if not self.drag: return
        moved = self.drag[4]; self.drag = None
        if moved:
            cx, cy = self.x + self.size // 2, self.y + self.size // 2
            left, top, right, bottom = P.monitor_work_area(cx, cy)
            self.area = (left, top, right, bottom); self.floor = bottom - self.size + round(8 * P.SCALE)
            self.x = max(left, min(right - self.size, self.x)); self.y = self.floor; self.place()
            self.remember(); self.tell()
        else:
            self.toggle_open()

    def on_menu(self, e):
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label="Close the house" if self.open else "Open the house", command=self.toggle_open)
        m.add_command(label="Decorate...", command=self.decorate_dialog)
        inside = [o for o in H.others("__house__", None) if o.get("inside")]
        if inside:
            out = tk.Menu(m, tearoff=0)
            for o in inside:
                out.add_command(label=f"{o.get('name', o['pid'])} ({ROOM_NAMES.get(o['inside'], o['inside'])})", command=lambda pid=o["pid"]: self.call_out(pid))
            out.add_separator(); out.add_command(label="Everyone", command=lambda: [self.call_out(o["pid"]) for o in inside])
            m.add_cascade(label="Come out", menu=out)
        else:
            m.add_command(label="Nobody's inside", state="disabled")
        m.add_separator()
        m.add_command(label="Quit the house", command=self.quit)
        m.tk_popup(e.x_root, e.y_root)

    def call_out(self, pid):
        try:
            (H.base_dir() / "plans" / f"house-out-{pid}.json").write_text(json.dumps({"out": True, "ts": time.time()}), encoding="utf-8")
        except OSError:
            pass

    # ---- the open house
    def toggle_open(self):
        if self.open:
            self.open = False
            if self.open_win is not None:
                self.open_win.destroy(); self.open_win = None
            self.root.deiconify(); self.place()
        else:
            self.open = True
            self.root.withdraw()
            self.open_win = tk.Toplevel(self.root)
            w = self.open_win
            w.overrideredirect(True); w.attributes("-topmost", True); w.attributes("-transparentcolor", P.COLORKEY); w.configure(bg=P.COLORKEY)
            base, _ = self._open_base()
            ow, oh = base.size
            x = max(self.area[0], min(self.area[2] - ow, int(self.x + self.size // 2 - ow // 2)))
            y = max(self.area[1], self.area[3] - oh + round(10 * P.SCALE))
            w.geometry(f"{ow}x{oh}+{x}+{y}")
            self.canvas_label = tk.Label(w, bg=P.COLORKEY, bd=0, highlightthickness=0); self.canvas_label.pack()
            self.canvas_label.bind("<Button-1>", lambda e: self.toggle_open())
            self.canvas_label.bind("<Button-3>", self.on_menu)
            self.draw_open()
        self.tell()

    def inside_pets(self):
        return [o for o in H.others("__house__", None) if o.get("inside")]

    def draw_open(self):
        if not self.open or self.open_win is None:
            return
        base, curtain = self._open_base()
        im = base.copy()
        s = self.open_scale()
        for o in self.inside_pets():
            room = o["inside"]
            r = LAYOUT["rooms"].get(room)
            if not r: continue
            ppu = r["petPx"] / 1.5                                     # render pixels per house unit at that depth
            px = round(r["petPx"] * s * 1.25)
            mood, pose, yaw, dy = self.room_pose(room, o)             # dy in house units, up is negative
            pet = self.pet_image(o["pid"], mood, pose, yaw, o.get("wearing", {}), px, o.get("species"), o.get("variant"))
            # the sprite's feet sit near the bottom of its frame; put them on the room floor
            x = round(r["spot"] * s - px / 2); y = round(r["floor"] * s - px * 0.86 + dy * ppu * s)
            im.alpha_composite(pet, (max(0, x), max(0, y)))
        if curtain is not None:
            im.alpha_composite(curtain)
        self.open_img = self._keyed(im)
        self.canvas_label.configure(image=self.open_img)

    def room_pose(self, room, o):
        t = self.anim
        if room == "bedroom":
            return ("sleepy", "squash" if (t // 4) % 2 == 0 else "idle", 0, -0.45)        # on the bed
        if room == "living":
            return ("happy", "sit", 0, -0.42)                                              # on the couch
        if room == "kitchen":
            return ("happy", "eat1" if (t // 2) % 2 == 0 else "eat2", 0, 0)
        if room == "bathroom":
            return ("happy", "idle", 0, 0)                                                 # behind the curtain
        return ("happy", "idle", 0, 0)

    # ---- decorate
    def decorate_dialog(self):
        win = tk.Toplevel(self.root); win.title("Decorate"); win.attributes("-topmost", True); P.window_icon(win); win.configure(bg=P.CREAM)
        win.geometry(f"+{max(self.area[0], int(self.x) - 300)}+{max(self.area[1], int(self.y) - 420)}")
        tk.Label(win, text="The house", bg=P.CREAM, fg="#23213B", font=("Segoe UI", 12, "bold")).pack(padx=16, pady=(12, 2), anchor="w")
        tk.Label(win, text="Tick what's out. Pieces marked with a price are in the shop.", bg=P.CREAM, fg="#6B6685", font=("Segoe UI", 9)).pack(padx=16, pady=(0, 8), anchor="w")
        srow = tk.Frame(win, bg=P.CREAM); srow.pack(padx=16, pady=(0, 6), anchor="w")
        tk.Label(srow, text="Style", bg=P.CREAM, fg="#5A3FC0", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 8))
        style_var = tk.StringVar(value=self.st.get("style", "cozy"))
        for sid, label in STYLES.items():
            tk.Radiobutton(srow, text=label, value=sid, variable=style_var, bg=P.CREAM, activebackground=P.CREAM, font=("Segoe UI", 10),
                           command=lambda: self.set_style(style_var.get())).pack(side="left", padx=(0, 10))
        cols = tk.Frame(win, bg=P.CREAM); cols.pack(padx=12, pady=(0, 10))
        vars_ = {}
        for i, room in enumerate(("bedroom", "bathroom", "living", "kitchen")):
            col = tk.Frame(cols, bg=P.CREAM); col.grid(row=i // 2, column=i % 2, sticky="nw", padx=8, pady=6)
            tk.Label(col, text=ROOM_NAMES[room], bg=P.CREAM, fg="#5A3FC0", font=("Segoe UI", 9, "bold")).pack(anchor="w")
            for pid, (name, r, inc, price) in PIECES.items():
                if r != room: continue
                if owns_piece(pid):
                    v = tk.BooleanVar(value=bool(self.st["furniture"].get(pid))); vars_[pid] = v
                    tk.Checkbutton(col, text=name, variable=v, bg=P.CREAM, activebackground=P.CREAM, anchor="w", font=("Segoe UI", 10),
                                   command=lambda pid=pid, v=v: self.set_piece(pid, v.get())).pack(anchor="w")
                else:
                    tk.Label(col, text=f"{name}, {price} in the shop", bg=P.CREAM, fg="#A29DB8", font=("Segoe UI", 9)).pack(anchor="w", padx=22)
            sw = tk.Frame(col, bg=P.CREAM); sw.pack(anchor="w", pady=(4, 0))
            tk.Label(sw, text="Walls", bg=P.CREAM, fg="#6B6685", font=("Segoe UI", 8)).pack(side="left", padx=(0, 6))
            for hexc in WALL_CHOICES[room]:
                tk.Button(sw, bg=hexc, activebackground=hexc, width=2, relief="flat", cursor="hand2",
                          command=lambda room=room, hexc=hexc: self.set_wall(room, hexc)).pack(side="left", padx=2)
        tk.Button(win, text="Close", command=win.destroy, padx=14).pack(pady=(0, 12))

    def set_style(self, style):
        self.st["style"] = style; self.st["walls"] = {}; save_house(self.st)
        self.frames.pop("open_key", None); self.closed_img = self._closed_image(); self.label.configure(image=self.closed_img); self.draw_open()

    def set_piece(self, pid, on):
        self.st["furniture"][pid] = bool(on); save_house(self.st); self.draw_open()

    def set_wall(self, room, hexc):
        self.st["walls"][room] = hexc; save_house(self.st)
        self.frames.pop("open_key", None); self.draw_open()

    # ---- loop
    def tick(self):
        self.anim += 1
        if self.open and self.anim % 2 == 0:
            self.draw_open()
        if self.anim % 20 == 0:
            self.tell()
        if self.selftest and self.anim > 10:
            print("house selftest ok"); self.root.destroy(); return
        self.root.after(300, self.tick)

    def quit(self):
        self.remember()
        try:
            door_file().unlink()
        except OSError:
            pass
        self.root.destroy()


def main(selftest=False):
    if not P.claim_instance("house"):
        return
    House(selftest=selftest).root.mainloop()
