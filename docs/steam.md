# Steam launch ownership and recorded playtime

Running `wallpaper64.exe` directly through Proton does not establish a Steam-owned
launch lifecycle. This project supports a Steam launch-option wrapper that stays
alive while your installed official renderer runs. It does not simulate playtime,
change a Steam database or use another application's Steamworks identity to report
fake activity. Wallpaper Engine must be owned and installed on the active account.

## One-time setup

1. Open Ninetales Wallpapers → **Settings → Steam**.
2. Copy the generated launch option. It looks like:

   ```text
   /home/YOUR_USER/.local/bin/ninetales-wallpapers steam-wrapper -- %command%
   ```

   Use the exact generated option; paths containing spaces are quoted for you.
3. Click **Open Steam properties**, or open Wallpaper Engine's properties from
   your Steam library, and paste the option into **Launch Options**.
4. Close the properties window so Steam saves it. Use **Check integration** in the
   app to detect the saved option. Existing custom options are never overwritten
   automatically; review them when replacing the field.
5. Stop any already-running Wallpaper Engine session in Steam. In the app, choose
   **Official · Proton**, enable **Launch through Steam**, then apply a wallpaper.

The app requests `steam://rungameid/431960`. Steam runs the wrapper as the launch
process for that application, and the wrapper starts the detected genuine renderer
through Proton on the private display. The received `%command%` is required as
part of the wrapper invocation; the wrapper substitutes its own renderer startup
for the Windows launcher UI. No proprietary files are patched or redistributed.

Leave this launch option installed when using the companion app. Pressing Play
in Steam without an active request from the companion app does not start a
wallpaper; open the companion app to create the request. Remove the launch option
to restore Steam's ordinary Wallpaper Engine launcher behavior.

## Startup and lifetime

**Start wallpaper when opening the app** restores the selected wallpaper. If there
is no selection, the official mode chooses an installed default project (Deep Space
when present). An incomplete Steam setup opens the Steam settings page. Startup at
login can be enabled separately.

Closing the library window leaves wallpaper playback running. **Static wallpaper**
ends the wallpaper session and restores Caelestia. Steam's Stop action also ends
its wrapper and the app restores the static wallpaper. A stale request, unrelated
process PID or previous launch ID cannot acknowledge a new render session.
The session cannot show a replacement background until decoded frames arrive.

## What the time display means

Settings reads the cached `Playtime` minutes for application 431960 from Steam's
active-account local preferences. That value can lag behind a running session and
is not a live stopwatch. The app never writes playtime or claims that an AppID
environment variable alone counts hours. Steam controls account-side recording and
synchronization; compare its library before and after a completed renderer session
when validating your setup. This full account-side test has not yet been performed
in the current restricted development environment.

Disabling **Launch through Steam** uses direct Proton execution. Native playback
also remains available. Neither mode is presented as guaranteed Steam playtime
tracking. Native / direct playback does not need the wrapper launch option.

References: Valve's [per-game launch options](https://help.steampowered.com/en/faqs/view/7D01-D2DD-D75E-2955),
[wrapper example](https://help.steampowered.com/en/faqs/view/145A-FE54-F37B-278A),
[Proton runtime options](https://github.com/ValveSoftware/Proton#runtime-config-options),
and Wallpaper Engine's [official controls](https://help.wallpaperengine.io/en/functionality/cli.html).
