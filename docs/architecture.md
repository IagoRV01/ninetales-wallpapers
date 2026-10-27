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

`audio.py` monitors sink-input state with `pactl --format=json`. Renderer
PulseAudio/PipeWire properties and verified process ancestry identify owned
streams. Only those streams are muted when other audible playback is present;
the supervisor restores only streams it actually changed, matching their client,
PID and object serial so reused sink-input indices are not unmuted accidentally.
It preserves manual muting, reports audio-server/control errors, and never
restarts the wallpaper for automatic audio changes.

`login.py` prepares private, self-contained SDDM bundles from validated library
metadata. Scenes/web projects export their preview; images/GIFs/videos are
copied, videos receive a poster, and profile pictures are decoded and cropped to
transparent circular PNGs. No user paths or artwork are added to source releases.
`integrations/sddm/theme` contains the original Qt 5 QML theme. Its production
adapter delegates authentication and session choice to SDDM; it does not store
credentials. The optional administrator installer verifies the bundle manifest,
backs up the previous theme and snippet, installs readable assets, and provides
rollback without restarting the display manager. `scripts/test-login.py` tests
the installed SDDM's real theme context and then exercises login failure/session
selection with a synthetic backend in offscreen mode.

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
redistribute renderer assets. It does not replace the display manager or login
session, or change OS package sources. The optional SDDM theme is activated only
by its separate administrator installer. That installer and the dependency/build
helper can install distribution dependencies.
Source release archives use an explicit allowlist and contain no user state.

## Official startup validation

The bridge resolves packaged executable layouts into a private runtime folder so
resource lookup matches the installed assets. Main startup and short IPC controls
use different Proton verbs (`run` and `runinprefix`). Native capture tools receive
a clean library environment, while Wine keeps its own runtime environment.

Startup saves diagnostics of the renderer window and its dedicated virtual screen.
It rejects black wallpaper output even if a crash dialog is visible on that private
screen. Capture includes the dedicated viewport's child windows, and readiness is
forwarded after actual decoded frames. Display credentials and FIFOs are removed
only after process shutdown. This path was validated with one live official scene;
it is still an experimental backend with project-dependent compatibility.
