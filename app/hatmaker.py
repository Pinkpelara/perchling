"""The hat maker. An owner picks a shape, two colours and a sticker, names the hat, and it goes in the closet
like any other hat. Every hat has a code (PH1-cap-1E90FF-FFFFFF-star-FFD166-Blue Star) that anyone can paste into
their own app to get the same hat, so hats travel between friends without a server.

The shapes are rendered once per pet and pose (tools/sprites, layer ids maker:cap and so on) with id colours:
the main part in the red channel, the trim in green, the sticker spot in blue, and the shine in all three.
paint() turns one of those frames into the owner's hat. Nothing is sent anywhere.
"""
import hashlib, json, re, time
import tkinter as tk
from tkinter import colorchooser
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageTk

SHAPES = {"cap": "Snapback", "beanie": "Beanie", "bucket": "Bucket hat", "tophat": "Top hat", "cowboy": "Ranch hat", "visor": "Visor"}
STICKERS = {"none": "Nothing", "star": "Star", "heart": "Heart", "bolt": "Bolt", "skull": "Skull", "smile": "Smiley",
            "diamond": "Diamond", "flower": "Flower", "letter": "Initial"}
SWATCHES = [("Black", "#1E1B24"), ("White", "#F4F1EA"), ("Charcoal", "#3A3A46"), ("Navy", "#1F2A5A"),
            ("Red", "#D63B3B"), ("Orange", "#E0862A"), ("Gold", "#F5C242"), ("Lime", "#8BD34A"),
            ("Teal", "#2FB3A3"), ("Sky", "#5AB0F0"), ("Royal", "#3B5BDB"), ("Purple", "#6C4BD0"),
            ("Pink", "#F58EA6"), ("Brown", "#7A4E2D"), ("Olive", "#6B7A4E"), ("Cream", "#FFF3D6")]
SPOT_ON = {"cap": "trim", "beanie": "trim", "bucket": "main", "tophat": "trim", "cowboy": "main", "visor": "main"}   # the part the sticker sits on
LIT = 220          # the red channel of a fully lit main part in the rendered layers
SHEEN = 0.6        # how much of the rendered highlight to keep


# ------------------------------------------------------------------ hats on disk
def load_hats(folder):
    out = []
    for p in sorted(Path(folder).glob("*.json")):
        try:
            h = json.loads(p.read_text(encoding="utf-8"))
            if h.get("shape") in SHAPES: out.append(h)
        except (OSError, ValueError):
            continue
    return sorted(out, key=lambda h: h.get("made", 0))


def load_hat(folder, hat_id):
    p = Path(folder) / f"{hat_id}.json"
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    except (OSError, ValueError):
        return None


def save_hat(folder, hat):
    hat = normal(hat)
    Path(folder).mkdir(parents=True, exist_ok=True)
    (Path(folder) / f"{hat['id']}.json").write_text(json.dumps(hat, indent=1), encoding="utf-8")
    return hat


def delete_hat(folder, hat_id):
    try:
        (Path(folder) / f"{hat_id}.json").unlink()
    except OSError:
        pass


def hat_id(hat):
    key = "|".join([hat["shape"], hat["main"].upper(), hat["trim"].upper(), hat.get("sticker", "none"), hat.get("sticker_color", "").upper()])
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]


def normal(hat):
    """A hat dict with every field present, colours as #RRGGBB, and its id."""
    h = {"shape": hat.get("shape", "cap") if hat.get("shape") in SHAPES else "cap",
         "main": color(hat.get("main"), "#1E1B24"), "trim": color(hat.get("trim"), "#F4F1EA"),
         "sticker": hat.get("sticker", "none") or "none", "sticker_color": color(hat.get("sticker_color"), "#F5C242"),
         "name": (hat.get("name") or "").strip()[:24], "made": hat.get("made") or time.time()}
    tok = h["sticker"]
    if not (tok in STICKERS or re.fullmatch(r"letter[A-Z0-9]", tok)):
        h["sticker"] = "none"
    h["id"] = hat_id(h)
    if not h["name"]:
        h["name"] = SHAPES[h["shape"]]
    return h


def color(v, default):
    v = (v or "").strip().lstrip("#")
    return "#" + v.upper() if re.fullmatch(r"[0-9a-fA-F]{6}", v) else default


def rgb(hexstr):
    h = hexstr.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# ------------------------------------------------------------------ the code
