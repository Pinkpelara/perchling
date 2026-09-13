"""Render Perchling sprite frames with headless Chrome, then pack sprite sheets.

Usage (system Python 3.12, Pillow installed):
  python render_sprites.py                 # all pets, all moods, 8 yaws, idle pose
  python render_sprites.py --pets antenna --moods happy --yaws 0,45 --size 256
  python render_sprites.py --sheets-only   # just repack existing frames

Output: assets/sprites/<pet>/<mood>_<pose>_<yaw>.png and assets/sprites/<pet>/<pet>_sheet.png + .json
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


def render_frame(chrome, pet, mood, pose, yaw, size, profile, shadow):
    dest = OUT / pet / f"{mood}_{pose}_{yaw:03d}.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"{PAGE.as_uri()}?pet={pet}&mood={mood}&pose={pose}&yaw={yaw}&size={size}&shadow={shadow}"
    cmd = [str(chrome), "--headless=new", "--no-first-run", "--no-default-browser-check", "--hide-scrollbars",
           f"--user-data-dir={profile}", f"--window-size={size},{size}", "--default-background-color=00000000",
           "--virtual-time-budget=6000", f"--screenshot={dest}", url]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
    if not dest.exists():
        raise RuntimeError(f"no frame written for {dest.name}")
    return dest


def pack_sheet(pet):
    frames = sorted((OUT / pet).glob("*.png"))
    frames = [f for f in frames if not f.name.endswith("_sheet.png")]
    if not frames:
        return
    w, h = Image.open(frames[0]).size
    cols = min(8, len(frames)); rows = (len(frames) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * w, rows * h), (0, 0, 0, 0))
    index = {}
    for i, f in enumerate(frames):
        x, y = (i % cols) * w, (i // cols) * h
        sheet.paste(Image.open(f).convert("RGBA"), (x, y))
        index[f.stem] = {"x": x, "y": y, "w": w, "h": h}
    sheet.save(OUT / pet / f"{pet}_sheet.png", optimize=True)
    (OUT / pet / f"{pet}_sheet.json").write_text(json.dumps({"frame": [w, h], "frames": index}, indent=1))
    print(f"{pet}: {len(frames)} frames -> {pet}_sheet.png ({cols}x{rows})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pets", default=",".join(PETS)); ap.add_argument("--moods", default=",".join(MOODS))
    ap.add_argument("--poses", default="idle"); ap.add_argument("--yaws", default="0,45,90,135,180,225,270,315")
    ap.add_argument("--size", type=int, default=256); ap.add_argument("--sheets-only", action="store_true")
    ap.add_argument("--shadow", default="0", help="floor shadow opacity; 0 for desktop sprites, 0.32 for showroom")
    ap.add_argument("--skip-existing", action="store_true")
    a = ap.parse_args()
    pets, moods, poses = a.pets.split(","), a.moods.split(","), a.poses.split(",")
    yaws = [int(y) for y in a.yaws.split(",")]
    if not a.sheets_only:
        chrome = find_chrome()
        profile = HERE / "_chrome-profile"
        t0 = time.time(); n = 0
        for pet in pets:
            for mood in moods:
                for pose in poses:
                    for yaw in yaws:
                        if a.skip_existing and (OUT / pet / f"{mood}_{pose}_{yaw:03d}.png").exists():
                            continue
                        render_frame(chrome, pet, mood, pose, yaw, a.size, profile, a.shadow); n += 1
                        print(f"  {pet} {mood} {pose} {yaw:3d}", flush=True)
        print(f"rendered {n} frames in {time.time() - t0:.0f}s")
    for pet in pets:
        pack_sheet(pet)


if __name__ == "__main__":
    main()
