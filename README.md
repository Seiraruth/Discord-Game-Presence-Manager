# Discord Presence Manager

Discord Presence Manager is a desktop tray app that lets you control what Discord displays as your current game/activity. It can force a selected game profile, apply custom Rich Presence fields, and optionally enrich status from Steam Rich Presence data.

## What the app does
- Runs in the system tray and manages Discord Rich Presence.
- Lets you **Force Game** from your configured game list.
- Can launch a fake executable name (`tools/dumb.exe`) so Discord detects the selected game executable name for testing/control scenarios.
- Supports optional Steam cookie integration to read status/group details from Steam Rich Presence.
- Provides Discord detectable-app sync to auto-fill missing `client_id` and executable mappings.

## Requirements
- Python 3.10+
- Discord desktop app running locally
- Windows is the primary supported platform (some code paths exist for macOS/Linux)
- Dependencies from `requirements.txt`

## Run from source
1. Clone this repository.
2. Create and activate a virtual environment.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create `.env` in the repository root (or let the app create a template) and define:
   ```env
   CLIENT_ID=YOUR_DISCORD_APPLICATION_CLIENT_ID
   ```
5. Start the app:
   ```bash
   python src/main.py
   ```

## `.env` / `CLIENT_ID` configuration
- `CLIENT_ID` is required.
- It must be a valid Discord Application Client ID you want to use as the default RPC app.
- If `CLIENT_ID` is missing, the app exits with a clear startup error instead of silently skipping RPC.

Optional variables:
- `UPDATE_INTERVAL` (seconds, default `10`)
- `STEAM_COOKIE`
- `TEST_RICH_URL`

## Force Game usage
1. Open tray menu.
2. Select **Force Game**.
3. Pick a configured game/profile.
4. The app updates Discord presence and (when executable data exists) launches a fake executable process name for Discord detection matching.
5. Use **Stop Current Presence** to stop forced mode and clear/idle according to settings.

## Steam cookie integration (high level)
- The app can retrieve a Steam cookie via Edge WebDriver flow.
- Cookie is stored in `.env` for reuse.
- Steam scraper uses that cookie to fetch Rich Presence text and party/group data for supported games.
- If Steam data is available, it is used to enrich Discord presence fields.

## Build / packaging
If you package this app (for example with PyInstaller), ensure:
- `tools/dumb.exe`, `tools/msedgedriver.exe`, `assets/`, `lang/`, and `config/` resources are included.
- `.env` is placed next to the executable or otherwise discoverable by runtime.

This repository currently focuses on source execution; packaging steps may vary by your build pipeline.

## Disclaimer about fake executable mode
The fake executable mode is intended for **Discord detection testing** and manual presence control workflows. Use responsibly and only in environments where this behavior is acceptable.

## New Force Game picker window
- By default, launching the app now opens a **Force Game** picker window immediately while still keeping tray support.
- You can search games quickly and click visual cards (with cover art when available) to force the activity.
- Double-click a card to force and minimize to tray.
- Tray **Force Game** now opens/focuses the same picker window.

### Cover image resolution and cache
Cover priority:
1. Cached local cover (`config/cache/game_art/`)
2. Steam CDN cover (when `steam_appid` exists)
3. SteamGridDB (optional)
4. Placeholder card with game title

Cache index is stored at `config/cache/game_art_index.json`.

### Optional SteamGridDB API key
You can configure artwork lookup with either:
- setting `steamgriddb_api_key` in app settings, or
- env var `STEAMGRIDDB_API_KEY`

If no key is present, the app still works and uses other cover sources/fallback placeholders.

### New relevant settings
`app_settings.json` now supports:
- `open_game_picker_on_startup` (default `true`)
- `minimize_to_tray_on_close` (default `true`)
- `remember_window_size` (default `true`)
- `show_recent_games_first` (default `true`)
- `enable_game_art_download` (default `true`)
- `steamgriddb_api_key` (default empty)
- `game_art_cache_days` (default `30`)

Set `open_game_picker_on_startup` to `false` to keep tray-only startup behavior.
