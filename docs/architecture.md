# Architecture

`core.py` owns atomic configuration, Steam KeyValues parsing, library discovery,
validated project metadata, backend command construction and supervisor startup.
Metadata paths must stay within the project directory, including resolved
symlinks. Subprocess commands use argument arrays rather than shell interpolation.

`gui.py` is a GTK 3 library browser. A worker scans the library every five seconds.
Metadata revisions avoid replacing the gallery on every poll. Steam handles actual
Workshop downloads; the GUI observes completed content and queue metadata.

`daemon.py` holds a user-state lock and supervises one selected playback backend.
It watches the owning Hyprland instance, output changes, optional pause conditions
and changes to Caelestia's selected static wallpaper. Configuration changes restart
playback; pause changes do not. An unsuccessful player is not restarted in a loop.
Upgrades gracefully replace an older supervisor when the application next applies
a wallpaper in the same session.

Native media uses `player/shell.qml` and `MediaWallpaper.qml`. Scene and web projects
use an external linux-wallpaperengine installation. `proton.py` discovers the
Windows renderer / Proton and constructs commands; `proton_bridge.py` implements
the private-display capture path described in [proton.md](proton.md).
`steam_integration.py` requests a genuine Steam launch, correlates the wrapper's
acknowledgement with a random short-lived request ID, and relays frame readiness
and pause / shutdown signals. The wrapper executes the detected official renderer;
it does not execute arbitrary command strings supplied by project metadata.

`i18n.py` loads one of four complete JSON catalogs. The UI uses Spanish message
IDs and named placeholders. Settings persist the language or use the system locale;
rebuilding the window applies a new language immediately. Error and supervisor
templates are localized when shown, while technical renderer logs stay unchanged.

Caelestia's patched background reads a runtime heartbeat and ready-output list.
It makes only the wallpaper surface transparent after a player is ready for that
output. A stale heartbeat restores the static wallpaper within 15 seconds. Shell
widgets and borders remain part of Caelestia. Interactive pointer forwarding is
not supplied by the Proton bridge.

## Community renderer geometry patch

Some scene models declare full-resolution dimensions while the first sampled
texture is a lower-resolution effect mask. Upstream `CImage::getSize()` could use
that texture's size, rendering an animated patch in the middle of the wallpaper.
`patch-renderer.py` prioritizes explicit object dimensions, then positive declared
model dimensions when autosizing is disabled, then texture dimensions. Six C++
assertions exercise the helper. Fresh builds patch source before compilation;
existing builds compile the affected object and link a replacement shared library
before atomically swapping it into place. Restart playback to load the new library.

## Boundaries

The project does not authenticate to Steam, bypass ownership, scrape Workshop or
redistribute renderer assets. It does not alter the display manager, login session
or OS package sources. Only the dependency/build helper invokes package management.
Source release archives use an explicit allowlist and contain no user state.
