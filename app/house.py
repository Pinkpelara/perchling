"""The house: a small house on the taskbar that opens into a dollhouse with four rooms.

Its own program (Perchlings.exe --house), so it stays up whatever the pets do. Pets are separate programs;
they go "inside" by hiding their window and saying which room they're in (household/here/<pet>.json), and
the house draws them in that room from their own sprite sheets. The house tells the pets where its door is
(household/house.json), and the pets tell the house what to do through household/commands/house.json
(open, close, decorate, style, out, move, quit), which is how the pet's panel drives it.
Furniture and wall colours are the owner's; pieces come from assets/house. Decorating is done with pictures:
every piece, every wall colour and both styles are tiles, and a preview of the house redraws on every click.
"""
import json, os, random, time, webbrowser
import tkinter as tk
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageTk

import perchling as P
import household as H
import stage as S
import menu as M

ART = P.ROOT / "assets" / "house"
LAYOUT = json.loads((ART / "layout.json").read_text(encoding="utf-8"))
PIECES = {   # id -> (name, room, included, price)
    "bed": ("Bed", "bedroom", True, ""), "lamp": ("Lamp", "bedroom", True, ""), "poster": ("Poster", "bedroom", False, "$0.99"),
    "couch": ("Couch", "living", True, ""), "tv": ("TV", "living", False, "$0.99"), "rug": ("Rug", "living", True, ""), "plant": ("Plant", "living", False, "$0.99"),
    "table": ("Table", "kitchen", True, ""), "stove": ("Stove", "kitchen", True, ""), "fridge": ("Fridge", "kitchen", False, "$0.99"), "fishtank": ("Fish tank", "kitchen", False, "$0.99"),
    "tub": ("Bathtub", "bathroom", True, ""), "curtain": ("Shower curtain", "bathroom", True, ""), "sink": ("Sink", "bathroom", False, "$0.99"),
}
ROOM_NAMES = {"living": "Living room", "kitchen": "Kitchen", "bedroom": "Bedroom", "bathroom": "Bathroom"}
ROOM_ORDER = ["bedroom", "bathroom", "living", "kitchen"]
DARK = ["#4A4860", "#3B4B6E", "#8FA58A", "#B8735A"]           # charcoal, navy, sage, terracotta
WALL_CHOICES = {
    "living": ["#FFD98F", "#FFC9A8", "#F5E6C8", "#CFE3E8"] + DARK, "kitchen": ["#A9DDA0", "#FFE9A8", "#BFE3F0", "#F6D2E0"] + DARK,
    "bedroom": ["#C9B3F2", "#F6D2E0", "#BFE3F0", "#FFE9A8"] + DARK, "bathroom": ["#93CFE3", "#C9E8D8", "#E9E2F8", "#FFFFFF"] + DARK,
}
WALL_NAMES = {"#FFD98F": "Butter", "#FFC9A8": "Peach", "#F5E6C8": "Cream", "#CFE3E8": "Mist", "#A9DDA0": "Mint", "#FFE9A8": "Lemon", "#BFE3F0": "Sky",
              "#F6D2E0": "Blush", "#C9B3F2": "Lilac", "#93CFE3": "Pool", "#C9E8D8": "Seafoam", "#E9E2F8": "Lavender", "#FFFFFF": "White",
              "#4A4860": "Charcoal", "#3B4B6E": "Navy", "#8FA58A": "Sage", "#B8735A": "Terracotta"}
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


