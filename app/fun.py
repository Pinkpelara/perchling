"""The parts that get clipped: music, reactions to the owner, mischief, signs, photos, confetti.

Nothing here identifies anything: the music listener reads only how loud the speakers are, the key watcher
counts key presses without knowing which letters, and nothing is stored or sent.
"""
import ctypes, os, random, threading, time
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
import tkinter as tk
from PIL import Image, ImageDraw, ImageFont, ImageGrab, ImageTk


# ------------------------------------------------------------------ music: just the volume
class AudioEar:
    """Samples the speakers' peak level ten times a second. music is True while there's been sound for a few seconds.

    Sound is judged over a window, not sample by sample: music at low volume dips under any bar between beats
    and between songs, so it counts as playing while most of the last three seconds had sound, and as stopped
    once four seconds have gone by with almost none.
    """
    QUIET = 0.008          # the meter reads 0 to 1; a whisper at low volume is around 0.01

    def __init__(self):
        self.level = 0.0
        self.music = False
        self.hearing = False       # sound right now, whatever the pet makes of it
        self.recent = []           # the last 40 samples, True where there was sound
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
        meter = None
        while True:
            if meter is None:                                # the default speakers can change (headphones plugged in): try again
                try:
                    meter = self._meter(); self.ok = True
                except Exception:
                    self.ok = False; time.sleep(5); continue
            try:
                peak = float(meter.GetPeakValue())
            except Exception:
                meter = None; peak = 0.0
            self.level = peak
            self.hearing = peak > self.QUIET
            self.recent = (self.recent + [self.hearing])[-40:]
            last30 = self.recent[-30:]
            if not self.music and len(last30) >= 25 and sum(last30) >= 0.6 * len(last30):
                self.music = True
            elif self.music and len(self.recent) >= 40 and sum(self.recent) < 4:
                self.music = False
            time.sleep(0.1)


# ------------------------------------------------------------------ keys and clicks: how much, never what
class KeyWatch:
    """Counts key presses and clicks. Knows the rate, not the letters.

    A thread polls the keys people type with every 30 ms while the keyboard is busy (every 100 ms when it's
    quiet) and counts key-down moments. Polling the plain key state is the one thing another program can't
    interfere with (the "pressed since last asked" flag is shared, so with three pets each would see a third),
    and a tap lasts 40 to 80 ms, so 30 ms catches all of them. Nothing is stored beyond a few seconds of timestamps.
    """
    VK_LBUTTON, VK_CONTROL, VK_Z, VK_S = 0x01, 0x11, 0x5A, 0x53
    KEYS = ([0x08, 0x09, 0x0D, 0x20, 0x2E] + list(range(0x30, 0x3A)) + list(range(0x41, 0x5B)) + list(range(0x60, 0x6A))
            + list(range(0xBA, 0xC1)) + list(range(0xDB, 0xDF)))      # backspace, tab, enter, space, delete, digits, letters, numpad, punctuation

    def __init__(self):
        self.presses = []          # timestamps of key presses (last 10 s)
        self.clicks = []
        self.undo_times = []
        self.save_times = []
        self._down = set()
        self._u = ctypes.windll.user32
        self._lock = threading.Lock()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        u = self._u; last_seen = 0.0
        while True:
            now = time.time()
            with self._lock:
                for vk in self.KEYS:
                    if u.GetAsyncKeyState(vk) & 0x8000:
                        if vk not in self._down:
                            self._down.add(vk); self.presses.append(now); last_seen = now
                            if vk == self.VK_Z and (u.GetAsyncKeyState(self.VK_CONTROL) & 0x8000): self.undo_times.append(now)
                            if vk == self.VK_S and (u.GetAsyncKeyState(self.VK_CONTROL) & 0x8000): self.save_times.append(now)
                    else:
                        self._down.discard(vk)
                if u.GetAsyncKeyState(self.VK_LBUTTON) & 0x8000:
                    if "click" not in self._down: self._down.add("click"); self.clicks.append(now); last_seen = now
                else:
                    self._down.discard("click")
            time.sleep(0.03 if now - last_seen < 10 else 0.1)

    def poll(self):
        """Called from the pet's loop: forget what's older than ten seconds."""
        now = time.time(); cut = now - 10
        with self._lock:
            self.presses = [t for t in self.presses if t > cut]; self.clicks = [t for t in self.clicks if t > cut]
            self.undo_times = [t for t in self.undo_times if t > now - 6]; self.save_times = [t for t in self.save_times if t > now - 6]

    def typing_rate(self):
        """Keys per second over the last four seconds."""
        return len([t for t in self.presses if t > time.time() - 4]) / 4.0

    def click_rate(self):
        return len([t for t in self.clicks if t > time.time() - 4]) / 4.0


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


