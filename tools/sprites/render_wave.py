"""Render the closet wave (every new item) for every pet: the same pose set as the other closet items."""
import subprocess, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
ITEMS = "wizard,pirate,viking,halo,devil,catears,bunny,tiara,sweatband,eyepatch,monocle,glasses3d,moustache,bowtie,scarf,bandana,tshirt,jersey,suit,sweater,angelwings,batwings,backpack,jetpack"
pets = sys.argv[1] if len(sys.argv) > 1 else "antenna,ears,leaf,horns"
t0 = time.time()
for poses, yaws in (("idle", "0,60,120,180,240,300"), ("walk1,walk2,squash,stretch,sit", "0,60,300"), ("lie,dab", "0")):
    subprocess.run([sys.executable, str(HERE / "render_sprites.py"), "--pets", pets, "--layers", ITEMS, "--poses", poses, "--yaws", yaws, "--skip-existing"], check=True)
print(f"wave rendered in {time.time() - t0:.0f}s")
