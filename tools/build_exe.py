"""Build the download: dist/Perchlings/ (one folder, Perchlings.exe inside) and dist/Perchlings-<version>-windows.zip.

Ships only what the app reads: app/perchling.py, app/species/*.json, app/closet.json, the packed sprite
sheets (never the loose frames), and an icon. Needs PyInstaller in the system Python 3.12; no admin rights.

Run:  python tools/build_exe.py
Test: dist/Perchlings/Perchlings.exe --pet antenna --selftest
"""
import re, shutil, subprocess, sys, zipfile
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
STAGE = BUILD / "stage"
DIST = ROOT / "dist"


def version():
    m = re.search(r'VERSION = "([^"]+)"', (ROOT / "app" / "perchling.py").read_text(encoding="utf-8"))
    return m.group(1) if m else "0.0.0"


def stage():
    if STAGE.exists():
        shutil.rmtree(STAGE)
    (STAGE / "app").mkdir(parents=True)
    shutil.copytree(ROOT / "app" / "species", STAGE / "app" / "species")
    shutil.copyfile(ROOT / "app" / "closet.json", STAGE / "app" / "closet.json")
    shutil.copyfile(ROOT / "app" / "shop.json", STAGE / "app" / "shop.json")
    shutil.copytree(ROOT / "assets" / "house", STAGE / "assets" / "house")
    for sheet in (ROOT / "assets" / "sprites").rglob("*_sheet.*"):
        if "_fit" in sheet.parts:
            continue
        dest = STAGE / sheet.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(sheet, dest)
    n = sum(1 for _ in (STAGE / "assets").rglob("*.png"))
    print(f"staged {n} sprite sheets")


def icon():
    src = Image.open(ROOT / "site" / "img" / "icon-512.png").convert("RGBA")
    out = BUILD / "perchlings.ico"
    src.save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return out


def main():
    BUILD.mkdir(exist_ok=True)
    stage()
    ico = icon()
    if DIST.exists():
        shutil.rmtree(DIST)
    sep = ";" if sys.platform == "win32" else ":"
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--name", "Perchlings",
           "--icon", str(ico),
           "--distpath", str(DIST), "--workpath", str(BUILD / "work"), "--specpath", str(BUILD),
           "--add-data", f"{STAGE / 'app'}{sep}app",
           "--add-data", f"{STAGE / 'assets'}{sep}assets",
           str(ROOT / "app" / "perchling.py")]
    subprocess.run(cmd, check=True)
    exe = DIST / "Perchlings" / "Perchlings.exe"
    if not exe.exists():
        sys.exit("no exe built")
    ver = version()
    zpath = DIST / f"Perchlings-{ver}-windows.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in (DIST / "Perchlings").rglob("*"):
            if f.is_file():
                z.write(f, f.relative_to(DIST))
        z.writestr("Perchlings/READ ME FIRST.txt", readme(ver))
    mb = zpath.stat().st_size / 1e6
    print(f"built {exe} and {zpath.name} ({mb:.1f} MB)")


def readme(ver):
    nl = chr(10)
    return nl.join([
        f"Perchlings {ver} for Windows 10 and 11",
        "",
        "1. Keep this whole folder together. Put it anywhere you like, for example in Documents.",
        "2. Double-click Perchlings.exe.",
        "3. The first time, it asks for the code from your email and a name for your pet.",
        "4. Your pet appears at the bottom of the screen. Right-click it for its panel: tricks, the closet, the house, everything.",
        "",
        "Windows may show a warning the first time, because this is a new app it has not seen before.",
        "Click More info, then Run anyway.",
        "",
        "To stop: right-click the pet, then Quit.",
        "To have it there every morning: right-click the pet, then Start with Windows.",
        "",
        "Everything your pet knows stays in one small file on this computer:",
        "%APPDATA%" + chr(92) + "Perchlings. Nothing is sent anywhere.",
        "",
    ])


if __name__ == "__main__":
    main()