def wall_colour(st, room):
    return st["walls"].get(room) or STYLE_WALLS.get(st.get("style", "cozy"), {}).get(room) or WALL_CHOICES[room][0]


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
        self.panel = None
        self.deco_win = None
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
        for room, r in LAYOUT["rooms"].items():                       # paint the walls
            colour = wall_colour(self.st, room)
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
                self.frames[pid] = P.Frames(species or pid, 128, variant=variant)
            im = self.frames[pid].compose(mood, pose, yaw, wearing)
            self.pet_frames[key] = im.resize((px, px), Image.LANCZOS)
        return self.pet_frames[key]

    # ---- pictures for the decorating tiles
    def piece_thumb(self, pid, px):
        """One piece of furniture, cut out of its layer, on white."""
        key = ("thumb", pid, px)
        if key not in self.frames:
            im = Image.open(ART / "furniture" / f"{pid}.png").convert("RGBA")
            bb = im.getbbox() or (0, 0, im.width, im.height); pad = 10
            im = im.crop((max(0, bb[0] - pad), max(0, bb[1] - pad), min(im.width, bb[2] + pad), min(im.height, bb[3] + pad)))
            im.thumbnail((px, px), Image.LANCZOS)
            out = Image.new("RGBA", (px, px), (255, 255, 255, 255)); out.alpha_composite(im, ((px - im.width) // 2, (px - im.height) // 2))
            self.frames[key] = out
        return self.frames[key]

    def wall_thumb(self, hexc, px):
        key = ("wall", hexc, px)
        if key not in self.frames:
            im = Image.new("RGBA", (px, px), (255, 255, 255, 255)); d = ImageDraw.Draw(im)
            d.rounded_rectangle((3, 3, px - 4, px - 4), radius=max(4, px // 6), fill=hexc, outline=(200, 194, 214, 255), width=1)
            self.frames[key] = im
        return self.frames[key]

    def style_thumb(self, style, px):
        key = ("style", style, px)
        if key not in self.frames:
            im = Image.open(ART / ("closed.png" if style == "cozy" else f"closed-{style}.png")).convert("RGBA")
            bb = im.getbbox() or (0, 0, im.width, im.height); im = im.crop(bb); im.thumbnail((px, px), Image.LANCZOS)
            out = Image.new("RGBA", (px, px), (255, 255, 255, 255)); out.alpha_composite(im, ((px - im.width) // 2, (px - im.height) // 2))
            self.frames[key] = out
        return self.frames[key]

    def preview_image(self, width):
        """The open house as it is right now (walls, furniture, curtain), width px wide."""
        base, curtain = self._open_base()
        im = base.copy()
        if curtain is not None: im.alpha_composite(curtain)
        bb = im.getbbox() or (0, 0, im.width, im.height); im = im.crop(bb)
        im = im.resize((width, max(1, round(im.height * width / im.width))), Image.LANCZOS)
        bg = Image.new("RGBA", im.size, (255, 248, 240, 255)); bg.alpha_composite(im)
        return bg

    # ---- where things are
    def place(self):
        self.root.geometry(f"{self.size}x{self.size}+{int(self.x)}+{int(self.y)}")

    def door_screen(self):
        """Where the front door is, in screen pixels: the x of its centre and the y of the ground."""
        c = LAYOUT["closed"]; k = self.size / c["w"]
        return int(self.x + c["door"][0] * k), int(self.y + c["ground"] * k)

    def tell(self):
        dx, dy = self.door_screen()
        info = {"door_x": dx, "door_y": dy, "x": int(self.x), "y": int(self.y), "size": self.size, "area": list(self.area), "open": self.open,
                "style": self.st.get("style", "cozy")}
        if self.open and self.open_win is not None:                   # the open house's window and its rooms, in screen pixels, for drops
            try:
                w = self.open_win; wx, wy = w.winfo_x(), w.winfo_y()
                if getattr(self, "open_pos", None): wx, wy = self.open_pos
                sc = self.open_scale()
                info["open_box"] = [int(wx), int(wy), w.winfo_width(), w.winfo_height()]
                info["rooms"] = {room: [int(wx + r["wall"][0] * sc), int(wy + r["wall"][1] * sc), int(wx + r["wall"][2] * sc), int(wy + (r["floor"] + 8) * sc)]
                                 for room, r in LAYOUT["rooms"].items()}
            except tk.TclError:
                pass
        tell_pets(info)

    def remember(self):
        self.st["x"] = int(self.x); self.st["mon"] = [int(self.x + self.size // 2), int(self.floor + self.size // 2)]
        save_house(self.st)

    def move_to(self, area):
        """Come to the taskbar of another screen: a pet's panel asked for the house over there."""
        try:
            left, top, right, bottom = [int(v) for v in area]
        except (TypeError, ValueError):
            return
        self.area = (left, top, right, bottom); self.floor = bottom - self.size + round(8 * P.SCALE)
        self.x = max(left, min(right - self.size, right - self.size - round(30 * P.SCALE))); self.y = self.floor
        if self.open:
            self.toggle_open()                      # closes the open view; it opens again where the house now stands
        self.place(); self.remember(); self.tell()

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
        """The right click: a card like the pets' panel, with pictures."""
        HousePanel(self, e.x_root, e.y_root)

    def call_out(self, pid):
        try:
            (H.base_dir() / "plans" / f"house-out-{pid}.json").write_text(json.dumps({"out": True, "ts": time.time()}), encoding="utf-8")
        except OSError:
            pass

    def everyone_out(self):
        for o in self.inside_pets():
            self.call_out(o["pid"])

    # ---- what the pets' panels ask for
    def on_command(self, cmd, data=None):
        data = data or {}
        if cmd == "open" and not self.open: self.toggle_open()
        elif cmd == "close" and self.open: self.toggle_open()
        elif cmd == "toggle": self.toggle_open()
        elif cmd == "decorate": self.decorate_dialog(data.get("room") if data.get("room") in ROOM_NAMES else None)
        elif cmd == "style":
            want = data.get("style")
            self.set_style(want if want in STYLES else ("loft" if self.st.get("style", "cozy") == "cozy" else "cozy"))
        elif cmd == "out": self.everyone_out()
        elif cmd == "move": self.move_to(data.get("area") or [])
        elif cmd == "quit": self.quit()

    # ---- the open house
    def toggle_open(self):
        if self.open:
            self.open = False
            if self.open_win is not None:
                self.open_win.destroy(); self.open_win = None
            self.open_pos = None
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
            w.geometry(f"{ow}x{oh}+{x}+{y}"); self.open_pos = (x, y)
            self.canvas_label = tk.Label(w, bg=P.COLORKEY, bd=0, highlightthickness=0); self.canvas_label.pack()
            self.canvas_label.bind("<ButtonPress-1>", self.on_open_press); self.canvas_label.bind("<B1-Motion>", self.on_open_drag)
            self.canvas_label.bind("<ButtonRelease-1>", self.on_open_release)
            self.canvas_label.bind("<Button-3>", self.on_menu)
            self.draw_open()
        self.tell()

    # ---- input on the open house: a click on a room decorates it, a drag moves the house, the menu closes it
    def pet_at(self, x, y):
        """The pet drawn under a point on the open house, with its picture, or None."""
        for pid, (x0, y0, x1, y1, im) in (getattr(self, "pet_boxes", None) or {}).items():
            if x0 <= x <= x1 and y0 <= y <= y1 and im.getpixel((min(im.width - 1, max(0, int(x - x0))), min(im.height - 1, max(0, int(y - y0)))))[3] > 40:
                return pid, im
        return None

    def on_open_press(self, e):
        w = self.open_win
        hit = self.pet_at(e.x, e.y) if getattr(self, "pet_boxes", None) else None
        if hit and hit[0] != "__house__":
            pid, im = hit                                             # a pet: pick it up out of its room
            ghost = self._keyed(im)
            self.pet_drag = {"pid": pid, "ghost": P.F.Overlay(self.root, ghost, e.x_root - im.width // 2, e.y_root - im.height // 2, P.COLORKEY), "img": ghost, "w": im.width, "moved": False}
            self.open_drag = None; return
        self.pet_drag = None
        self.open_drag = (e.x_root, e.y_root, w.winfo_x(), w.winfo_y(), False, e.x, e.y)

    def on_open_drag(self, e):
        pd = getattr(self, "pet_drag", None)
        if pd:
            pd["moved"] = True; pd["ghost"].move(e.x_root - pd["w"] // 2, e.y_root - pd["w"] // 2); return
        if not getattr(self, "open_drag", None): return
        sx, sy, ox, oy, _, cx, cy = self.open_drag
        dx, dy = e.x_root - sx, e.y_root - sy
        if abs(dx) + abs(dy) > 4:
            self.open_drag = (sx, sy, ox, oy, True, cx, cy)
            self.open_pos = (ox + dx, oy + dy)
            self.open_win.geometry(f"+{ox + dx}+{oy + dy}")

    def on_open_release(self, e):
        pd = getattr(self, "pet_drag", None)
        if pd:
            self.pet_drag = None; pd["ghost"].close()
            w = self.open_win
            try: bx, by, bw, bh = w.winfo_x(), w.winfo_y(), w.winfo_width(), w.winfo_height()
            except tk.TclError: return
            inside = bx <= e.x_root <= bx + bw and by <= e.y_root <= by + bh
            if pd["moved"] and not inside:                            # let go outside the house: it comes out right there
                try:
                    (H.base_dir() / "plans" / f"house-out-{pd['pid']}.json").write_text(json.dumps({"out": True, "x": int(e.x_root), "y": int(e.y_root), "ts": time.time()}), encoding="utf-8")
                except OSError:
                    pass
            elif not pd["moved"]:                                     # just a click on it: the room's dialog, as before
                room = self.room_at(e.x, e.y)
                if room: self.room_dialog(room, e.x_root, e.y_root)
            return
        d = getattr(self, "open_drag", None)
        if not d: return
        self.open_drag = None
        sx, sy, ox, oy, moved, cx, cy = d
        if moved:                                                 # settle on the taskbar of whatever monitor it landed on
            w = self.open_win; ow, oh = w.winfo_width(), w.winfo_height()
            px, py = self.open_pos                                     # where the drag left it (winfo_x lags behind)
            left, top, right, bottom = P.monitor_work_area(px + ow // 2, py + oh // 2)
            self.area = (left, top, right, bottom); self.floor = bottom - self.size + round(8 * P.SCALE)
            x = max(left, min(right - ow, px)); y = max(top, bottom - oh + round(10 * P.SCALE))
            w.geometry(f"+{x}+{y}"); self.open_pos = (x, y)
            self.x = max(left, min(right - self.size, x + ow // 2 - self.size // 2)); self.y = self.floor
            self.remember(); self.tell()
            return
        room = self.room_at(cx, cy)
        if room:
            self.room_dialog(room, e.x_root, e.y_root)

    def room_at(self, x, y):
        """Which room a point on the open house is in, or None (the roof, the ground, the gaps)."""
        s = self.open_scale()
        for room, r in LAYOUT["rooms"].items():
            x0, y0, x1, y1 = r["wall"]
            if x0 * s <= x <= x1 * s and y0 * s <= y <= (r["floor"] + 8) * s:
                return room
        return None

    def inside_pets(self):
        return [o for o in H.others("__house__", None) if o.get("inside")]

    def draw_open(self):
        if not self.open or self.open_win is None:
            return
        base, curtain = self._open_base()
        im = base.copy()
        s = self.open_scale(); boxes = {}
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
            boxes[o["pid"]] = (max(0, x), max(0, y), max(0, x) + px, max(0, y) + px, pet)
        if curtain is not None:
            im.alpha_composite(curtain)
        self.pet_boxes = boxes
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

    # ---- decorate, with pictures
    def decorate_dialog(self, room=None, at=None):
        """Every piece, every wall colour and both styles as tiles, with a preview of the house that redraws on each click.
        room: just that room (a click on the open house), else the whole house. at: screen point to open near."""
        old = self.deco_win
        if old is not None:
            try: old.destroy()
            except tk.TclError: pass
        win = tk.Toplevel(self.root); win.title("Decorate the house" if not room else ROOM_NAMES[room])
        win.attributes("-topmost", True); P.window_icon(win); win.configure(bg=M.BG)
        self.deco_win = win; win.keep = []
        Sc = P.SCALE
        head = tk.Frame(win, bg=M.BG); head.pack(fill="x", padx=14, pady=(12, 2))
        tk.Label(head, text="The house" if not room else ROOM_NAMES[room], bg=M.BG, fg=M.INK, font=("Segoe UI", 12, "bold")).pack(side="left")
        tk.Label(head, text="Click a picture to put it in or take it out. Anything with a price is in the shop.", bg=M.BG, fg=M.SOFT, font=("Segoe UI", 9)).pack(side="left", padx=(12, 0))
        cols = tk.Frame(win, bg=M.BG); cols.pack(padx=14, pady=(4, 8), anchor="nw")
        left = tk.Frame(cols, bg=M.BG); left.pack(side="left", anchor="n", padx=(0, 14))
        right = tk.Frame(cols, bg=M.BG); right.pack(side="left", anchor="n")
        preview = tk.Label(left, bg=M.BG, bd=0); preview.pack(anchor="w")
        style_box = tk.Frame(left, bg=M.BG); style_box.pack(anchor="w", pady=(6, 0))
        px = round(46 * Sc)

        def draw_preview():
            preview.img = ImageTk.PhotoImage(self.preview_image(round(360 * Sc))); preview.configure(image=preview.img)

        def after(fn):
            def go():
                fn(); redraw(); draw_preview()
            return go

        def redraw():
            for c in list(style_box.winfo_children()) + list(right.winfo_children()): c.destroy()
            win.keep.clear()
            tk.Label(style_box, text="STYLE", bg=M.BG, fg=M.SOFT, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(2, 2))
            tiles = []
            for sid, label in STYLES.items():
                ph = ImageTk.PhotoImage(self.style_thumb(sid, px)); win.keep.append(ph)
                tiles.append((ph, label, after(lambda s=sid: self.set_style(s)), self.st.get("style", "cozy") == sid))
            M.tile_grid(style_box, Sc, tiles, cols=4, keep=win.keep)
            for r in ([room] if room else ROOM_ORDER):
                tk.Label(right, text=ROOM_NAMES[r].upper(), bg=M.BG, fg=M.SOFT, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(4 if r == ROOM_ORDER[0] or room else 8, 2))
                tiles = []
                for pid, (name, rr, inc, price) in PIECES.items():
                    if rr != r: continue
                    ph = ImageTk.PhotoImage(self.piece_thumb(pid, px)); win.keep.append(ph)
                    on = bool(self.st["furniture"].get(pid))
                    if owns_piece(pid):
                        tiles.append((ph, name, after(lambda p=pid, o=on: self.set_piece(p, not o)), on, "in" if on else "out"))
                    else:
                        tiles.append((ph, name, lambda: webbrowser.open(P.SHOP.get("store_url", "")), False, f"{price} in the shop"))
                M.tile_grid(right, Sc, tiles, cols=4, keep=win.keep)
                sw = tk.Frame(right, bg=M.BG); sw.pack(anchor="w", pady=(3, 0))
                tk.Label(sw, text="Walls", bg=M.BG, fg=M.SOFT, font=("Segoe UI", 8)).pack(side="left", padx=(2, 6))
                cur = wall_colour(self.st, r).lower()
                for hexc in WALL_CHOICES[r]:
                    chip = tk.Label(sw, bg=hexc, width=3, cursor="hand2", highlightthickness=2, highlightbackground=M.ACCENT if hexc.lower() == cur else M.LINE, bd=0)
                    chip.pack(side="left", padx=2)
                    chip.bind("<Button-1>", lambda e, rm=r, h=hexc: after(lambda: self.set_wall(rm, h))())
                    M.tip(chip, WALL_NAMES.get(hexc.upper(), "Wall"))
        row = tk.Frame(left, bg=M.BG); row.pack(anchor="w", pady=(12, 4))
        if room:
            tk.Button(row, text="The whole house...", command=lambda: (win.destroy(), self.decorate_dialog()), padx=10).pack(side="left")
        tk.Button(row, text="Done", command=win.destroy, padx=14).pack(side="left", padx=(8 if room else 0, 0))
        redraw(); draw_preview()
        win.update_idletasks()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        if at:
            x, y = int(at[0]) - w // 2, int(at[1]) - h - 24
        else:
            x, y = int(self.x) + self.size // 2 - w // 2, int(self.y) - h - 20
        win.geometry(f"+{max(self.area[0], min(self.area[2] - w, x))}+{max(self.area[1], min(self.area[3] - h, y))}")

    def room_dialog(self, room, x, y):
        """Clicked a room in the open house: that room's pieces and walls, right where the click was."""
        self.decorate_dialog(room, at=(x, y))

    def set_style(self, style):
        self.st["style"] = style; self.st["walls"] = {}; save_house(self.st)
        self.frames.pop("open_key", None); self.closed_img = self._closed_image(); self.label.configure(image=self.closed_img); self.draw_open(); self.tell()

    def set_piece(self, pid, on):
        self.st["furniture"][pid] = bool(on); save_house(self.st); self.draw_open()

    def set_wall(self, room, hexc):
        self.st["walls"][room] = hexc; save_house(self.st)
        self.frames.pop("open_key", None); self.draw_open()

    # ---- loop
    def tick(self):
        self.anim += 1
        cmd = S.take_command("house")
        if cmd:
            try:
                self.on_command(cmd.get("cmd"), cmd)
            except tk.TclError:
                pass
        if self.open and self.anim % 2 == 0:
            self.draw_open()
        if self.anim % 5 == 0:                 # every 1.5 s; the pets give up on a house after 20 s
            self.tell()
        if self.selftest and self.anim > 10:
            print("house selftest ok"); self.root.destroy(); return
        self.root.after(300, self.tick)

    def quit(self):
        """Put the house away. Its door file goes, so the pets stop looking for it; a pet's panel brings it back."""
        self.remember()
        try:
            door_file().unlink()
        except OSError:
            pass
        self.root.destroy()


class HousePanel:
    """The house's right-click card: open or close it, decorate, the style, who is inside, put it away."""
    def __init__(self, house, x, y):
        self.h = house; self.S = P.SCALE
        old = house.panel
        if old is not None:
            old.close()
        house.panel = self
        self.win = w = tk.Toplevel(house.root)
        w.overrideredirect(True); w.attributes("-topmost", True); w.configure(bg=M.LINE)
        self.frame = tk.Frame(w, bg=M.BG, padx=round(12 * self.S), pady=round(10 * self.S)); self.frame.pack(padx=1, pady=1)
        self.keep = []
        self.at = (x, y)
        self.build()
        w.bind("<Escape>", lambda e: self.close())
        w.bind("<FocusOut>", lambda e: self.timers.append(self.win.after(120, lambda: None if self.win.focus_displayof() else self.close())))
        self.timers = [w.after(60, lambda: (w.focus_force(), w.lift()))]   # cancelled on close (see menu.Panel)

    def close(self):
        if self.h.panel is self:
            self.h.panel = None
        for t in self.timers:
            try: self.win.after_cancel(t)
            except tk.TclError: pass
        self.timers = []
        try: self.win.destroy()
        except tk.TclError: pass

    def act(self, fn):
        def go():
            self.close(); fn()
        return go

    def build(self):
        h = self.h; S = self.S; BG = M.BG
        top = tk.Frame(self.frame, bg=BG); top.pack(fill="x", pady=(0, round(6 * S)))
        ph = ImageTk.PhotoImage(h.style_thumb(h.st.get("style", "cozy"), round(56 * S))); self.keep.append(ph)
        tk.Label(top, image=ph, bg=BG, bd=0).pack(side="left", padx=(0, round(8 * S)))
        txt = tk.Frame(top, bg=BG); txt.pack(side="left", fill="x", expand=True)
        tk.Label(txt, text="The house", bg=BG, fg=M.INK, font=("Segoe UI", 13, "bold"), anchor="w").pack(anchor="w")
        inside = h.inside_pets()
        who = ", ".join(f"{o.get('name', o['pid'])} in the {ROOM_NAMES.get(o['inside'], o['inside']).lower()}" for o in inside) or "nobody inside right now"
        tk.Label(txt, text=f"{STYLES.get(h.st.get('style', 'cozy'), 'Cozy')} style · {who}", bg=BG, fg=M.SOFT, font=("Segoe UI", 9), anchor="w", wraplength=round(300 * S), justify="left").pack(anchor="w")
        xb = tk.Label(top, text="✕", bg=BG, fg=M.SOFT, font=("Segoe UI", 11), cursor="hand2"); xb.pack(side="right", anchor="n")
        xb.bind("<Button-1>", lambda e: self.close())
        other = "loft" if h.st.get("style", "cozy") == "cozy" else "cozy"
        sph = ImageTk.PhotoImage(h.style_thumb(other, round(28 * S))); self.keep.append(sph)
        tiles = [("\U0001F3E0", "Close the house" if h.open else "Open the house", self.act(h.toggle_open)),
                 ("\U0001F6CB️", "Decorate", self.act(h.decorate_dialog)),
                 (sph, f"{STYLES[other]} style", self.act(lambda: h.set_style(other)))]
        if inside:
            tiles.append(("\U0001F6AA", "Everyone out", self.act(h.everyone_out)))
        tiles.append(("\U0001F4E6", "Put it away", self.act(h.quit)))
        tk.Label(self.frame, text="THE HOUSE", bg=BG, fg=M.SOFT, font=("Segoe UI", 8, "bold"), anchor="w").pack(anchor="w", pady=(2, 2))
        M.tile_grid(self.frame, S, tiles, cols=5, keep=self.keep, tips=M.HOUSE_TIPS)
        if inside:
            tk.Label(self.frame, text="INSIDE, CLICK TO CALL OUT", bg=BG, fg=M.SOFT, font=("Segoe UI", 8, "bold"), anchor="w").pack(anchor="w", pady=(6, 2))
            pets = []
            for o in inside:
                try:
                    im = h.pet_image(o["pid"], "happy", "idle", 0, o.get("wearing", {}), 128, o.get("species"), o.get("variant"))
                    bg = Image.new("RGBA", im.size, (255, 255, 255, 255)); bg.alpha_composite(im)
                    ph2 = ImageTk.PhotoImage(bg.crop((15, 10, 113, 118)).resize((round(34 * S),) * 2, Image.LANCZOS)); self.keep.append(ph2); ic = ph2
                except Exception:
                    ic = "\U0001F43E"
                pets.append((ic, f"{o.get('name', o['pid'])}: {ROOM_NAMES.get(o['inside'], o['inside']).lower()}", self.act(lambda pid=o["pid"]: h.call_out(pid))))
            M.tile_grid(self.frame, S, pets, cols=5, keep=self.keep)
        tk.Label(self.frame, text="Click a room in the open house to decorate just that room. Drag the house to move it. Right-click any pet and it's on that menu too.",
                 bg=BG, fg=M.SOFT, font=("Segoe UI", 8), wraplength=round(400 * S), justify="left").pack(anchor="w", pady=(6, 0))
        self.win.update_idletasks()
        w, hh = self.win.winfo_reqwidth(), self.win.winfo_reqheight()
        x, y = self.at; a = h.area
        x = max(a[0], min(a[2] - w, x - w // 2)); y = max(a[1], min(a[3] - hh, y - hh - round(8 * S)))
        self.win.geometry(f"+{int(x)}+{int(y)}")


def main(selftest=False):
    if not P.claim_instance("house"):
        return
    House(selftest=selftest).root.mainloop()