# ------------------------------------------------------------------ clips: eight seconds of the pet, as a GIF
def grab_region(x0, y0, x1, y1):
    """A screenshot of just that box, any monitor. PIL's grab copies the whole desktop first (half a second at 4K)."""
    w, h = int(x1 - x0), int(y1 - y0)
    if w <= 0 or h <= 0:
        return None
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    for f in (user32.GetDC, gdi32.CreateCompatibleDC, gdi32.CreateCompatibleBitmap, gdi32.SelectObject):
        f.restype = ctypes.c_void_p
    user32.GetDC.argtypes = [ctypes.c_void_p]; gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
    gdi32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    gdi32.BitBlt.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    gdi32.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
    gdi32.DeleteObject.argtypes = [ctypes.c_void_p]; gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
    user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    screen = user32.GetDC(None)
    mem = gdi32.CreateCompatibleDC(screen)
    bmp = gdi32.CreateCompatibleBitmap(screen, w, h)
    old = gdi32.SelectObject(mem, bmp)
    gdi32.BitBlt(mem, 0, 0, w, h, screen, int(x0), int(y0), 0x00CC0020 | 0x40000000)     # SRCCOPY | CAPTUREBLT
    class BMI(ctypes.Structure):
        _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32), ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
                    ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32), ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32),
                    ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32), ("biClrImportant", ctypes.c_uint32)]
    bmi = BMI(); bmi.biSize = ctypes.sizeof(BMI); bmi.biWidth = w; bmi.biHeight = -h; bmi.biPlanes = 1; bmi.biBitCount = 32
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bmi), 0)
    gdi32.SelectObject(mem, old); gdi32.DeleteObject(bmp); gdi32.DeleteDC(mem); user32.ReleaseDC(None, screen)
    return Image.frombuffer("RGB", (w, h), buf, "raw", "BGRX", 0, 1)


