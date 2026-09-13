"""Inline web/pets.js into web/look-test.html -> web/dist/look-test.html (single file for publishing)."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
src = (ROOT / "web" / "look-test.html").read_text(encoding="utf-8")
pets = (ROOT / "web" / "pets.js").read_text(encoding="utf-8")
out = src.replace('<script src="pets.js"></script>', "<script>\n" + pets + "\n</script>")
assert out != src, "pets.js script tag not found"
dist = ROOT / "web" / "dist"; dist.mkdir(exist_ok=True)
(dist / "look-test.html").write_text(out, encoding="utf-8")
print("built", dist / "look-test.html", len(out), "bytes")
