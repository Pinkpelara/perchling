"""Render the hat maker shapes for every pet: the same pose set as the closet items, id colours, no tone mapping."""
import subprocess, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
SHAPES = ["cap", "beanie", "bucket", "tophat", "cowboy", "visor"]
layers = ",".join("maker:" + s for s in SHAPES)
pets = sys.argv[1] if len(sys.argv) > 1 else "antenna,ears,leaf,horns"
t0 = time.time()
for poses, yaws in (("idle", "0,60,120,180,240,300"), ("walk1,walk2,squash,stretch,sit", "0,60,300"), ("lie,dab", "0")):
    subprocess.run([sys.executable, str(HERE / "render_sprites.py"), "--pets", pets, "--layers", layers, "--poses", poses, "--yaws", yaws, "--skip-existing"], check=True)
print(f"maker shapes rendered in {time.time() - t0:.0f}s")
