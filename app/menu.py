"""The pet's panel: what the right click opens. A card with the pet's portrait and name, then tiles in groups
(Do, Say, Share, Wear, Household, Settings), each with an icon, and picture previews for the tricks and the
Together picks. Sub-pages open in the same card with a Back button. It closes when you click anywhere else.

Icons come from the Windows emoji font, drawn once per size and cached. Previews are the pet's own frames.
"""
import time
import tkinter as tk
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageTk

BG, CARD, INK, SOFT, ACCENT, HOVER, LINE, ON = "#FFF8F0", "#FFFFFF", "#23213B", "#6B6685", "#5A3FC0", "#EFE7FF", "#E8DFF3", "#2FB3A3"
_icons = {}

# which frame stands for each trick and each Together pick
PREVIEW = {"bounce": ("happy", "stretch", 0), "peekaboo": ("surprised", "idle", 0), "zoomies": ("happy", "walk1", 60), "nap": ("sleepy", "squash", 0),
           "sit": ("happy", "sit", 0), "lie": ("happy", "lie", 0), "spin": ("happy", "idle", 120), "wave": ("happy", "wave1", 0), "dab": ("happy", "dab", 0),
           "flex": ("happy", "flex", 0), "moonwalk": ("happy", "walk2", 300), "rot": ("sulky", "lie", 0), "spinout": ("surprised", "idle", 60),
           "faint": ("surprised", "lie", 0), "sideeye": ("sulky", "idle", 300),
           "study": ("happy", "study", 0), "work": ("happy", "work", 0), "game": ("happy", "game", 0), "eat": ("happy", "eat1", 0)}
ROOMS = (("living", "Living room"), ("bedroom", "Bedroom, for a nap"), ("kitchen", "Kitchen"))


