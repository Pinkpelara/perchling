# Perchlings

Cute 3D pets that live on your desktop. You buy one, download it, click it, and it hops out and wanders your screen. Close the window; the pet stays. Name it, pick five things it can do, dress it from its closet. It learns your routine, celebrates birthdays, and sulks when you ignore it.

This repo is the whole product: the pets' look, the tools that turn that look into game-ready art, the desktop app, and the shop site.

## Layout

```
web/pets.js                 The pets, as three.js geometry. Single source of truth for the look.
web/look-test.html          Interactive demo (drag to turn, click a pet, pick a mood). Loads pets.js.
web/dist/look-test.html     Same demo with pets.js inlined, for publishing. Built by tools/build_looktest.py.
tools/sprites/sprite.html   Renders one pet, one mood, one pose, one angle, transparent background.
tools/sprites/render_sprites.py   Drives headless Chrome over every pet/mood/pose/angle and packs sprite sheets.
assets/sprites/<pet>/       Rendered frames + <pet>_sheet.png + <pet>_sheet.json (generated, not hand-edited).
docs/                       Look recipe, catalog, decisions.
app/                        The Windows desktop app (next).
```

## The four pets

Labelled by colour until they have names. Each keeps one silhouette feature.

| Label | Feature | Style |
|---|---|---|
| Teal | antenna with a ball | cute (baby proportions, blush) |
| Pink | round side ears | cute |
| Green | leaf on top | calm (a little older) |
| Gold | small horns | cool (smaller eyes set higher, half-lidded, no blush, taller) |

Moods: happy, surprised, sleepy, sulky. Poses: idle, blink, walk1, walk2, squash, stretch.

## Run things

Needs Python 3.12 with Pillow, and Chrome or Edge installed. No admin rights needed.

```
python tools/build_looktest.py                      # rebuild web/dist/look-test.html
python tools/sprites/render_sprites.py              # all pets, all moods, 8 angles, idle pose
python tools/sprites/render_sprites.py --pets horns --moods happy,sulky --yaws 0,40
```

Open `web/dist/look-test.html` in a browser to see the pets.

## How the desktop app will draw them

Real-time 3D on the desktop is v2. v1 pre-renders the same three.js pets to transparent sprite frames (this repo's `tools/sprites`) and plays them in a small always-on-top window, the same way Beam works. At pet size the result is indistinguishable from live 3D and costs almost nothing to run.

## Rules

- The catalog (tricks, behaviours, gadgets, closet shelves) is research-backed; every item has a source. See `docs/catalog.md`.
- No wellness or productivity features. It is a pet.
- No ads, no mystery boxes, no chat, no social feed. Fixed prices.
- Local-first: what the pet learns about the owner stays on their computer.
- An adult holds the account; a child can be the owner. No birth years, location, photos or messaging.
