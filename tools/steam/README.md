# Perchlings on Steam

What Steam gives us: reviews and discovery (Bongo Cat's 100k reviews did the marketing), a free-to-play listing with paid extras, and later the Community Market for tradeable hats. What it costs: the Steamworks fee (US$100 per app, refundable after $1,000 in sales), and a few days of forms.

## Owner's part (only the account holder can do these)
1. Go to partner.steamgames.com, create a Steamworks account with the business details, pay the app fee. Steam reviews the paperwork in a few days.
2. Create the app "Perchlings". Note the **App ID** and the **Depot ID** (Steam makes one depot by default).
3. Store page: paste the copy from `store-page.md`, upload the images from `assets/` (made by `build_assets.py`), set the price to Free, tags and categories as listed. Submit for review (a few days).
4. Send me the App ID and Depot ID. Never send a password or a token.

## My part
- `build_assets.py` renders every capsule and library image at Steam's exact sizes from the pet stills.
- `app_build.vdf` and `depot_build.vdf` are the upload recipe. Fill in the two IDs, then from a normal command prompt (no admin):
  ```
  steamcmd +login <steam user> +run_app_build "<repo>\tools\steam\app_build.vdf" +quit
  ```
  steamcmd is a portable zip from Valve; it asks for the account password and Steam Guard code in its own window. The first upload goes to the "default" branch; set it live in Steamworks > Builds.
- Launch options in Steamworks: executable `Perchlings.exe`, Windows only. The installer is not used on Steam; Steam installs the folder from `tools/build_exe.py` (the `dist/Perchlings` one-folder build), so the Steam build is the same files as the download.
- Later: Steam Inventory Service for tradeable hats (the Bongo Cat loop), and paid DLC for extra pets if the in-app shop isn't wanted there.

## Order of work
Store page and paperwork first (they take the longest), then the build. The app itself needs nothing Steam-specific to run.
