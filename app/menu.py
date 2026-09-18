"""The pet's panel: what the right click opens. A card with the pet's portrait and name, then tiles in groups
(Do; Say and share; Wear and own; Household; Settings), each with an icon, and picture previews for the tricks and
the Together picks. Everything the pet can do is on this card: the house too (bring it out, open it, decorate it,
put it away), breaks, naps, a dance, a party, the egg. Sub-pages open in the same card with a Back button.
It closes when you click anywhere else.

Icons come from the Windows emoji font, drawn once per size and cached. Previews are the pet's own frames.
"""
import time
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageTk

BG, CARD, INK, SOFT, ACCENT, HOVER, LINE, ON = "#FFF8F0", "#FFFFFF", "#23213B", "#6B6685", "#5A3FC0", "#EFE7FF", "#E8DFF3", "#2FB3A3"
_icons = {}
_house_thumbs = {}

# which frame stands for each trick and each Together pick
PREVIEW = {"bounce": ("happy", "stretch", 0), "peekaboo": ("surprised", "idle", 0), "zoomies": ("happy", "walk1", 60), "nap": ("sleepy", "squash", 0),
           "sit": ("happy", "sit", 0), "lie": ("happy", "lie", 0), "spin": ("happy", "idle", 120), "wave": ("happy", "wave1", 0), "dab": ("happy", "dab", 0),
           "flex": ("happy", "flex", 0), "moonwalk": ("happy", "walk2", 300), "rot": ("sulky", "lie", 0), "spinout": ("surprised", "idle", 60),
           "faint": ("surprised", "lie", 0), "sideeye": ("sulky", "idle", 300),
           "study": ("happy", "study", 0), "work": ("happy", "work", 0), "game": ("happy", "game", 0), "eat": ("happy", "eat1", 0),
           "backflip": ("happy", "idle", 180), "sneak": ("surprised", "squash", 60), "panic": ("surprised", "walk1", 300), "meditate": ("sleepy", "sit", 0),
           "loaf": ("happy", "squash", 0), "wiggle": ("happy", "squash", 60), "bow": ("happy", "squash", 0), "rockout": ("happy", "game", 0),
           "stare": ("happy", "idle", 0), "jumpscare": ("surprised", "stretch", 0), "yoga": ("sleepy", "stretch", 0), "shiver": ("surprised", "idle", 0),
           "sneeze": ("surprised", "squash", 0), "karate": ("happy", "dab", 0), "robot": ("happy", "idle", 60), "hype": ("happy", "wave1", 0),
           "slowclap": ("happy", "wave2", 0), "kiss": ("happy", "wave2", 0), "parkour": ("happy", "stretch", 60), "chase": ("happy", "walk1", 60),
           "snack": ("happy", "eat2", 0), "homework": ("sleepy", "study", 0), "scream": ("surprised", "stretch", 0), "statue": ("happy", "stretch", 0)}
ROOMS = (("living", "Living room"), ("bedroom", "Bedroom, for a nap"), ("kitchen", "Kitchen"))
ROOM_NAMES = {"living": "living room", "kitchen": "kitchen", "bedroom": "bedroom", "bathroom": "bathroom"}


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


