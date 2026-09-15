"""Render the house: the closed outside (for the taskbar), the open dollhouse, each piece of furniture as a layer,
and the pixel layout the app needs (where pets stand in each room, where the door is).

  python tools/sprites/render_house.py            # everything
  python tools/sprites/render_house.py --keep     # fit checks with the house visible, into assets/sprites/_fit/

Output: assets/house/closed.png, open.png, layout.json, furniture/<piece>.png
"""
import argparse, json, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_sprites import find_chrome, HERE  # noqa: E402

ROOT = HERE.parent.parent
OUT = ROOT / "assets" / "house"
PAGE = HERE / "house.html"
PIECES = ["bed", "lamp", "rug", "couch", "tv", "plant", "table", "fridge", "stove", "tub", "curtain", "sink", "poster", "fishtank"]
OPEN = (1200, 900)
CLOSED = (512, 512)


def shot(chrome, url, dest, w, h, profile):
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [str(chrome), "--headless=new", "--no-first-run", "--no-default-browser-check", "--hide-scrollbars",
           f"--user-data-dir={profile}", f"--window-size={w},{h}", "--default-background-color=00000000",
           "--virtual-time-budget=8000", f"--screenshot={dest}", url]
    for attempt in (1, 2, 3):
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
        except subprocess.TimeoutExpired:
            print(f"  (chrome hung on {dest.name}, try {attempt})", flush=True); continue
        if dest.exists():
            return dest
    raise RuntimeError(f"no image for {dest.name}")


def layout(chrome, profile):
    url = f"{PAGE.as_uri()}?view=open&w={OPEN[0]}&h={OPEN[1]}&layout=1"
    cmd = [str(chrome), "--headless=new", "--no-first-run", "--hide-scrollbars", f"--user-data-dir={profile}",
           f"--window-size={OPEN[0]},{OPEN[1]}", "--virtual-time-budget=8000", "--dump-dom", url]
    dom = subprocess.run(cmd, capture_output=True, text=True, timeout=90).stdout
    a = dom.rfind('<pre id="layout">'); b = dom.find("</pre>", a)
    if a < 0:
        raise RuntimeError("no layout in the page")
    data = json.loads(dom[a + len('<pre id="layout">'):b].replace("&quot;", '"'))
    url2 = f"{PAGE.as_uri()}?view=closed&w={CLOSED[0]}&h={CLOSED[1]}&layout=1"
    cmd[-1] = url2; cmd[cmd.index(f"--window-size={OPEN[0]},{OPEN[1]}")] = f"--window-size={CLOSED[0]},{CLOSED[1]}"
    dom2 = subprocess.run(cmd, capture_output=True, text=True, timeout=90).stdout
    a = dom2.rfind('<pre id="layout">'); b = dom2.find("</pre>", a)
    closed = json.loads(dom2[a + len('<pre id="layout">'):b].replace("&quot;", '"'))
    data["closed"] = {"w": closed["w"], "h": closed["h"], "door": closed["door"], "ground": closed["ground"]}
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="fit checks: furniture with the house visible, into _fit/")
    ap.add_argument("--pieces", default=",".join(PIECES))
    a = ap.parse_args()
    chrome = find_chrome(); profile = HERE / "_chrome-profile"
    t0 = time.time()
    if a.keep:
        for piece in a.pieces.split(","):
            shot(chrome, f"{PAGE.as_uri()}?view=open&w={OPEN[0]}&h={OPEN[1]}&layer={piece}&keep=1", ROOT / "assets" / "sprites" / "_fit" / f"house_{piece}.png", *OPEN, profile)
            print("  fit", piece, flush=True)
        return
    shot(chrome, f"{PAGE.as_uri()}?view=closed&w={CLOSED[0]}&h={CLOSED[1]}", OUT / "closed.png", *CLOSED, profile); print("  closed", flush=True)
    shot(chrome, f"{PAGE.as_uri()}?view=open&w={OPEN[0]}&h={OPEN[1]}", OUT / "open.png", *OPEN, profile); print("  open", flush=True)
    for piece in a.pieces.split(","):
        shot(chrome, f"{PAGE.as_uri()}?view=open&w={OPEN[0]}&h={OPEN[1]}&layer={piece}", OUT / "furniture" / f"{piece}.png", *OPEN, profile)
        print("  layer", piece, flush=True)
    (OUT / "layout.json").write_text(json.dumps(layout(chrome, profile), indent=1), encoding="utf-8")
    print(f"house rendered in {time.time() - t0:.0f}s -> {OUT}")


if __name__ == "__main__":
    main()