def record_clip(where, seconds=8, fps=12, max_w=480, out_dir=None, name="Perchling", done=None):
    """Records the screen around the pet (where() returns the box to grab each frame, so it follows the pet)
    and writes a GIF to Pictures/Perchlings/Clips. Runs in a thread; done(path or None) is called at the end."""
    def work():
        frames = []; t0 = time.time(); n = int(seconds * fps); size = None
        for i in range(n):
            x0, y0, x1, y1 = where()
            try:
                im = grab_region(x0, y0, x1, y1)
            except Exception:
                im = None
            if im is not None:
                if size is None:
                    k = min(1.0, max_w / im.width); size = (max(2, round(im.width * k)), max(2, round(im.height * k)))
                frames.append(im.resize(size, Image.BILINEAR))
            time.sleep(max(0, t0 + (i + 1) / fps - time.time()))
        path = None
        if frames:
            pal = frames[len(frames) // 2].convert("P", palette=Image.ADAPTIVE, colors=255)      # one palette for the whole clip: faster, steadier colours
            frames = [f.quantize(palette=pal, dither=Image.FLOYDSTEINBERG) for f in frames]
            folder = out_dir or Path(os.path.expanduser("~")) / "Pictures" / "Perchlings" / "Clips"
            try:
                folder.mkdir(parents=True, exist_ok=True)
                path = folder / f"{name} {datetime.now().strftime('%Y-%m-%d %H-%M-%S')}.gif"
                frames[0].save(path, save_all=True, append_images=frames[1:], duration=round(1000 / fps), loop=0, optimize=False)
            except OSError:
                path = None
        if done: done(path)
    threading.Thread(target=work, daemon=True).start()


# ------------------------------------------------------------------ effects: a trail that follows the pet
EFFECT_COLOURS = {"sparkles": [(255, 236, 140), (255, 255, 255), (255, 209, 102)], "hearts": [(245, 100, 140), (255, 150, 180), (230, 60, 110)],
                  "rainbow": [(255, 80, 80), (255, 170, 60), (250, 230, 80), (90, 200, 120), (80, 150, 250), (170, 100, 240)],
                  "fire": [(255, 120, 40), (255, 200, 60), (230, 60, 30)], "snow": [(255, 255, 255), (220, 240, 255)],
                  "bubbles": [(170, 220, 255), (210, 240, 255)], "notes": [(90, 63, 192), (47, 179, 163), (245, 142, 166)], "stars": [(255, 220, 90), (255, 255, 255)]}


class Trail:
    """One colour-keyed window behind the pet with a few particles that rise, fall or drift, redrawn as they move."""
    def __init__(self, root, kind, colorkey, colorkey_rgb, scale):
        self.kind, self.scale, self.rgb = kind, scale, colorkey_rgb
        self.parts = []                     # [x, y, vx, vy, age, colour, size]
        self.w = self.h = 0
        self.ov = Overlay(root, keyed(Image.new("RGBA", (2, 2), (0, 0, 0, 0)), colorkey_rgb, 1), -5000, -5000, colorkey, topmost=True)
        self.rnd = random.Random()

    def close(self):
        self.ov.close()

    def spawn(self, n, sx, sy):
        rnd = self.rnd; cols = EFFECT_COLOURS.get(self.kind, EFFECT_COLOURS["sparkles"])
        for _ in range(n):
            up = self.kind in ("fire", "bubbles", "notes", "hearts"); down = self.kind == "snow"
            vy = rnd.uniform(-2.2, -0.8) if up else (rnd.uniform(0.6, 1.4) if down else rnd.uniform(-0.6, 0.6))
            self.parts.append([sx + rnd.uniform(-10, 10) * self.scale, sy + rnd.uniform(-10, 10) * self.scale, rnd.uniform(-0.8, 0.8), vy, 0, rnd.choice(cols), rnd.uniform(7, 13) * self.scale])

    def tick(self, x, y, size, moving, floor):
        """x, y, size: the pet's window; moving: -1, 0 or 1 (which way). Draws around it and one pet-width behind."""
        S = size; W, H = int(S * 2.2), int(S * 1.6); ox, oy = int(x - S * 0.6), int(y - S * 0.5)
        cx, cy = x + S * 0.5, y + S * 0.55                                  # the pet's middle, on the screen
        if moving or self.kind in ("fire", "bubbles", "snow") or self.rnd.random() < 0.3:
            behind = -moving * S * 0.4 if moving else 0
            self.spawn(2 if moving else 1, cx + behind, y - S * 0.1 if self.kind == "snow" else cy)
        keep = []
        for p in self.parts:                                                 # particles live in screen space, so they stay where they were dropped
            p[0] += p[2] * self.scale; p[1] += p[3] * self.scale; p[4] += 1
            if p[4] < 30 and ox <= p[0] <= ox + W and oy <= p[1] <= oy + H: keep.append(p)
        self.parts = keep[-48:]
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        for sx_, sy_, _, _, age, c, sz in self.parts:
            px, py = sx_ - ox, sy_ - oy
            a = int(255 * (1 - age / 30)); r = sz * (1 - age / 60)
            col = c + (255,)
            if a < 100: continue
            k = self.kind
            if k in ("sparkles", "stars"):
                d.polygon([(px, py - r), (px + r * 0.3, py - r * 0.3), (px + r, py), (px + r * 0.3, py + r * 0.3), (px, py + r), (px - r * 0.3, py + r * 0.3), (px - r, py), (px - r * 0.3, py - r * 0.3)], fill=col)
            elif k == "hearts":
                d.ellipse((px - r, py - r, px, py), fill=col); d.ellipse((px, py - r, px + r, py), fill=col); d.polygon([(px - r, py - r * 0.3), (px + r, py - r * 0.3), (px, py + r)], fill=col)
            elif k == "notes":
                d.ellipse((px - r * 0.6, py, px + r * 0.4, py + r * 0.7), fill=col); d.line([(px + r * 0.4, py + r * 0.35), (px + r * 0.4, py - r)], fill=col, width=max(1, int(2 * self.scale)))
            elif k == "bubbles":
                d.ellipse((px - r, py - r, px + r, py + r), outline=col, width=max(1, int(2 * self.scale)))
            elif k == "fire":
                d.polygon([(px, py - r * 1.4), (px + r * 0.7, py + r * 0.3), (px, py + r), (px - r * 0.7, py + r * 0.3)], fill=col)
            else:
                d.ellipse((px - r * 0.7, py - r * 0.7, px + r * 0.7, py + r * 0.7), fill=col)
        self.ov.set(keyed(im, self.rgb, 60)); self.ov.move(ox, oy)
