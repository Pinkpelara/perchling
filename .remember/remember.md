# Handoff

## State
v0.26.1 (2026-09-16, commit 1819c2a): the site and the app's longer lines rewritten in the voice the user asked for (explaining it to a friend over coffee; adults, not kids; rules in memory feedback_perchlings_site_voice.md). Before it v0.26.0 (0b558bc): the pet's panel carries everything (house page: bring out / open / decorate / style / everyone out / put away; breaks by kind, nap, dance, party, egg page), the house decorates with pictures and has its own card, pets drive the house via household/commands/house.json, reactions fire in more states with lower bars, dances run in sets, bedroom naps are rate-limited, lowercase owner names work. Site: routine.gif and breaks.gif rows, "one right-click away", demo page screenshots. Full test run + house checks green. Before it v0.25.0 (picks are owned, not capped) and the sales-page site (792c484, pushed this session).

## Next
1. If the user reports a line that still reads wrong, fix that line in site/index.html (or the bio in app/species/*.json) and push; do not restructure the page.
2. Batch 3 of the catalog: house styles (castle, cabin, spaceship) in web/house.js + render_house.py, and a yard; then seasonal shelves and a pet maker.
3. Owner-side blockers to keep raising: the Lemon Squeezy checkout link (set site.js buyUrl, demoAdopt false; the demo checkout hands out installers for $0), the Steamworks account (tools/steam/ is ready), a domain instead of pinkpelara.github.io.

## Context
- Run the app and tools with system Python 3.12 (AppData\Local\Programs\Python\Python312\python.exe); the shell's default python is 3.11 and lacks the libraries.
- Never start a second headless Chrome on tools/sprites/_chrome-profile while a render runs; renders take ~4 s/frame when the user's pets are running.
- Never view live screen grabs; verify captures by pixel comparison. Screenshots of my own test windows (panel, decorate dialog) are fine and feed site/img/demo via assets/sprites/_fit/_menu_home.png, _decorate.png, _menu_house.png.
- House style: no em dashes or exclamation marks in app/site prose, US spelling on the site, humanizer before committing prose; site copy follows docs/competitor-language.md; never handle GitHub tokens (pushes may wait on the user's browser sign-in; cached creds worked on 2026-09-16).
- Test pets run from source with APPDATA at .testrun/; kill stray pythonw perchling.py processes before a run. The user's real pets run from the installed exe with the real APPDATA; their one-copy mutexes are Perchlings-<id>-d0d48cdf. The user had put the house away; "Bring out the house" on any pet's panel brings it back.
