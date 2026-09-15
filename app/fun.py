"""The parts that get clipped: music, reactions to the owner, mischief, signs, photos, confetti.

Nothing here identifies anything: the music listener reads only how loud the speakers are, the key watcher
counts key presses without knowing which letters, and nothing is stored or sent.
"""
import ctypes, os, random, threading, time
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
import tkinter as tk
from PIL import Image, ImageDraw, ImageFont, ImageTk


# ------------------------------------------------------------------ music: just the volume
class AudioEar:
    """Samples the speakers' peak level ten times a second. music is True while there's been sound for a few seconds."""
    def __init__(self):
        self.level = 0.0
        self.music = False
        self._loud_since = None
        self._quiet_since = time.time()
        self.ok = False
        threading.Thread(target=self._run, daemon=True).start()

    def _meter(self):
        from comtypes import CLSCTX_ALL, CoInitialize
        from pycaw.pycaw import AudioUtilities, IAudioMeterInformation
        CoInitialize()
        dev = AudioUtilities.GetSpeakers()
        iface = dev._dev.Activate(IAudioMeterInformation._iid_, CLSCTX_ALL, None)
        return iface.QueryInterface(IAudioMeterInformation)

    def _run(self):
        try:
            meter = self._meter(); self.ok = True
        except Exception:
            return
        while True:
            try:
                peak = float(meter.GetPeakValue())
            except Exception:
                peak = 0.0
            self.level = peak
            now = time.time()
            if peak > 0.03:
                self._loud_since = self._loud_since or now; self._quiet_since = None
                if now - self._loud_since > 2.5: self.music = True
            else:
                self._quiet_since = self._quiet_since or now; self._loud_since = None
                if now - self._quiet_since > 4: self.music = False
            time.sleep(0.1)


# ------------------------------------------------------------------ keys and clicks: how much, never what
class KeyWatch:
    """Counts key presses and clicks by polling key states. Knows the rate, not the letters."""
    VK_LBUTTON, VK_CONTROL, VK_Z, VK_S = 0x01, 0x11, 0x5A, 0x53

    def __init__(self):
        self.presses = []          # timestamps of key presses (last 10 s)
        self.clicks = []
        self.undo_times = []
        self.save_times = []
        self._down = set()
        self._u = ctypes.windll.user32

    def poll(self):
        now = time.time()
        u = self._u
        for vk in range(0x08, 0xFF):
            if vk in (self.VK_LBUTTON, 0x02, 0x04): continue
            if u.GetAsyncKeyState(vk) & 0x8000:
                if vk not in self._down:
                    self._down.add(vk); self.presses.append(now)
                    if vk == self.VK_Z and (u.GetAsyncKeyState(self.VK_CONTROL) & 0x8000): self.undo_times.append(now)
                    if vk == self.VK_S and (u.GetAsyncKeyState(self.VK_CONTROL) & 0x8000): self.save_times.append(now)
            else:
                self._down.discard(vk)
        if u.GetAsyncKeyState(self.VK_LBUTTON) & 0x8000:
            if "click" not in self._down: self._down.add("click"); self.clicks.append(now)
        else:
            self._down.discard("click")
        cut = now - 10
        self.presses = [t for t in self.presses if t > cut]; self.clicks = [t for t in self.clicks if t > cut]
        self.undo_times = [t for t in self.undo_times if t > now - 6]; self.save_times = [t for t in self.save_times if t > now - 6]

    def typing_rate(self):
        return len([t for t in self.presses if t > time.time() - 5]) / 5.0

    def click_rate(self):
        return len([t for t in self.clicks if t > time.time() - 5]) / 5.0


def screen_locked():
    """True while the lock screen is up (the input desktop can't be opened)."""
    try:
        h = ctypes.windll.user32.OpenInputDesktop(0, False, 0x0100)
        if h:
            ctypes.windll.user32.CloseDesktop(h); return False
        return True
    except (AttributeError, OSError):
        return False


# ------------------------------------------------------------------ small windows that appear and go
class Overlay:
    """A colour-keyed, click-through-ish window with one image, gone after a while."""
    def __init__(self, root, image, x, y, colorkey, ms=None, topmost=True):
        self.win = tk.Toplevel(root); self.win.overrideredirect(True); self.win.attributes("-topmost", topmost)
        self.win.attributes("-transparentcolor", colorkey); self.win.configure(bg=colorkey)
        self.label = tk.Label(self.win, bg=colorkey, bd=0, highlightthickness=0); self.label.pack()
        self.colorkey = colorkey
        self.set(image); self.move(x, y)
        if ms: root.after(ms, self.close)

    def set(self, image):
        self.img = image; self.label.configure(image=image)

    def move(self, x, y):
        self.win.geometry(f"+{int(x)}+{int(y)}")

    def close(self):
        try: self.win.destroy()
        except tk.TclError: pass


def keyed(im, colorkey_rgb, cut=110):
    mask = im.getchannel("A").point(lambda a: 255 if a >= cut else 0)
    out = Image.new("RGB", im.size, colorkey_rgb); out.paste(im.convert("RGB"), mask=mask)
    return ImageTk.PhotoImage(out)