def icon(ch, px):
    """One emoji as an image, see-through around it."""
    key = (ch, px)
    if key not in _icons:
        im = Image.new("RGBA", (px, px), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        try:
            f = ImageFont.truetype("C:/Windows/Fonts/seguiemj.ttf", round(px * 0.72))
            d.text((px * 0.5, px * 0.52), ch, font=f, embedded_color=True, anchor="mm")
        except Exception:
            pass
        if im.getbbox() is None:                                   # no glyph: a coloured dot with the first letter
            d.ellipse((px * 0.12, px * 0.12, px * 0.88, px * 0.88), fill=(90, 63, 192, 255))
        _icons[key] = im
    return _icons[key]


class Panel:
    def __init__(self, pet, x, y):
        import perchling as P
        self.P = P; self.pet = pet; self.S = P.SCALE
        old = getattr(pet, "panel", None)
        if old is not None:
            old.close()
        pet.panel = self
        self.win = w = tk.Toplevel(pet.root)
        w.overrideredirect(True); w.attributes("-topmost", True); w.configure(bg=LINE)
        self.frame = tk.Frame(w, bg=BG, padx=round(12 * self.S), pady=round(10 * self.S)); self.frame.pack(padx=1, pady=1)
        self.images = []                                           # keep PhotoImages alive
        self.at = (x, y)
        self.page = "home"
        self.build()
        w.bind("<Escape>", lambda e: self.close())
        w.bind("<FocusOut>", self.on_focus_out)
        w.after(60, lambda: (w.focus_force(), w.lift()))

    # ---- plumbing
    def on_focus_out(self, e):
        self.win.after(120, lambda: None if self.win.focus_displayof() else self.close())

    def close(self):
        if getattr(self.pet, "panel", None) is self:
            self.pet.panel = None
        try: self.win.destroy()
        except tk.TclError: pass

    def act(self, fn):
        """Run an action and close the card."""
        def go():
            self.close()
            fn()
        return go

    def place(self):
        self.win.update_idletasks()
        w, h = self.win.winfo_reqwidth(), self.win.winfo_reqheight()
        x, y = self.at; a = self.pet.area
        x = max(a[0], min(a[2] - w, x - w // 2)); y = max(a[1], min(a[3] - h, y - h - round(8 * self.S)))
        self.win.geometry(f"+{int(x)}+{int(y)}")

    def photo(self, im):
        ph = ImageTk.PhotoImage(im); self.images.append(ph); return ph

    def preview(self, key, px):
        mood, pose, yaw = PREVIEW.get(key, ("happy", "idle", 0))
        im = self.pet.frames.compose(mood, pose, yaw, self.pet.st["wearing"])
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255)); bg.alpha_composite(im)
        return self.photo(bg.crop((30, 20, 226, 236)).resize((px, px), Image.LANCZOS))

    # ---- pieces
    def clear(self):
        for c in self.frame.winfo_children(): c.destroy()
        self.images = []

    def header(self):
        pet = self.pet; S = self.S
        top = tk.Frame(self.frame, bg=BG); top.pack(fill="x", pady=(0, round(6 * S)))
        im = pet.frames.compose(pet.mood if pet.mood != "sulky" else "happy", "idle", 0, pet.st["wearing"])
        bg = Image.new("RGBA", im.size, (255, 248, 240, 255)); bg.alpha_composite(im)
        px = round(56 * S)
        tk.Label(top, image=self.photo(bg.crop((30, 20, 226, 236)).resize((px, px), Image.LANCZOS)), bg=BG, bd=0).pack(side="left", padx=(0, round(8 * S)))
        txt = tk.Frame(top, bg=BG); txt.pack(side="left", fill="x", expand=True)
        tk.Label(txt, text=pet.st["name"], bg=BG, fg=INK, font=("Segoe UI", 13, "bold"), anchor="w").pack(anchor="w")
        bits = [pet.sp.get("archetype", "")]
        hat = pet.st["wearing"].get("hat")
        if hat:
            name = next((it["name"] for sh in self.P.CLOSET["shelves"] for it in sh["items"] if it["id"] == hat), None)
            if hat.startswith("my:"):
                h = pet.frames.hat(hat[3:]); name = h["name"] if h else None
            if name: bits.append(f"wearing the {name.lower()}")
        egg = pet.egg()
        if egg and egg.get("by") == pet.pid:
            bits.append(f"an egg, {max(1, round(self.P.E.hours_left(egg)))} h to go")
        else:
            bits.append(f"egg in {max(0, self.P.E.GOOD_DAYS_FOR_EGG - pet.good_days())} good days")
        if pet.mood == "sulky": bits.append("sulking")
        tk.Label(txt, text=" · ".join(b for b in bits if b), bg=BG, fg=SOFT, font=("Segoe UI", 9), anchor="w", justify="left", wraplength=round(250 * S)).pack(anchor="w")
        tk.Label(top, text="✕", bg=BG, fg=SOFT, font=("Segoe UI", 11), cursor="hand2").pack(side="right", anchor="n")
        top.winfo_children()[-1].bind("<Button-1>", lambda e: self.close())

    def caption(self, text):
        tk.Label(self.frame, text=text.upper(), bg=BG, fg=SOFT, font=("Segoe UI", 8, "bold"), anchor="w").pack(anchor="w", pady=(round(6 * self.S), 2))

    def grid(self, tiles, cols=5):
        """tiles: [(image or emoji, label, action, more?)]. Big square tiles, icon over text."""
        S = self.S; g = tk.Frame(self.frame, bg=BG); g.pack(anchor="w")
        tw = round(78 * S)
        for i, (ic, label, action, *rest) in enumerate(tiles):
            more = bool(rest and rest[0]); on = rest[1] if len(rest) > 1 else None
            t = tk.Frame(g, bg=CARD, width=tw, height=round(64 * S), highlightthickness=1, highlightbackground=LINE, cursor="hand2")
            t.grid(row=i // cols, column=i % cols, padx=2, pady=2); t.pack_propagate(False)
            img = ic if not isinstance(ic, str) else self.photo(icon(ic, round(26 * S)))
            tk.Label(t, image=img, bg=CARD, bd=0).pack(pady=(round(5 * S), 0))
            tk.Label(t, text=label + (" ›" if more else "") + ("" if on is None else (": on" if on else ": off")), bg=CARD, fg=INK if on is None or on else SOFT,
                     font=("Segoe UI", 8), wraplength=tw - 6).pack()
            if on is not None:
                tk.Frame(t, bg=ON if on else LINE, height=round(3 * S)).pack(side="bottom", fill="x")
            for wdg in (t, *t.winfo_children()):
                wdg.bind("<Enter>", lambda e, t=t: self.paint(t, HOVER)); wdg.bind("<Leave>", lambda e, t=t: self.paint(t, CARD))
                wdg.bind("<Button-1>", lambda e, a=action: a())

    def paint(self, t, colour):
        t.configure(bg=colour)
        for c in t.winfo_children():
            if isinstance(c, tk.Label): c.configure(bg=colour)

    def back(self, title):
        row = tk.Frame(self.frame, bg=BG); row.pack(fill="x", pady=(0, round(4 * self.S)))
        b = tk.Label(row, text="‹ Back", bg=BG, fg=ACCENT, font=("Segoe UI", 10, "bold"), cursor="hand2"); b.pack(side="left")
        b.bind("<Button-1>", lambda e: self.show("home"))
        tk.Label(row, text=title, bg=BG, fg=INK, font=("Segoe UI", 11, "bold")).pack(side="left", padx=(10, 0))

    # ---- pages
    def show(self, page):
        self.page = page; self.clear(); self.build(); self.place()

    def build(self):
        pet = self.pet; P = self.P
        getattr(self, "page_" + self.page)()
        if self.page == "home":                                   # the footer: version, update, quit
            foot = tk.Frame(self.frame, bg=BG); foot.pack(fill="x", pady=(round(6 * self.S), 0))
            tk.Label(foot, text=f"Perchlings {P.VERSION}", bg=BG, fg=SOFT, font=("Segoe UI", 8)).pack(side="left")
            q = tk.Label(foot, text="Quit", bg=BG, fg=ACCENT, font=("Segoe UI", 9, "bold"), cursor="hand2"); q.pack(side="right")
            q.bind("<Button-1>", lambda e: self.act(pet.quit)())
            if pet.update_to:
                u = tk.Label(foot, text=f"Update to {pet.update_to.lstrip('v')}", bg=BG, fg=ACCENT, font=("Segoe UI", 9, "bold"), cursor="hand2"); u.pack(side="right", padx=(0, 14))
                u.bind("<Button-1>", lambda e: self.act(pet.do_update)())
        self.place()

    def page_home(self):
        pet = self.pet; P = self.P; H = P.H
        self.header()
        picked = set(pet.st["picks"])
        tricks = [t for t in pet.sp["catalog"]["tricks"] if t["id"] in picked]
        together = [t for t in pet.sp["catalog"].get("together", []) if t["id"] in picked]
        here = H.others(pet.pid, pet.area)
        self.caption("Do")
        do = [("✋", "Tickle", self.act(pet.tickle)),
              (self.preview(tricks[0]["id"], round(28 * self.S)) if tricks else "⭐", "Tricks", lambda: self.show("tricks"), True),
              ("💻", "Together", lambda: self.show("together"), True),
              ("🤝", "Play with the others" if here else "No one else is out", (lambda: self.show("play")) if here else (lambda: None), bool(here)),
              ("📁", "Hide", self.act(pet.hide))]
        if pet.house_here():
            do.append(("🏠", "Go inside", lambda: self.show("inside"), True))
        self.grid(do)
        self.caption("Say and share")
        self.grid([("📓", "Notebook", self.act(pet.notebook_dialog)), ("⏰", "Remind me", self.act(pet.remind_dialog)), ("🪧", "Hold a sign", self.act(pet.sign_dialog)),
                   ("📸", "Photo", self.act(pet.take_photo)), ("🎬", "Clip 8 seconds", self.act(pet.take_clip))])
        self.caption("Wear")
        self.grid([("🧢", "Closet", self.act(pet.closet_dialog)), ("🎨", "Hat maker", self.act(pet.hat_maker)), ("🛍️", "Shop", self.act(pet.shop_dialog)), ("🔑", "Enter a code", self.act(pet.code_dialog))])
        self.caption("Household and settings")
        chaos = pet.st.get("chaos", "cheeky")
        self.grid([("🐾", "Pets", lambda: self.show("pets"), True), ("🎥", "Streamer stage", self.act(pet.open_stage)),
                   ({"sweet": "😇", "cheeky": "😏", "menace": "😈"}[chaos], f"Attitude: {chaos}", lambda: self.show("attitude"), True),
                   ("🎵", "Music", self.toggle("music"), False, pet.st.get("music", True)),
                   ("👀", "Reacts", self.toggle("reacts"), False, pet.st.get("reacts", True)),
                   ("🌅", "With Windows", self.toggle_autostart, False, pet.autostart.get()),
                   ("✏️", "Rename", self.act(pet.rename)), ("🎂", "Your birthday", self.act(pet.set_birthday)), ("🎯", "Pick five", self.act(pet.pick_dialog)),
                   ("🚪", f"Let {pet.st['name']} go", self.act(pet.let_go))])

    def toggle(self, key):
        def go():
            self.pet.set_flag(key, not self.pet.st.get(key, True))
            var = getattr(self.pet, key + "_var", None)
            if var is not None: var.set(self.pet.st[key])
            self.show("home")
        return go

    def toggle_autostart(self):
        self.pet.autostart.set(not self.pet.autostart.get()); self.pet.toggle_autostart(); self.show("home")

    def page_tricks(self):
        pet = self.pet; picked = set(pet.st["picks"])
        self.back("Tricks")
        tiles = [(self.preview(t["id"], round(40 * self.S)), t["name"], self.act(lambda tid=t["id"]: pet.do_trick(tid))) for t in pet.sp["catalog"]["tricks"] if t["id"] in picked]
        tiles.append(("🎯", "Pick five", self.act(pet.pick_dialog)))
        self.grid(tiles)
        tk.Label(self.frame, text="Its own move comes up on its own too. Pick five changes the list.", bg=BG, fg=SOFT, font=("Segoe UI", 8)).pack(anchor="w", pady=(4, 0))

    def page_together(self):
        pet = self.pet; picked = set(pet.st["picks"])
        self.back("Together")
        tiles = [(self.preview(t["id"], round(40 * self.S)), t["name"], self.act(lambda tid=t["id"]: pet.do_together(tid))) for t in pet.sp["catalog"].get("together", []) if t["id"] in picked]
        if not tiles:
            tk.Label(self.frame, text="Study, work, game or eat with you, until you click it. Pick one in Pick five.", bg=BG, fg=SOFT, font=("Segoe UI", 9), wraplength=round(300 * self.S), justify="left").pack(anchor="w")
            tiles = [("🎯", "Pick five", self.act(pet.pick_dialog))]
        else:
            tk.Label(self.frame, text="It keeps you company until you click it.", bg=BG, fg=SOFT, font=("Segoe UI", 8)).pack(anchor="w", pady=(0, 4))
        self.grid(tiles)

    def page_play(self):
        pet = self.pet; H = self.P.H
        self.back("Play with the others")
        here = H.others(pet.pid, pet.area)
        kinds = list(H.KINDS) + (["parade"] if len(here) >= 2 else [])
        em = {"dance": "💃", "chase": "🏃", "wrestle": "🤼", "race": "🏁", "nap": "😴", "copycat": "🪞", "hatswap": "🎩", "peekaboo": "🙈", "gossip": "💬", "parade": "🎺"}
        self.grid([(em.get(k, "⭐"), H.NAMES[k], self.act(lambda k=k: pet.play_now(k))) for k in kinds])
        who = ", ".join(o.get("name", o["pid"]) for o in here)
        tk.Label(self.frame, text=f"Out right now: {who}. Anyone in the house comes out for it.", bg=BG, fg=SOFT, font=("Segoe UI", 8), wraplength=round(300 * self.S), justify="left").pack(anchor="w", pady=(4, 0))

    def page_inside(self):
        pet = self.pet
        self.back("Go inside")
        em = {"living": "🛋️", "bedroom": "🛏️", "kitchen": "🍳"}
        self.grid([(em[r], label, self.act(lambda r=r: pet.go_inside(r, 15 * 60) or pet.say("Not right now."))) for r, label in ROOMS])

    def page_attitude(self):
        pet = self.pet; cur = pet.st.get("chaos", "cheeky")
        self.back("Attitude")
        tiles = [("😇", "Sweet", "no mischief at all"), ("😏", "Cheeky", "muddy footprints, notes, a look now and then"),
                 ("😈", "Menace", "steals your cursor, spins out, faints, rots in your way")]
        self.grid([(ic, name, self.act(lambda lv=name.lower(): pet.set_chaos(lv)), False, cur == name.lower()) for ic, name, _ in tiles], cols=3)
        for ic, name, what in tiles:
            tk.Label(self.frame, text=f"{name}: {what}.", bg=BG, fg=SOFT, font=("Segoe UI", 8)).pack(anchor="w")

    def page_pets(self):
        pet = self.pet; P = self.P
        self.back("Pets")
        tiles = []
        for pid in P.adopted_ids():
            pst = P.pet_state(pid)
            try:
                im = P.Frames(pid, 128, variant=pst.get("variant")).compose("happy", "idle", 0, pst.get("wearing", {}))
                bg = Image.new("RGBA", im.size, (255, 255, 255, 255)); bg.alpha_composite(im)
                ic = self.photo(bg.crop((30, 20, 226, 236)).resize((round(34 * self.S),) * 2, Image.LANCZOS))
            except Exception:
                ic = "🐾"
            if pid == pet.pid:
                tiles.append((ic, f"{pet.st['name']} (me)", lambda: None, False, True))
            else:
                out = not pst.get("home", False)
                tiles.append((ic, f"{pst.get('name', pid)}: {'out' if out else 'home'}", self.act(lambda pid=pid, out=out: pet.toggle_pet(pid, out)), False, out))
        tiles.append(("➕", "Adopt another", self.act(pet.adopt_another)))
        self.grid(tiles)
        tk.Label(self.frame, text="Click a pet to send it home or bring it out.", bg=BG, fg=SOFT, font=("Segoe UI", 8)).pack(anchor="w", pady=(4, 0))


def tile_grid(parent, S, tiles, cols=5, keep=None):
    """A grid of tiles for a dialog: tiles are (image or emoji, label, action, selected?, note?).
    keep: a list that holds the PhotoImages alive (pass the window's own list)."""
    keep = keep if keep is not None else []
    g = tk.Frame(parent, bg=BG); g.pack(anchor="w")
    tw = round(84 * S)
    for i, (ic, label, action, *rest) in enumerate(tiles):
        selected = bool(rest and rest[0]); note = rest[1] if len(rest) > 1 else None
        t = tk.Frame(g, bg=CARD, width=tw, height=round((78 if note else 68) * S), highlightthickness=2 if selected else 1,
                     highlightbackground=ACCENT if selected else LINE, cursor="hand2" if action else "arrow")
        t.grid(row=i // cols, column=i % cols, padx=2, pady=2); t.pack_propagate(False)
        if isinstance(ic, str):
            img = ImageTk.PhotoImage(icon(ic, round(28 * S))); keep.append(img)
        else:
            img = ic
        tk.Label(t, image=img, bg=CARD, bd=0).pack(pady=(round(4 * S), 0))
        tk.Label(t, text=label, bg=CARD, fg=INK if action else SOFT, font=("Segoe UI", 8, "bold" if selected else "normal"), wraplength=tw - 6).pack()
        if note:
            tk.Label(t, text=note, bg=CARD, fg=ACCENT if action else SOFT, font=("Segoe UI", 7)).pack()
        if action:
            for wdg in (t, *t.winfo_children()):
                wdg.bind("<Enter>", lambda e, t=t: _paint(t, HOVER)); wdg.bind("<Leave>", lambda e, t=t: _paint(t, CARD))
                wdg.bind("<Button-1>", lambda e, a=action: a())
    return g


def _paint(t, colour):
    t.configure(bg=colour)
    for c in t.winfo_children():
        if isinstance(c, tk.Label): c.configure(bg=colour)


def pet_still(frames, mood, pose, yaw, wearing, px, keep, bg=(255, 255, 255, 255)):
    """The pet as a small picture, for tiles."""
    im = frames.compose(mood, pose, yaw, wearing)
    b = Image.new("RGBA", im.size, bg); b.alpha_composite(im)
    ph = ImageTk.PhotoImage(b.crop((30, 20, 226, 236)).resize((px, px), Image.LANCZOS)); keep.append(ph); return ph