def to_code(hat):
    h = normal(hat)
    return "-".join(["PH1", h["shape"], h["main"][1:], h["trim"][1:], h["sticker"], h["sticker_color"][1:], h["name"]])


def from_code(text):
    """A hat from a code, or None if it isn't one."""
    parts = (text or "").strip().split("-", 6)
    if len(parts) < 6 or parts[0].upper() != "PH1" or parts[1] not in SHAPES:
        return None
    name = parts[6] if len(parts) > 6 else ""
    return normal({"shape": parts[1], "main": parts[2], "trim": parts[3], "sticker": parts[4], "sticker_color": parts[5], "name": name})


# ------------------------------------------------------------------ painting
def sticker_image(sticker, colr, px=96):
    """A flat sticker, see-through around it."""
    im = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    if sticker in ("none", "", None):
        return im
    d = ImageDraw.Draw(im)
    c = rgb(colr) + (255,)
    dark = (35, 33, 59, 255) if sum(rgb(colr)) > 300 else (255, 255, 255, 255)
    line = max(2, px // 32)
    P = lambda pts: [(x * px, y * px) for x, y in pts]
    if sticker == "star":
        import math
        pts = []
        for i in range(10):
            r = 0.47 if i % 2 == 0 else 0.2; a = -math.pi / 2 + i * math.pi / 5
            pts.append((0.5 + r * math.cos(a), 0.52 + r * math.sin(a)))
        d.polygon(P(pts), fill=c, outline=dark, width=line)
    elif sticker == "heart":
        d.polygon(P([(0.09, 0.42), (0.91, 0.42), (0.5, 0.92)]), fill=c)
        d.ellipse(P([(0.08, 0.14), (0.52, 0.58)]), fill=c); d.ellipse(P([(0.48, 0.14), (0.92, 0.58)]), fill=c)
    elif sticker == "bolt":
        d.polygon(P([(0.58, 0.04), (0.22, 0.56), (0.47, 0.56), (0.38, 0.96), (0.78, 0.42), (0.53, 0.42)]), fill=c, outline=dark, width=line)
    elif sticker == "skull":
        d.ellipse(P([(0.14, 0.06), (0.86, 0.72)]), fill=c)
        d.rounded_rectangle(P([(0.3, 0.55), (0.7, 0.9)]), radius=px * 0.08, fill=c)
        d.ellipse(P([(0.26, 0.3), (0.46, 0.52)]), fill=dark); d.ellipse(P([(0.54, 0.3), (0.74, 0.52)]), fill=dark)
        d.polygon(P([(0.5, 0.52), (0.44, 0.64), (0.56, 0.64)]), fill=dark)
        for x in (0.42, 0.5, 0.58): d.line(P([(x, 0.76), (x, 0.9)]), fill=dark, width=line)
    elif sticker == "smile":
        d.ellipse(P([(0.06, 0.06), (0.94, 0.94)]), fill=c, outline=dark, width=line)
        d.ellipse(P([(0.28, 0.32), (0.4, 0.46)]), fill=dark); d.ellipse(P([(0.6, 0.32), (0.72, 0.46)]), fill=dark)
        d.arc(P([(0.24, 0.36), (0.76, 0.8)]), start=20, end=160, fill=dark, width=line + 1)
    elif sticker == "diamond":
        d.polygon(P([(0.5, 0.06), (0.92, 0.4), (0.5, 0.94), (0.08, 0.4)]), fill=c, outline=dark, width=line)
        lighter = tuple(min(255, v + 70) for v in rgb(colr)) + (255,)
        d.polygon(P([(0.2, 0.4), (0.5, 0.12), (0.8, 0.4)]), fill=lighter)
    elif sticker == "flower":
        import math
        for i in range(5):
            a = -math.pi / 2 + i * 2 * math.pi / 5; cx, cy = 0.5 + 0.27 * math.cos(a), 0.5 + 0.27 * math.sin(a)
            d.ellipse(P([(cx - 0.2, cy - 0.2), (cx + 0.2, cy + 0.2)]), fill=c)
        d.ellipse(P([(0.36, 0.36), (0.64, 0.64)]), fill=dark)
    elif sticker.startswith("letter"):
        ch = sticker[6:7] or "A"
        f = _font(int(px * 0.8))
        w = f.getlength(ch); bb = f.getbbox(ch)
        d.text(((px - w) / 2, (px - (bb[3] - bb[1])) / 2 - bb[1]), ch, font=f, fill=c, stroke_width=line, stroke_fill=dark)
    return im


def _font(size):
    for name in ("seguisb.ttf", "segoeuib.ttf", "arialbd.ttf"):
        p = Path("C:/Windows/Fonts") / name
        if p.exists(): return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def paint(frame, hat):
    """The owner's hat from an id-coloured frame: colours by channel, the shine kept, the sticker on its spot."""
    r, g, b, a = frame.split()
    low = ImageChops.darker(ImageChops.darker(r, g), b)                      # what all three channels share is the shine
    R, G, B = (ImageChops.subtract(ch, low) for ch in (r, g, b))
    sheen = low.point(lambda x: int(x * SHEEN))
    main, trim = rgb(hat["main"]), rgb(hat["trim"])
    under = trim if SPOT_ON.get(hat["shape"]) == "trim" else main       # the spot takes the colour of the part it sits on
    chans = []
    for i in range(3):
        km, kt, ku = main[i] / LIT, trim[i] / LIT, under[i] / LIT
        ch = ImageChops.add(R.point(lambda x, k=km: min(255, int(x * k))), G.point(lambda x, k=kt: min(255, int(x * k))))
        ch = ImageChops.add(ch, B.point(lambda x, k=ku: min(255, int(x * k))))
        chans.append(ImageChops.add(ch, sheen))
    out = Image.merge("RGBA", (chans[0], chans[1], chans[2], a))
    sticker = hat.get("sticker", "none")
    if sticker and sticker != "none":
        spot = B.point(lambda x: 255 if x > 24 else 0)
        box = spot.getbbox()
        if box:
            bw, bh = box[2] - box[0], box[3] - box[1]
            if bw >= 4 and bh >= 4:
                peak = max(B.crop(box).getdata()) or 1
                lit = B.point(lambda x, p=peak: min(255, int(x * 255 / p)))
                st = sticker_image(sticker, hat.get("sticker_color", "#F5C242"), 96).resize((max(2, int(bw * 0.92)), max(2, int(bh * 0.92))), Image.LANCZOS)
                layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
                layer.alpha_composite(st, (box[0] + (bw - st.width) // 2, box[1] + (bh - st.height) // 2))
                lr, lg, lb, la = layer.split()
                la = ImageChops.multiply(la, spot)                               # clipped to the spot
                shaded = Image.merge("RGBA", (ImageChops.multiply(lr, lit), ImageChops.multiply(lg, lit), ImageChops.multiply(lb, lit), la))
                out.alpha_composite(shaded)
    return out


# ------------------------------------------------------------------ the window
class HatMaker:
    """Shape, colours, sticker and name on the left; the pet trying it on on the right; your hats underneath."""
    BG = "#FFF8F0"

    def __init__(self, pet, folder, scale=1.0):
        self.pet, self.folder, self.scale = pet, Path(folder), scale
        self.win = win = tk.Toplevel(pet.root); win.title("Hat maker"); win.attributes("-topmost", True); win.configure(bg=self.BG)
        try:
            import perchling as P; P.window_icon(win)
        except Exception:
            pass
        win.geometry(f"+{max(pet.area[0], int(pet.x) - 300)}+{max(pet.area[1], int(pet.y) - 560)}")
        self.shape = tk.StringVar(value="cap"); self.main = tk.StringVar(value="#1E1B24"); self.trim = tk.StringVar(value="#F4F1EA")
        self.sticker = tk.StringVar(value="star"); self.scolor = tk.StringVar(value="#F5C242"); self.letter = tk.StringVar(value="")
        self.name = tk.StringVar(value="")
        for v in (self.shape, self.main, self.trim, self.sticker, self.scolor, self.letter):
            v.trace_add("write", lambda *a: self.refresh())
        left = tk.Frame(win, bg=self.BG); left.pack(side="left", fill="y", padx=(16, 8), pady=12, anchor="n")
        right = tk.Frame(win, bg=self.BG); right.pack(side="left", fill="y", padx=(8, 16), pady=12, anchor="n")
        self.title(left, "Shape")
        grid = tk.Frame(left, bg=self.BG); grid.pack(anchor="w")
        for i, (sid, label) in enumerate(SHAPES.items()):
            tk.Radiobutton(grid, text=label, value=sid, variable=self.shape, bg=self.BG, activebackground=self.BG, anchor="w",
                           font=("Segoe UI", 10)).grid(row=i // 3, column=i % 3, sticky="w", padx=4)
        self.title(left, "Main color"); self.swatches(left, self.main)
        self.title(left, "Trim color"); self.swatches(left, self.trim)
        self.title(left, "Sticker")
        grid = tk.Frame(left, bg=self.BG); grid.pack(anchor="w")
        for i, (sid, label) in enumerate(STICKERS.items()):
            tk.Radiobutton(grid, text=label, value=sid, variable=self.sticker, bg=self.BG, activebackground=self.BG, anchor="w",
                           font=("Segoe UI", 10)).grid(row=i // 5, column=i % 5, sticky="w", padx=2)
        tk.Label(grid, text="Initial:", bg=self.BG, fg="#6B6685", font=("Segoe UI", 9)).grid(row=1, column=4, sticky="e", padx=(8, 2))
        tk.Entry(grid, textvariable=self.letter, width=3, font=("Segoe UI", 10)).grid(row=1, column=5, sticky="w")
        self.title(left, "Sticker color"); self.swatches(left, self.scolor)
        self.title(left, "Name")
        tk.Entry(left, textvariable=self.name, width=26, font=("Segoe UI", 10)).pack(anchor="w", padx=8)
        btns = tk.Frame(left, bg=self.BG); btns.pack(anchor="w", pady=(12, 0))
        tk.Button(btns, text="Wear it", command=self.wear, padx=12, bg="#5A3FC0", fg="#FFFFFF", activebackground="#4A32A6", activeforeground="#FFFFFF",
                  relief="flat", font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Button(btns, text="Save", command=self.save, padx=12).pack(side="left", padx=(8, 0))
        tk.Button(btns, text="Copy code", command=self.copy_code, padx=12).pack(side="left", padx=(8, 0))
        tk.Button(btns, text="Close", command=win.destroy, padx=12).pack(side="left", padx=(8, 0))

        tk.Label(right, text=f"{pet.st['name']} tries it on", bg=self.BG, fg="#23213B", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        views = tk.Frame(right, bg=self.BG); views.pack(anchor="w")
        self.preview = tk.Label(views, bg=self.BG, bd=0); self.preview.pack(side="left")
        self.preview2 = tk.Label(views, bg=self.BG, bd=0); self.preview2.pack(side="left", anchor="s")
        self.status = tk.Label(right, text="", bg=self.BG, fg="#6B6685", font=("Segoe UI", 9)); self.status.pack(anchor="w", pady=(2, 8))
        self.title(right, "Your hats")
        self.listbox = tk.Listbox(right, height=6, width=34, font=("Segoe UI", 10), activestyle="none", bd=1, relief="solid")
        self.listbox.pack(anchor="w")
        self.listbox.bind("<<ListboxSelect>>", lambda e: self.load_selected())
        hb = tk.Frame(right, bg=self.BG); hb.pack(anchor="w", pady=(6, 0))
        tk.Button(hb, text="Wear", command=self.wear_selected, padx=10).pack(side="left")
        tk.Button(hb, text="Copy code", command=self.copy_selected, padx=10).pack(side="left", padx=(6, 0))
        tk.Button(hb, text="Delete", command=self.delete_selected, padx=10).pack(side="left", padx=(6, 0))
        self.title(right, "Got a code from a friend?")
        cr = tk.Frame(right, bg=self.BG); cr.pack(anchor="w")
        self.code_in = tk.Entry(cr, width=30, font=("Segoe UI", 10)); self.code_in.pack(side="left")
        tk.Button(cr, text="Add", command=self.add_code, padx=10).pack(side="left", padx=(6, 0))
        self.hats = []
        self.fill_list(); self.refresh()

    def title(self, parent, text):
        tk.Label(parent, text=text, bg=self.BG, fg="#5A3FC0", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(8, 2))

    def swatches(self, parent, var):
        grid = tk.Frame(parent, bg=self.BG); grid.pack(anchor="w", padx=8)
        for i, (name, hexstr) in enumerate(SWATCHES):
            b = tk.Button(grid, bg=hexstr, activebackground=hexstr, width=2, relief="flat", bd=0, cursor="hand2",
                          command=lambda h=hexstr, v=var: v.set(h))
            b.grid(row=0, column=i, padx=1, pady=2)
        tk.Button(grid, text="More...", command=lambda v=var: self.more(v), relief="flat", bg="#EFE7FF", padx=6,
                  font=("Segoe UI", 8)).grid(row=0, column=len(SWATCHES), padx=(6, 0))

    def more(self, var):
        got = colorchooser.askcolor(color=var.get(), parent=self.win, title="Pick a color")
        if got and got[1]:
            var.set(got[1].upper())

    def current(self):
        tok = self.sticker.get()
        if tok == "letter":
            ch = (self.letter.get().strip()[:1] or (self.name.get().strip()[:1]) or "A").upper()
            tok = "letter" + (ch if re.fullmatch(r"[A-Z0-9]", ch) else "A")
        return normal({"shape": self.shape.get(), "main": self.main.get(), "trim": self.trim.get(), "sticker": tok,
                       "sticker_color": self.scolor.get(), "name": self.name.get()})

    def refresh(self):
        try:
            hat = self.current()
        except tk.TclError:
            return
        fr = self.pet.frames
        px = round(200 * self.scale)
        for label, yaw, size in ((self.preview, 0, px), (self.preview2, 300, round(px * 0.66))):
            im = fr.compose("happy", "idle", yaw, dict(self.pet.st["wearing"], hat="maker-preview"), preview_hat=hat)
            bg = Image.new("RGBA", im.size, (255, 248, 240, 255)); bg.alpha_composite(im)
            label.img = ImageTk.PhotoImage(bg.resize((size, size), Image.LANCZOS)); label.configure(image=label.img)

    def fill_list(self):
        self.hats = load_hats(self.folder)
        self.listbox.delete(0, "end")
        for h in self.hats:
            self.listbox.insert("end", f"{h['name']}  ({SHAPES.get(h['shape'], h['shape'])})")

    def selected(self):
        sel = self.listbox.curselection()
        return self.hats[sel[0]] if sel and sel[0] < len(self.hats) else None

    def load_selected(self):
        h = self.selected()
        if not h: return
        self.shape.set(h["shape"]); self.main.set(h["main"]); self.trim.set(h["trim"]); self.scolor.set(h["sticker_color"])
        if h["sticker"].startswith("letter"):
            self.sticker.set("letter"); self.letter.set(h["sticker"][6:])
        else:
            self.sticker.set(h["sticker"])
        self.name.set(h["name"])

    def save(self, quiet=False):
        hat = save_hat(self.folder, self.current())
        self.fill_list()
        if not quiet: self.status.configure(text=f"Saved. It's in the closet as {hat['name']}.")
        return hat

    def wear(self):
        hat = self.save(quiet=True)
        self.put_on(hat)

    def put_on(self, hat):
        self.pet.st["wearing"]["hat"] = "my:" + hat["id"]
        self.pet.frames.forget_custom(hat["id"])
        self.pet.save_state(); self.pet.show(*self.pet.last_frame)
        self.status.configure(text=f"{self.pet.st['name']} is wearing {hat['name']}.")

    def wear_selected(self):
        h = self.selected()
        if h: self.put_on(h)

    def copy_code(self):
        hat = self.save(quiet=True)
        self.clip(to_code(hat))

    def copy_selected(self):
        h = self.selected()
        if h: self.clip(to_code(h))

    def clip(self, code):
        self.win.clipboard_clear(); self.win.clipboard_append(code)
        self.status.configure(text="Code copied. Send it to a friend and they paste it in their hat maker.")

    def delete_selected(self):
        h = self.selected()
        if not h: return
        delete_hat(self.folder, h["id"])
        if self.pet.st["wearing"].get("hat") == "my:" + h["id"]:
            self.pet.st["wearing"]["hat"] = None; self.pet.save_state(); self.pet.show(*self.pet.last_frame)
        self.fill_list(); self.status.configure(text=f"{h['name']} is gone.")

    def add_code(self):
        hat = from_code(self.code_in.get())
        if not hat:
            self.status.configure(text="That doesn't look like a hat code. It starts with PH1-."); return
        save_hat(self.folder, hat); self.fill_list(); self.code_in.delete(0, "end")
        self.status.configure(text=f"Got {hat['name']}. It's in the closet now.")
        self.put_on(hat)