def footprint_image(scale, facing, colorkey_rgb):
    s = max(10, int(14 * scale)); im = Image.new("RGBA", (s * 2, s * 2), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    mud = (120, 84, 52, 190)
    d.ellipse((s * 0.5, s * 0.7, s * 1.5, s * 1.9), fill=mud)
    for i in range(3): d.ellipse((s * (0.45 + i * 0.4), s * 0.25, s * (0.75 + i * 0.4), s * 0.65), fill=mud)
    if facing < 0: im = im.transpose(Image.FLIP_LEFT_RIGHT)
    return keyed(im, colorkey_rgb, 60)


def note_image(scale, text, colorkey_rgb):
    w, h = int(150 * scale), int(110 * scale)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((2, 2, w - 3, h - 3), radius=int(6 * scale), fill=(255, 241, 150, 255), outline=(220, 200, 90, 255), width=2)
    d.rectangle((2, 2, w - 3, int(14 * scale)), fill=(245, 220, 110, 255))
    f = font(int(13 * scale))
    y = int(20 * scale)
    for line in wrap(text, f, w - int(16 * scale)):
        d.text((int(8 * scale), y), line, font=f, fill=(70, 55, 30, 255)); y += int(17 * scale)
    return keyed(im, colorkey_rgb)


def font(size, bold=False):
    for name in (["seguisb.ttf", "segoeuib.ttf"] if bold else ["segoeui.ttf"]):
        p = Path("C:/Windows/Fonts") / name
        if p.exists(): return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def wrap(text, f, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if f.getlength(t) <= width or not cur: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines


def sign_frame(pet_im, text, facing=1):
    """The pet holding a sign on a stick, at sheet size (256). Text wraps; long text gets smaller."""
    im = pet_im.copy(); d = ImageDraw.Draw(im)
    size = 20 if len(text) <= 24 else (16 if len(text) <= 60 else 13)
    f = font(size, bold=True)
    lines = wrap(text, f, 120)[:4]
    bw, bh = 136, max(46, 12 + len(lines) * (size + 4))
    x0 = 122 if facing > 0 else 0; y0 = 10
    d.rectangle((x0 + 62, y0 + bh - 4, x0 + 68, 175), fill=(170, 120, 70, 255))                     # the stick, into the pet's hand
    d.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), radius=8, fill=(255, 250, 235, 255), outline=(170, 120, 70, 255), width=3)
    y = y0 + 6
    for line in lines:
        d.text((x0 + (bw - f.getlength(line)) / 2, y), line, font=f, fill=(35, 33, 59, 255)); y += size + 4
    return im


def photo(pet_im, name, house_im=None, out_dir=None):
    """A framed picture with stickers and a caption. Returns the saved path."""
    W, H = 900, 700
    im = Image.new("RGBA", (W, H), (255, 248, 240, 255)); d = ImageDraw.Draw(im)
    for i in range(0, W, 60):
        d.ellipse((i + 20, 18, i + 34, 32), fill=random.choice([(245, 142, 166, 255), (255, 209, 102, 255), (196, 176, 255, 255), (47, 179, 163, 255)]))
        d.ellipse((i + 20, H - 32, i + 34, H - 18), fill=random.choice([(245, 142, 166, 255), (255, 209, 102, 255), (196, 176, 255, 255), (47, 179, 163, 255)]))
    d.rounded_rectangle((40, 50, W - 40, H - 90), radius=28, fill=(240, 228, 250, 255))
    if house_im is not None:
        hw = W - 120; hh = round(house_im.height * hw / house_im.width)
        im.alpha_composite(house_im.resize((hw, hh), Image.LANCZOS), (60, 60))
    size = 480 if house_im is None else 330
    big = pet_im.resize((size, size), Image.LANCZOS)
    im.alpha_composite(big, (W // 2 - size // 2, H - 90 - size + 10))
    for _ in range(9):
        x, y = random.randint(60, W - 90), random.randint(70, H - 130); r = random.randint(8, 16)
        if random.random() < 0.5:
            d.polygon([(x, y - r), (x + r * 0.3, y - r * 0.3), (x + r, y), (x + r * 0.3, y + r * 0.3), (x, y + r), (x - r * 0.3, y + r * 0.3), (x - r, y), (x - r * 0.3, y - r * 0.3)], fill=(255, 209, 102, 255))
        else:
            d.ellipse((x - r, y - r, x, y), fill=(245, 142, 166, 255)); d.ellipse((x, y - r, x + r, y), fill=(245, 142, 166, 255)); d.polygon([(x - r, y - r * 0.3), (x + r, y - r * 0.3), (x, y + r)], fill=(245, 142, 166, 255))
    f = font(34, bold=True); f2 = font(18)
    d.text((60, H - 80), name, font=f, fill=(35, 33, 59, 255))
    d.text((60, H - 40), datetime.now().strftime("%B %d, %Y") + "  ·  Perchlings", font=f2, fill=(107, 102, 133, 255))
    out_dir = out_dir or Path(os.path.expanduser("~")) / "Pictures" / "Perchlings"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name} {datetime.now().strftime('%Y-%m-%d %H-%M-%S')}.png"
    im.convert("RGB").save(path); return path


def confetti_frames(w, h, colorkey_rgb, n=14):
    """A short burst of falling confetti as keyed frames."""
    rnd = random.Random()
    bits = [(rnd.randint(0, w), rnd.randint(-h, 0), rnd.choice([(245, 142, 166), (255, 209, 102), (196, 176, 255), (47, 179, 163), (88, 166, 78)]), rnd.uniform(2, 5), rnd.uniform(-1, 1)) for _ in range(90)]
    frames = []
    for k in range(n):
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        for x, y, c, fall, drift in bits:
            yy = y + fall * k * 6; xx = x + drift * k * 4 + 6 * (1 if k % 2 else -1) * (1 if fall > 3.5 else 0)
            if 0 <= yy <= h: d.rectangle((xx, yy, xx + 6, yy + 10), fill=c + (255,))
        frames.append(keyed(im, colorkey_rgb, 60))
    return frames
