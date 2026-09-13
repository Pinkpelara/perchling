"""Render Perchling sprite frames with headless Chrome, then pack sprite sheets.

Usage (system Python 3.12, Pillow installed):
  python render_sprites.py                 # all pets, all moods, 8 yaws, idle pose
  python render_sprites.py --pets antenna --moods happy --yaws 0,45 --size 256
  python render_sprites.py --sheets-only   # just repack existing frames
  python render_sprites.py --layers beanie,crown --poses idle,walk1,walk2,squash,stretch --yaws 0,60,300
                                           # closet items as see-through layers, one sheet per item per pet
  python render_sprites.py --layers beanie --keep --yaws 0   # pet + item together, to check the fit (not packed)

Output: assets/sprites/<pet>/<mood>_<pose>_<yaw>.png and assets/sprites/<pet>/<pet>_sheet.png + .json
        assets/sprites/<pet>/outfits/<item>/<pose>_<yaw>.png and assets/sprites/<pet>/outfits/<item>_sheet.png + .json
        assets/sprites/_fit/<pet>_<item>_<pose>_<yaw>.png for --keep checks (not committed)
"""
import argparse, json, os, subprocess, sys, time
from pathlib import Path
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT / "assets" / "sprites"
PAGE = HERE / "sprite.html"
CHROME_CANDIDATES = [
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Google/Chrome/Application/chrome.exe",
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
]
PETS = ["antenna", "ears", "leaf", "horns"]
MOODS = ["happy", "surprised", "sleepy", "sulky"]
POSES = ["idle", "blink", "walk1", "walk2", "squash", "stretch"]


def find_chrome():
    for c in CHROME_CANDIDATES:
        if c.exists():
            return c
    sys.exit("Chrome or Edge not found; set CHROME env var")


def render_frame(chrome, pet, mood, pose, yaw, size, profile, shadow, layer="", keep=False):
    if layer and keep:
        dest = OUT / "_fit" / f"{pet}_{layer}_{pose}_{yaw:03d}.png"
    elif layer:
        dest = OUT / pet / "outfits" / layer / f"{pose}_{yaw:03d}.png"
    else:
        dest = OUT / pet / f"{mood}_{pose}_{yaw:03d}.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"{PAGE.as_uri()}?pet={pet}&mood={mood}&pose={pose}&yaw={yaw}&size={size}&shadow={shadow}"
    if layer:
        url += f"&layer={layer}" + ("&keep=1" if keep else "")
    cmd = [str(chrome), "--headless=new", "--no-first-run", "--no-default-browser-check", "--hide-scrollbars",
           f"--user-data-dir={profile}", f"--window-size={size},{size}", "--default-background-color=00000000",
           "--virtual-time-budget=6000", f"--screenshot={dest}", url]
    for attempt in (1, 2, 3):            # headless Chrome occasionally hangs; a fresh start fixes it
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
        except subprocess.TimeoutExpired:
            print(f"  (chrome hung on {dest.name}, try {attempt})", flush=True)
            continue
        if dest.exists():
            return dest
    raise RuntimeError(f"no frame written for {dest.name}")


def pack_sheet(pet, layer=""):
    folder = OUT / pet / "outfits" / layer if layer else OUT / pet
    name = layer or pet
    frames = sorted(folder.glob("*.png"))
    frames = [f for f in frames if not f.name.endswith("_sheet.png")]
    if not frames:
        return
    dest = folder.parent if layer else folder
    w, h = Image.open(frames[0]).size
    cols = min(8, len(frames)); rows = (len(frames) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * w, rows * h), (0, 0, 0, 0))
    index = {}
    for i, f in enumerate(frames):
        x, y = (i % cols) * w, (i // cols) * h
        sheet.paste(Image.open(f).convert("RGBA"), (x, y))
        index[f.stem] = {"x": x, "y": y, "w": w, "h": h}
    sheet.save(dest / f"{name}_sheet.png", optimize=True)
    (dest / f"{name}_sheet.json").write_text(json.dumps({"frame": [w, h], "frames": index}, indent=1))
    print(f"{pet}{' ' + layer if layer else ''}: {len(frames)} frames -> {name}_sheet.png ({cols}x{rows})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pets", default=",".join(PETS)); ap.add_argument("--moods", default=",".join(MOODS))
    ap.add_argument("--poses", default="idle"); ap.add_argument("--yaws", default="0,45,90,135,180,225,270,315")
    ap.add_argument("--size", type=int, default=256); ap.add_argument("--sheets-only", action="store_true")
    ap.add_argument("--shadow", default="0", help="floor shadow opacity; 0 for desktop sprites, 0.32 for showroom")
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--layers", default="", help="closet item ids to render as layers (see app/closet.json); mood is ignored")
    ap.add_argument("--keep", action="store_true", help="with --layers: keep the pet visible, write to _fit/, do not pack")
    a = ap.parse_args()
    pets, moods, poses = a.pets.split(","), a.moods.split(","), a.poses.split(",")
    yaws = [int(y) for y in a.yaws.split(",")]
    layers = [l for l in a.layers.split(",") if l]
    if not a.sheets_only:
        chrome = find_chrome()
        profile = HERE / "_chrome-profile"
        t0 = time.time(); n = 0
        for pet in pets:
            if layers:
                for layer in layers:
                    for pose in poses:
                        for yaw in yaws:
                            if a.skip_existing and not a.keep and (OUT / pet / "outfits" / layer / f"{pose}_{yaw:03d}.png").exists():
                                continue
                            render_frame(chrome, pet, "happy", pose, yaw, a.size, profile, a.shadow, layer, a.keep); n += 1
                            print(f"  {pet} {layer} {pose} {yaw:3d}", flush=True)
                continue
            for mood in moods:
                for pose in poses:
                    for yaw in yaws:
                        if a.skip_existing and (OUT / pet / f"{mood}_{pose}_{yaw:03d}.png").exists():
                            continue
                        render_frame(chrome, pet, mood, pose, yaw, a.size, profile, a.shadow); n += 1
                        print(f"  {pet} {mood} {pose} {yaw:3d}", flush=True)
        print(f"rendered {n} frames in {time.time() - t0:.0f}s")
    if a.keep:
        return
    for pet in pets:
        if layers:
            for layer in layers:
                pack_sheet(pet, layer)
        else:
            pack_sheet(pet)


if __name__ == "__main__":
    main()
