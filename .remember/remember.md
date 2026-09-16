# Handoff

## State
v0.22.0 is released (39 tricks, Effects shelf, size setting). Batch 2 (24 closet items + a Back shelf) is coded but NOT committed: web/pets.js, app/closet.json, app/shop.json, web/look-test.html, site/index.html, tools/sprites/render_wave.py. Its renders were running in the background (log: .render_wave.log; expect outfits/<id>_sheet.json with 23 frames for 24 items x 4 pets). Memory file project_perchlings.md has the full history.

## Next
1. User reports (2026-09-16): the house is gone and its right-click menu has no options; the panel still says "Pick five" in the Household tiles and on the tricks page (rename to "Picks"; five picks included, the rest bought via picks:all, never a cap on what a pet can do or wear). Check house.py startup (start_house_if_needed, claim_instance, house.json ts), log the house process, fix, add to tools/testrun.py.
2. When the wave render is complete: verify the sheets, run `python tools/testrun.py` (all parts), `tools/build_looktest.py` + `tools/build_site.py`, humanizer pass on site copy, bump VERSION to 0.23.0, commit, push (GCM browser sign-in may be needed), confirm the release via the GitHub API.
3. Batch 3: house styles (castle, cabin, spaceship) and a yard; then seasonal shelves and a pet maker.

## Context
- Never start a second headless Chrome on tools/sprites/_chrome-profile while a render runs (frames fail three times and the batch aborts).
- Never view live screen grabs (they capture the user's work windows); verify captures by pixel comparison instead.
- House style: no em dashes or exclamation marks in app/site prose, US spelling on the site, no competitor names on the site, humanizer before committing prose. Never handle GitHub tokens; pushes wait on the user's browser sign-in.
- Test pets run from the source tree with APPDATA pointed at .testrun/; kill stray pythonw perchling.py processes before a run.