def house_thumb(root, style, px):
    """The closed house in a style, small, for tiles."""
    key = (style, px)
    if key not in _house_thumbs:
        name = "closed.png" if style == "cozy" else f"closed-{style}.png"
        try:
            im = Image.open(root / "assets" / "house" / name).convert("RGBA")
            bb = im.getbbox() or (0, 0, im.width, im.height); im = im.crop(bb); im.thumbnail((px, px), Image.LANCZOS)
            out = Image.new("RGBA", (px, px), (0, 0, 0, 0)); out.alpha_composite(im, ((px - im.width) // 2, (px - im.height) // 2))
        except OSError:
            out = icon("\U0001F3E0", px)
        _house_thumbs[key] = out
    return _house_thumbs[key]


TIPS = {   # one plain line per tile, shown on hover, so nothing on the menu needs guessing
    "Tickle": "A tickle. Same as clicking the pet.",
    "Tricks": "Its tricks. Pick one and it does it right now, whatever it was doing.",
    "Keep you company": "It sits next to you with a laptop, headphones or a snack until you click it.",
    "Play with the others": "A chase, a race, a wrestle, a hat swap, a parade or a gossip with the other pets out.",
    "No one else is out": "Bring another pet out and they can play together.",
    "Dance": "It dances for half a minute, music or not. With music on, they dance on their own.",
    "Stop dancing": "It sits the next couple of minutes out, even with music on.",
    "Hide": "It turns into a plain folder until you pick Come out.",
    "Come out": "The folder turns back into your pet.",
    "Bathroom break": "A bathroom or shower break: in the house if it's out, else behind a curtain here.",
    "Nap": "It sleeps, in the bedroom if the house is out, else right here, until you pick Wake up. Nothing else wakes it.",
    "Wake up": "Ends the nap. It gets up with a stretch.",
    "Cursor tricks": "What your mouse can do to it: spin it dizzy, lift it and it pulls out a parachute, drop it on the house.",
    "Go inside": "It walks into a room of the house for a while.",
    "Notebook": "Tell it things. It remembers, brings them up later, and gossips about them.",
    "Remind me": "A day, a time, a few words. It hops up and tells you when it's time.",
    "Hold a sign": "Type a few words and it holds them up on a sign for half a minute.",
    "Photo": "A framed photo of your pet with stickers, saved to Pictures.",
    "Clip 8 seconds": "Records eight seconds of your pet as a GIF you can post.",
    "Throw a party": "Confetti and party hats for every pet, right now.",
    "Closet": "Everything it can wear, shown on your pet before you pick.",
    "Hat maker": "Make your own hat: a shape, two colors, a sticker, a name, and a code to share.",
    "Shop": "Outfits, effects, furniture and tricks, $0.99 each. Bought once, used by every pet here.",
    "Enter a code": "The code from your email: a pet, an item or a friend's hat.",
    "Choose tricks": "Which of its tricks and habits are switched on. Five come free.",
    "Pets": "Everyone in the household: bring a pet out, send it home, or adopt another.",
    "Egg": "How close it is to finding an egg, and what's in one.",
    "Streamer stage": "A green-screen window with every pet on it, for streams.",
    "Bring out the house": "A little house on the taskbar: naps, meals, bathroom breaks, four rooms to decorate.",
    "The house": "Open it, decorate it, send the pets in, or put it away.",
    "House on another screen": "Bring the house over to this screen.",
    "Music": "Dances when it hears music. It only hears how loud your speakers are.",
    "Reacts": "Cheers when you type fast, notices when you leave and come back, comments on undo and clicks.",
    "With Windows": "Starts with Windows so it's on the taskbar when you log in.",
    "Rename": "Give it a new name.",
    "Your birthday": "Tell it your birthday and there's confetti on the day.",
    "Take the hats off": "",
}


PLAY_TIPS = {"dance": "Everyone out dances together.", "chase": "One runs, the other chases, then they swap.", "wrestle": "A glare, a charge, and one goes flying. Three rounds.",
             "race": "A dash across the taskbar. Someone wins.", "nap": "They doze off next to each other.", "copycat": "One does a move, the other copies it.",
             "hatswap": "They trade hats.", "peekaboo": "They take turns ducking down and popping up.", "gossip": "They sit down and talk about you.", "parade": "Everyone marches across the screen in a line, there and back."}

HOUSE_TIPS = {"Open the house": "Opens the front so you can see the rooms and who's in them.", "Close the house": "Closes the front. The pets inside stay inside.",
              "Decorate": "Furniture and wall colors for each room.", "Loft style": "Switch the house to the loft look.", "Cozy style": "Switch the house to the cozy look.",
              "Everyone out": "Calls every pet out of the house.", "Put it away": "Takes the house off the taskbar until you bring it out again."}

TIP_DELAY = 220   # ms the pointer rests on a tile before its tip shows: long enough not to flash while crossing the card


class Tip:
    """One tooltip window per toplevel, reused: shown after a short rest on a widget or anything inside it, hidden only
    once the pointer has left the whole widget. Bindings on the widget alone are not enough: the labels inside cover
    it, and Tk fires Leave on the widget the moment the pointer crosses onto a child, so a hand gliding across a tile
    never saw its tip (0.28.3). Reusing the window also spares the panel a new toplevel on every crossing."""
    def __init__(self, top):
        self.top = top; self.win = None; self.label = None; self.owner = None; self.timer = None
        top.bind("<Destroy>", lambda e: self.hide() if e.widget is top else None, add="+")   # no timer outlives the card

    def _make(self):
        w = tk.Toplevel(self.top); w.withdraw(); w.overrideredirect(True); w.attributes("-topmost", True)
        self.label = tk.Label(w, text="", bg=INK, fg="#FFFFFF", font=("Segoe UI", 8), padx=6, pady=2); self.label.pack()
        self.win = w

    def show(self, widget, text):
        try:
            if self.win is None or not self.win.winfo_exists(): self._make()
            self.label.configure(text=text); self.win.update_idletasks()
            x, y = widget.winfo_rootx(), widget.winfo_rooty() - self.win.winfo_reqheight() - 4
            if y < widget.winfo_vrooty(): y = widget.winfo_rooty() + widget.winfo_height() + 4      # no room above: below
            sw = widget.winfo_screenwidth()
            x = max(0, min(x, sw - self.win.winfo_reqwidth()))
            self.win.geometry(f"+{x}+{y}"); self.win.deiconify(); self.win.lift(); self.owner = widget
        except tk.TclError:
            self.win = None

    def hide(self):
        if self.timer is not None:
            try: self.top.after_cancel(self.timer)
            except tk.TclError: pass
            self.timer = None
        self.owner = None
        if self.win is not None:
            try: self.win.withdraw()
            except tk.TclError: self.win = None

    def attach(self, widget, text):
        def inside(w):
            while w is not None:
                if w is widget: return True
                w = getattr(w, "master", None)
            return False
        def enter(e):
            if self.owner is widget: return                                     # crossing between the tile's own parts
            self.hide()
            self.timer = self.top.after(TIP_DELAY, lambda: self.show(widget, text))
        def leave(e):
            try: under = widget.winfo_containing(e.x_root, e.y_root)
            except tk.TclError: under = None
            if not inside(under): self.hide()
        widget.tip_text = text                                                  # what the harness reads back
        for w in (widget, *widget.winfo_children()):
            w.bind("<Enter>", enter, add="+"); w.bind("<Leave>", leave, add="+"); w.bind("<Button-1>", lambda e: self.hide(), add="+")


def tip(widget, text):
    """A one-line tip that shows when the pointer rests on the widget (a tile, a chip) or anything inside it."""
    top = widget.winfo_toplevel()
    t = getattr(top, "_tip", None)
    if t is None:
        t = top._tip = Tip(top)
    t.attach(widget, text)


class Panel:
    COLS = 7

    def __init__(self, pet, x, y):
        import perchling as P
        self.P = P; self.pet = pet; self.S = P.SCALE
        old = getattr(pet, "panel", None)
        if old is not None:
            old.close()
        pet.panel = self
        self.win = w = tk.Toplevel(pet.root)
        w.overrideredirect(True); w.attributes("-topmost", True); w.configure(bg=LINE)
        # the card sits in a canvas, so on a short screen it scrolls with the wheel instead of running off the bottom
        self.canvas = tk.Canvas(w, bg=BG, bd=0, highlightthickness=0); self.canvas.pack(padx=1, pady=1)
        self.frame = tk.Frame(self.canvas, bg=BG, padx=round(12 * self.S), pady=round(10 * self.S))
        self.canvas.create_window((0, 0), window=self.frame, anchor="nw")
        self.scrolls = False
        self.images = []                                           # keep PhotoImages alive
        self.at = (x, y)
        self.page = "home"
        self.build()
        w.bind("<Escape>", lambda e: self.close())
        w.bind("<FocusOut>", self.on_focus_out)
        w.bind("<MouseWheel>", self.on_wheel)                              # on this window only: a global binding would wipe the shop's on close
        self.timers = [w.after(60, lambda: (w.focus_force(), w.lift()))]   # cancelled on close: a timer that outlives its window
                                                                            # fires into whatever Tk command has reused its name

    # ---- plumbing
    def on_focus_out(self, e):
        self.timers.append(self.win.after(120, lambda: None if self.win.focus_displayof() else self.close()))

    def on_wheel(self, e):
        if self.scrolls:
            try: self.canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")
            except tk.TclError: pass

    def close(self):
        if getattr(self.pet, "panel", None) is self:
            self.pet.panel = None
        for t in self.timers:
            try: self.win.after_cancel(t)
            except tk.TclError: pass
        self.timers = []
        try: self.win.destroy()
        except tk.TclError: pass

    def act(self, fn):
        """Run an action and close the card."""
        def go():
            self.close()
            fn()
        return go

    def place(self):
        self.frame.update_idletasks()
        fw, fh = self.frame.winfo_reqwidth(), self.frame.winfo_reqheight()
        a = self.pet.area
        maxh = a[3] - a[1] - round(12 * self.S)
        h = min(fh, maxh); self.scrolls = fh > maxh
        self.canvas.configure(width=fw, height=h, scrollregion=(0, 0, fw, fh), yscrollincrement=round(40 * self.S))
        self.canvas.yview_moveto(0)
        self.win.update_idletasks()
        w, hh = self.win.winfo_reqwidth(), self.win.winfo_reqheight()
        x, y = self.at
        x = max(a[0], min(a[2] - w, x - w // 2)); y = max(a[1], min(a[3] - hh, y - hh - round(8 * self.S)))
        self.win.geometry(f"+{int(x)}+{int(y)}")

    def photo(self, im):
        ph = ImageTk.PhotoImage(im); self.images.append(ph); return ph

    def preview(self, key, px):
        mood, pose, yaw = PREVIEW.get(key, ("happy", "idle", 0))
        im = self.pet.frames.compose(mood, pose, yaw, self.pet.st["wearing"])
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255)); bg.alpha_composite(im)
        return self.photo(bg.crop((30, 20, 226, 236)).resize((px, px), Image.LANCZOS))

    def portrait(self, pid, pst, px):
        """A small picture of another pet in the household, from its own sheets."""
        P = self.P
        try:
            im = P.Frames(pid, 128, variant=pst.get("variant")).compose("happy", "idle", 0, pst.get("wearing", {}))
            bg = Image.new("RGBA", im.size, (255, 255, 255, 255)); bg.alpha_composite(im)
            return self.photo(bg.crop((30, 20, 226, 236)).resize((px, px), Image.LANCZOS))
        except Exception:
            return "\U0001F43E"

    # ---- pieces
    def clear(self):
        for c in self.frame.winfo_children(): c.destroy()
        self.images = []

    def header(self):
        pet = self.pet; S = self.S
        top = tk.Frame(self.frame, bg=BG); top.pack(fill="x", pady=(0, round(4 * S)))
        im = pet.frames.compose(pet.mood if pet.mood != "sulky" else "happy", "idle", 0, pet.st["wearing"])
        bg = Image.new("RGBA", im.size, (255, 248, 240, 255)); bg.alpha_composite(im)
        px = round(54 * S)
        tk.Label(top, image=self.photo(bg.crop((30, 20, 226, 236)).resize((px, px), Image.LANCZOS)), bg=BG, bd=0).pack(side="left", padx=(0, round(8 * S)))
        txt = tk.Frame(top, bg=BG); txt.pack(side="left", fill="x", expand=True)
        tk.Label(txt, text=pet.st["name"], bg=BG, fg=INK, font=("Segoe UI", 13, "bold"), anchor="w").pack(anchor="w")
        bits = [("mini " if pet.st.get("hatched") else "") + pet.sp.get("archetype", "")]
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
        if pet.state == "dance": bits.append("dancing")
        if not pet.flag("reacts"): bits.append("reactions off")
        if not pet.flag("music"): bits.append("music off")
        tk.Label(txt, text=" \u00b7 ".join(b for b in bits if b), bg=BG, fg=SOFT, font=("Segoe UI", 9), anchor="w", justify="left", wraplength=round(330 * S)).pack(anchor="w")
        xb = tk.Label(top, text="\u2715", bg=BG, fg=SOFT, font=("Segoe UI", 11), cursor="hand2"); xb.pack(side="right", anchor="n")
        xb.bind("<Button-1>", lambda e: self.close())

    def caption(self, text):
        tk.Label(self.frame, text=text.upper(), bg=BG, fg=SOFT, font=("Segoe UI", 8, "bold"), anchor="w").pack(anchor="w", pady=(round(4 * self.S), 1))

    def note(self, text, pady=(4, 0)):
        tk.Label(self.frame, text=text, bg=BG, fg=SOFT, font=("Segoe UI", 8), wraplength=round(440 * self.S), justify="left").pack(anchor="w", pady=pady)

    def grid(self, tiles, cols=None, tips=None):
        """tiles: [(image or emoji, label, action, more?, on?)]. Square tiles, icon over text. tips: {label: one line}
        for this page's tiles, looked up before the shared TIPS."""
        S = self.S; g = tk.Frame(self.frame, bg=BG); g.pack(anchor="w"); tips = tips or {}
        cols = cols or self.COLS
        tw = round(74 * S)
        def text_of(label, more, on, word):
            return label + (" ›" if more else "") + ("" if on is None else f": {word or ('on' if on else 'off')}")
        parts = [(ic, label, action, bool(rest and rest[0]), rest[1] if len(rest) > 1 else None, rest[2] if len(rest) > 2 else None)
                 for ic, label, action, *rest in tiles]
        f8 = tkfont.Font(family="Segoe UI", size=8)
        two = any(f8.measure(text_of(label, more, on, word)) > tw - 6 for _, label, _, more, on, word in parts)
        th = round((70 if two else 58) * S)                 # a long label (a hatchling's name) gets a second line, not cut off
        for i, (ic, label, action, more, on, word) in enumerate(parts):
            t = tk.Frame(g, bg=CARD, width=tw, height=th, highlightthickness=1, highlightbackground=LINE, cursor="hand2")
            t.grid(row=i // cols, column=i % cols, padx=2, pady=2); t.pack_propagate(False)
            img = ic if not isinstance(ic, str) else self.photo(icon(ic, round(23 * S)))
            tk.Label(t, image=img, bg=CARD, bd=0).pack(pady=(round(3 * S), 0))
            tk.Label(t, text=text_of(label, more, on, word), bg=CARD, fg=INK if on is None or on else SOFT,
                     font=("Segoe UI", 8), wraplength=tw - 6).pack()
            if on is not None:
                tk.Frame(t, bg=ON if on else LINE, height=round(3 * S)).pack(side="bottom", fill="x")
            for wdg in (t, *t.winfo_children()):
                wdg.bind("<Enter>", lambda e, t=t: self.paint(t, HOVER)); wdg.bind("<Leave>", lambda e, t=t: self.paint(t, CARD))
                wdg.bind("<Button-1>", lambda e, a=action: a())
            key = label.split(":")[0].strip(); head = key.split(",")[0].strip()          # "Music, hears sound" is still Music
            text = tips.get(label) or tips.get(key) or TIPS.get(label) or TIPS.get(key) or TIPS.get(head) or {"Size": "Small, medium or large.", "Attitude": "Sweet behaves. Cheeky leaves footprints and notes. Menace steals your cursor."}.get(key)
            if label.startswith("Let ") and label.endswith(" go"):
                text = "Gives the pet back for good. It forgets everything."
            if text:
                tip(t, text)

    def paint(self, t, colour):
        t.configure(bg=colour)
        for c in t.winfo_children():
            if isinstance(c, tk.Label): c.configure(bg=colour)

    def back(self, title):
        row = tk.Frame(self.frame, bg=BG); row.pack(fill="x", pady=(0, round(4 * self.S)))
        b = tk.Label(row, text="\u2039 Back", bg=BG, fg=ACCENT, font=("Segoe UI", 10, "bold"), cursor="hand2"); b.pack(side="left")
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
        here = H.others(pet.pid, pet.area)
        house = P.house_info(); house_here = pet.house_here()
        dancing = pet.state == "dance" or time.time() < pet.dance_force_until
        self.caption("Do")
        do = [("\u270b", "Tickle", self.act(pet.tickle)),
              (self.preview(tricks[0]["id"], round(28 * self.S)) if tricks else "\u2b50", "Tricks", lambda: self.show("tricks"), True),
              ("\U0001F4BB", "Keep you company", lambda: self.show("together"), True),
              ("\U0001F91D", "Play with the others" if here else "No one else is out", (lambda: self.show("play")) if here else (lambda: None), bool(here)),
              ("\U0001F57A", "Stop dancing" if dancing else "Dance", self.act(pet.stop_dancing if dancing else pet.dance_now)),
              ("\U0001F4C2", "Come out", self.act(pet.unhide)) if pet.state == "hide" else ("\U0001F4C1", "Hide", self.act(pet.hide)),
              ("\U0001F6BF", "Bathroom break", lambda: self.show("break"), True),
              ("\u2600\ufe0f", "Wake up", self.act(pet.wake_up)) if pet.napping() else ("\U0001F634", "Nap", self.act(pet.nap_now)),
              ("\U0001F5B1\ufe0f", "Cursor tricks", lambda: self.show("cursor"), True)]
        if house_here:
            do.append(("\U0001F3E0", "Go inside", lambda: self.show("inside"), True))
        self.grid(do)
        self.caption("Say and share")
        self.grid([("\U0001F4D3", "Notebook", self.act(pet.notebook_dialog)), ("\u23f0", "Remind me", self.act(pet.remind_dialog)), ("\U0001FAA7", "Hold a sign", self.act(pet.sign_dialog)),
                   ("\U0001F4F8", "Photo", self.act(pet.take_photo)), ("\U0001F3AC", "Clip 8 seconds", self.act(pet.take_clip)), ("\U0001F389", "Throw a party", self.act(pet.party_now))])
        self.caption("Wear and own")
        self.grid([("\U0001F9E2", "Closet", self.act(pet.closet_dialog)), ("\U0001F3A8", "Hat maker", self.act(pet.hat_maker)), ("\U0001F6CD\ufe0f", "Shop", self.act(pet.shop_dialog)),
                   ("\U0001F511", "Enter a code", self.act(pet.code_dialog)), ("\U0001F3AF", "Choose tricks", self.act(pet.pick_dialog))])
        self.caption("Household")
        if house_here:
            house_label = "The house"
        elif house:
            house_label = "House on another screen"
        else:
            house_label = "Bring out the house"
        hph = self.photo(house_thumb(P.ROOT, (house or {}).get("style", "cozy"), round(26 * self.S)))
        self.grid([("\U0001F43E", "Pets", lambda: self.show("pets"), True), (hph, house_label, lambda: self.show("house"), True),
                   ("\U0001F95A", "Egg", lambda: self.show("egg"), True), ("\U0001F3A5", "Streamer stage", self.act(pet.open_stage))])
        self.caption("Settings")
        chaos = pet.st.get("chaos", "cheeky")
        hearing = getattr(pet.ear, "hearing", False)
        self.grid([({"sweet": "\U0001F607", "cheeky": "\U0001F60F", "menace": "\U0001F608"}[chaos], f"Attitude: {chaos}", lambda: self.show("attitude"), True),
                   ("\U0001F3B5", "Music" + (", hears sound" if hearing else ""), self.toggle("music"), False, pet.flag("music")),
                   ("\U0001F440", "Reacts", self.toggle("reacts"), False, pet.flag("reacts")),
                   ("\U0001F305", "With Windows", self.toggle_autostart, False, pet.autostart.get()),
                   ("\U0001F4CF", f"Size: {pet.st.get('size', 'medium')}", self.cycle_size),
                   ("\u270f\ufe0f", "Rename", self.act(pet.rename)), ("\U0001F382", "Your birthday", self.act(pet.set_birthday)),
                   ("\U0001F6AA", f"Let {pet.st['name']} go", self.act(pet.let_go))])

    def toggle(self, key):
        def go():
            self.pet.set_flag(key, not self.pet.flag(key))
            var = getattr(self.pet, key + "_var", None)
            if var is not None: var.set(self.pet.st[key])
            self.show("home")
        return go

    def cycle_size(self):
        order = ["small", "medium", "large"]
        cur = self.pet.st.get("size", "medium")
        self.pet.set_size(order[(order.index(cur) + 1) % 3]); self.show("home")

    def toggle_autostart(self):
        self.pet.autostart.set(not self.pet.autostart.get()); self.pet.toggle_autostart(); self.show("home")

    def page_tricks(self):
        pet = self.pet; picked = set(pet.st["picks"])
        self.back("Tricks")
        mine = [t for t in pet.sp["catalog"]["tricks"] if t["id"] in picked]
        tiles = [(self.preview(t["id"], round(40 * self.S)), t["name"], self.act(lambda tid=t["id"]: pet.do_trick(tid))) for t in mine]
        tiles.append(("\U0001F3AF", "Choose tricks", self.act(pet.pick_dialog)))
        self.grid(tiles, tips={t["name"]: t.get("what", "") for t in mine})
        self.note("It does these on its own too, when it feels like it. Switch more on under Choose tricks.")

    def page_together(self):
        """Its own page: all four ways of keeping you company. Owned ones start on a click; the others say the price
        (or take a free pick). Nothing here is under Choose tricks."""
        pet = self.pet; P = self.P
        self.back("Keep you company")
        every = pet.sp["catalog"].get("together", [])
        free = P.free_picks()
        tiles, tips = [], {}
        for t in every:
            owned = P.owns_pick(t["id"])
            price = P.SHOP["items"].get(f"pick:{t['id']}", {}).get("price", "$0.99")
            word = None if owned else ("free pick" if free else price)
            tiles.append((self.preview(t["id"], round(40 * self.S)), t["name"], self.act(lambda tid=t["id"]: pet.company_pick(tid)), False, None if owned else False, word))   # a locked one reads "Study with me: $0.99", dimmed
            tips[t["name"]] = t.get("what", "") + ("" if owned else (" A free pick makes it yours." if free else f" {price} in the shop."))
        self.note("It sits down next to you and stays until you click it. You start it, you end it.", pady=(0, 4))
        self.grid(tiles, tips=tips)

    def page_play(self):
        pet = self.pet; H = self.P.H
        self.back("Play with the others")
        here = H.others(pet.pid, pet.area)
        kinds = list(H.KINDS) + (["parade"] if len(here) >= 2 else [])
        em = {"dance": "\U0001F483", "chase": "\U0001F3C3", "wrestle": "\U0001F93C", "race": "\U0001F3C1", "nap": "\U0001F634", "copycat": "\U0001FA9E", "hatswap": "\U0001F3A9",
              "peekaboo": "\U0001F648", "gossip": "\U0001F4AC", "parade": "\U0001F3BA"}
        self.grid([(em.get(k, "\u2b50"), H.NAMES[k], self.act(lambda k=k: pet.play_now(k))) for k in kinds], tips={H.NAMES[k]: PLAY_TIPS.get(k, "") for k in kinds})
        who = ", ".join(o.get("name", o["pid"]) for o in here)
        self.note(f"Out right now: {who}. Anyone in the house comes out for it.")

    def page_cursor(self):
        pet = self.pet
        self.back("Cursor tricks")
        self.grid([("\U0001F635", "Dizzy", self.act(pet.dizzy_now)), ("\U0001FA82", "Parachute", self.act(pet.parachute_now)),
                   ("\U0001F3E0", "Into the house", self.act(lambda: pet.go_inside("living", 15 * 60) or pet.say("Bring out the house first.")))],
                  tips={"Dizzy": "Or spin your cursor around it fast, two or three times.", "Parachute": "Or pick it up, hold it in the air for a second, and let go.",
                        "Into the house": "Or drag it onto the house. Drag it out of an open room and it comes out where you drop it."})
        self.note("These happen on their own with the mouse: spin your cursor around it and it gets dizzy; pick it up and its legs kick, hold it up and out comes "
                  "a parachute; drop it on the house and it walks in; drag it out of an open room and it lands where you let go.")

    def page_inside(self):
        pet = self.pet
        self.back("Go inside")
        em = {"living": "\U0001F6CB\ufe0f", "bedroom": "\U0001F6CF\ufe0f", "kitchen": "\U0001F373"}
        self.grid([(em[r], label, self.act(lambda r=r: pet.go_inside(r, 15 * 60) or pet.say("Not right now."))) for r, label in ROOMS],
                  tips={"Living room": "It sits on the couch or watches TV for a while.", "Bedroom, for a nap": "It sleeps in its bed until you pick Wake up or call it out of the house.",
                        "Kitchen": "It eats at the table, then usually needs the bathroom."})
        self.note("Up to fifteen minutes, or until the house calls it out. Breaks happen in the bathroom on their own.")

    def page_break(self):
        pet = self.pet
        self.back("Bathroom break")
        self.grid([("\U0001F6BD", "Bathroom", self.act(lambda: pet.take_break("bath"))),
                   ("\U0001F6BF", "Shower", self.act(lambda: pet.take_break("shower")))],
                  tips={"Bathroom": "A quick one behind a curtain, or upstairs if the house is out.", "Shower": "A longer one, steam and all, behind the curtain or in the house."})
        self.note("A curtain drops in front of it and nobody sees a thing. With the house out, it uses the bathroom upstairs. "
                  "It takes breaks on its own too, and always after a meal.")

    def page_egg(self):
        pet = self.pet; P = self.P; S = self.S
        self.back("Egg")
        head, lines = pet.egg_status()
        row = tk.Frame(self.frame, bg=BG); row.pack(anchor="w", fill="x")
        tk.Label(row, image=self.photo(P.E.egg_image(round(72 * S), seed=7)), bg=BG, bd=0).pack(side="left", padx=(0, 10))
        txt = tk.Frame(row, bg=BG); txt.pack(side="left", anchor="n")
        tk.Label(txt, text=head, bg=BG, fg=INK, font=("Segoe UI", 11, "bold"), anchor="w", wraplength=round(360 * S), justify="left").pack(anchor="w")
        for line in lines:
            tk.Label(txt, text=line, bg=BG, fg=SOFT, font=("Segoe UI", 9), anchor="w", wraplength=round(360 * S), justify="left").pack(anchor="w", pady=(2, 0))

    def page_house(self):
        pet = self.pet; P = self.P; H = P.H; S = self.S
        self.back("The house")
        house = P.house_info(); here = pet.house_here()
        if not house:
            self.note("It sits on the taskbar next to the pets. They nap in the bedroom, eat in the kitchen and take their breaks in the bathroom. "
                      "Click it to open it up and decorate the rooms.", pady=(0, 6))
            self.grid([(self.photo(house_thumb(P.ROOT, "cozy", round(26 * S))), "Bring out the house", self.act(pet.bring_out_house))])
            return
        if not here:
            self.note("The house is on another screen. Drag it over, or call it here.", pady=(0, 6))
            self.grid([(self.photo(house_thumb(P.ROOT, house.get("style", "cozy"), round(26 * S))), "Bring it here", self.act(pet.bring_out_house))], tips={"Bring it here": "Moves the house to this screen."})
            return
        style = house.get("style", "cozy"); other = "loft" if style == "cozy" else "cozy"
        is_open = bool(house.get("open"))
        inside = [o for o in H.others(pet.pid, None) if o.get("inside")]
        me_inside = pet.state == "inside"
        tiles = [("\U0001F3E0", "Close the house" if is_open else "Open the house", self.act(lambda: pet.house_cmd("close" if is_open else "open"))),
                 ("\U0001F6CB\ufe0f", "Decorate", self.act(lambda: pet.house_cmd("decorate"))),
                 (self.photo(house_thumb(P.ROOT, other, round(26 * S))), f"{'Loft' if other == 'loft' else 'Cozy'} style", self.act(lambda: pet.house_cmd("style", style=other))),
                 ("\U0001F6B6", "Go inside", lambda: self.show("inside"), True)]
        if inside or me_inside:
            tiles.append(("\U0001F6AA", "Everyone out", self.act(lambda: pet.house_cmd("out"))))
        tiles.append(("\U0001F4E6", "Put it away", self.act(lambda: pet.house_cmd("quit"))))
        self.grid(tiles, tips=HOUSE_TIPS)
        if inside:
            self.caption("Inside, click to call out")
            pets = []
            for o in inside:
                pst = P.pet_state(o["pid"]) or {"wearing": o.get("wearing", {}), "variant": o.get("variant")}
                pets.append((self.portrait(o["pid"], pst, round(34 * S)), f"{o.get('name', o['pid'])}: {ROOM_NAMES.get(o['inside'], o['inside'])}", self.act(lambda pid=o["pid"]: pet.call_out(pid))))
            self.grid(pets)
        self.note(f"{'Loft' if style == 'loft' else 'Cozy'} style. Click a room in the open house to decorate just that room; drag the house to move it. "
                  "Put away, it stays away until you bring it out again.")

    def page_attitude(self):
        pet = self.pet; cur = pet.st.get("chaos", "cheeky")
        self.back("Attitude")
        tiles = [("\U0001F607", "Sweet", "no mischief at all"), ("\U0001F60F", "Cheeky", "muddy footprints, notes, a look now and then"),
                 ("\U0001F608", "Menace", "steals your cursor, spins out, faints, rots in your way")]
        self.grid([(ic, name, self.act(lambda lv=name.lower(): pet.set_chaos(lv)), False, cur == name.lower()) for ic, name, _ in tiles], cols=3,
                  tips={name: f"{name}: {what}." for _, name, what in tiles})
        for ic, name, what in tiles:
            tk.Label(self.frame, text=f"{name}: {what}.", bg=BG, fg=SOFT, font=("Segoe UI", 8)).pack(anchor="w")

    def page_pets(self):
        pet = self.pet; P = self.P; H = P.H
        self.back("Pets")
        inside = {o["pid"]: o["inside"] for o in H.others(pet.pid, None) if o.get("inside")}
        tiles = []
        for pid in P.adopted_ids():
            pst = P.pet_state(pid)
            ic = self.portrait(pid, pst, round(34 * self.S))
            if pid == pet.pid:
                tiles.append((ic, f"{pet.st['name']} (me)", lambda: None, False, True, "out"))
            elif pid in inside:
                tiles.append((ic, pst.get("name", pid), self.act(lambda pid=pid: pet.call_out(pid)), False, True, f"in the {ROOM_NAMES.get(inside[pid], inside[pid])}"))
            else:
                out = not pst.get("home", False)
                tiles.append((ic, pst.get("name", pid), self.act(lambda pid=pid, out=out: pet.toggle_pet(pid, out)), False, out, "out" if out else "home"))
        tiles.append(("\u2795", "Adopt another", self.act(pet.adopt_another)))
        tips = {}
        for ic, label, action, *rest in tiles:
            word = rest[2] if len(rest) > 2 else None
            if label == "Adopt another": tips[label] = "Another pet for this computer. They play together, gossip about you and share the house."
            elif label.endswith("(me)"): tips[label] = "This one. It's out right now."
            elif word == "home": tips[label] = "At home. Click to bring it out."
            elif word == "out": tips[label] = "Out right now. Click to send it home."
            elif word: tips[label] = f"Inside, {word}. Click to call it out."
        self.grid(tiles, tips=tips)
        self.note("Click a pet to send it home or bring it out. A pet in the house comes out when you click it here.")


def tile_grid(parent, S, tiles, cols=5, keep=None, tips=None):
    """A grid of tiles for a dialog: tiles are (image or emoji, label, action, selected?, note?).
    keep: a list that holds the PhotoImages alive (pass the window's own list). tips: {label: what it does}, on hover."""
    keep = keep if keep is not None else []; tips = tips or {}
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
        if tips.get(label):
            tip(t, tips[label])
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
