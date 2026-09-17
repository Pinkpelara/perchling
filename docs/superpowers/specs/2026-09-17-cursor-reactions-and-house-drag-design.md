# Cursor reactions, the parachute, and dragging pets in and out of the house

Design agreed with the owner on 2026-09-17 (brainstorm answers: A, C, A, C). Go given 2026-09-17.

## 1. Lift it and it kicks; hold it up and it pulls out a parachute

- While a pet is in your hand (state `held`) it shows `surprised_dangle1_000` / `surprised_dangle2_000`, alternating every 150 ms: legs kicking, arms out, looking down. New poses `dangle1`, `dangle2` in `web/pets.js` `setPose`, rendered into every species sheet at yaw 0 for moods happy and surprised (`tools/sprites/render_sprites.py --poses dangle1,dangle2 --yaws 0 --moods happy,surprised`).
- After 1.2 s in the hand, or as soon as the pet is more than 60 px above its floor, the parachute opens: a `fun.Overlay` window above the pet holding one of three chute frames (`assets/sprites/_props/parachute_{L,C,R}.png`, a real three.js canopy with striped gores and lines to the pet's shoulders, rendered by `tools/sprites/sprite.html?prop=parachute&sway=-1|0|1&size=256`). It follows the pet while dragged and sways.
- On release with the chute open and the pet above the floor: state `float`. It sinks 3 px a tick, drifts sideways with the sway, legs relaxed (`happy_dangle*`), lands with the usual squash, the chute closes, and it says one of its `land` lines ("Nailed it.", "Again."). Released low or before the chute opened: today's fall.
- The chute frames are composed at pet size × 2. Nothing else about `held` changes (the menu's Tickle and Rename still work on a dropped pet).

## 2. Spin the cursor around it and it gets dizzy

- Every tick while the pet is visible and the cursor is within 2.6 × size of its centre, the pet accumulates the signed angle the cursor sweeps around it. More than two and a half turns (900°) within 2 s, in one direction, means dizzy. A slow circle or a straight pass adds nothing.
- Dizzy (state `dizzy`, 3.2 s): mood `dizzy` in `pets.js` (spiral eyes as tube spirals, a wavy mouth, brows askew, head tilted), rendered as `dizzy_idle_{000,060,300}`, `dizzy_squash_000`, `dizzy_stretch_000` for each species. The face turns 060/000/300 while the body staggers ±4 px, then a squash and a flop, then up with "Whoa." Three stars circle its head the whole time: a `fun.Overlay` above the pet with 12 Pillow-drawn star frames (the stars on top of the real face, as chosen).
- Dizzy works in every visible state except in the hand, inside, hidden, behind the curtain, and mid-play (say nothing then). It sets any errand aside the way a tickle does and carries on after. Cooldown 25 s per pet.

## 3. Drag pets into and out of the house

- Into: on a drop (release after a move) whose cursor lands inside the house's window box (closed: `x, y, size`; open: the new `open_box` and `rooms` boxes the house writes to `household/house.json` in `tell()`), the pet lands, then walks in: `go_inside(room, 15 min)` with the room under the cursor when the house is open, else `living`. A drop from high with the chute open floats down first, then walks in.
- Out: a press on a pet drawn in an open room (`draw_open` records each pet's box in `self.pet_boxes`) starts a pet drag instead of a house drag: an `Overlay` ghost of that pet follows the cursor. On release outside the house the house writes `plans/house-out-<pid>.json` with `{"out": true, "x": drop_x, "y": drop_y}`; `Pet.called_out()` returns the drop point and `come_out(at=(x, y))` places the pet there: on the floor at that x, or floating down under the chute when dropped high. Released back over the house, the ghost vanishes and nothing changes.

## 4. Faster reactions, two levels, anywhere on the screen

- `KeyWatch` already counts every key and click on the whole screen. `reactions()` now has two bars: a nod (`react_to("notice")`, no line, at most every `NOTICE_EVERY`) at 7 keys in 2 s or 5 clicks in 2 s; the full reaction with the line at 15 keys in 5 s or 15 clicks in 10 s. Undo and save runs are unchanged.
- The cheer and easy cooldowns stay household-wide.

## 5. Visible on the menu, on the site, in the harness

- A new panel page `Cursor tricks ›` under Do: three tiles that do the thing now (Dizzy, Parachute: it hops up and floats down, Into the house) with tips that say the gesture ("Or spin your cursor around it fast.").
- `tools/build_skills.py` gains three notices (lift, spin, drop on the house). README sections for each. The routine, reacts and desk clips are untouched.
- Harness part 1: dangle frames while held; the chute opens after the hold and the float lands; the angle accumulator turns dizzy on a fast circle and not on a slow one; dizzy frames and stars; a drop on the house box walks in; `called_out` with a point comes out there; the two bars (7 keys → nod only, 15 keys in 5 s → line). Part 2: a real drag of a pet onto the real house (SendInput) when the PC is untouched. Everything existing must stay green.
