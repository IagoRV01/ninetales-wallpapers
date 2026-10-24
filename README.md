# Ninetales Wallpapers

Created and maintained by [IagoRV01](https://github.com/IagoRV01).

A GTK wallpaper library and playback supervisor for **Hyprland with Caelestia**.
Browse downloaded Wallpaper Engine projects, local videos, GIFs and images, choose
an output, and restore the last wallpaper when your desktop starts.

**Version 0.5.3a1 is a prerelease.** Native playback remains available.
The official Windows renderer through Proton is experimental: its
Wayland bridge has now been validated with the Snowpoint City - Eevee scene on
the Mint / Hyprland development system. Other projects and configurations may differ. This project is independent of
Wallpaper Engine, Valve, Hyprland and Caelestia.

## Features

- Searchable thumbnail gallery, type filters and a simple playback panel.
- Steam library discovery, including additional library drives.
- Workshop download status and automatic library refresh every five seconds.
- Native images, GIFs and videos through Qt Multimedia and Quickshell.
- Scene and web projects through the separately installed
  [linux-wallpaperengine](https://github.com/Almamu/linux-wallpaperengine) renderer.
- Official `wallpaper64.exe` through Proton and a private virtual display.
- Steam-managed launch lifecycle for the official renderer, with cached Steam playtime display.
- Settings for language, playback, Steam, library folders and diagnostics.
- Spanish, English, French and Portuguese interfaces; saved language choice or system detection.
- Output selection, fill/fit/stretch, mute, pause and startup restoration.
- Optional pauses for fullscreen applications, battery use or powered-off displays.
- Caelestia keeps its bars and widgets; its static wallpaper remains until the new
  player reports readiness and returns if the supervisor stops responding.

Project documentation is in English. Choose the interface language in **Settings → General**; the interface rebuilds immediately when the choice is saved.

## Backend support

| Content | Native backend | Official backend through Proton |
| --- | --- | --- |
| Images, GIFs, videos | Qt Multimedia / Qt Quick | Experimental capture bridge |
| Wallpaper Engine scenes | External community renderer; compatibility varies | Validated with one installed scene on the development system |
| Web wallpapers | External renderer; compatibility varies | Unverified, dependent on Proton and Windows components |
| Application / executable wallpapers | Rejected by the library | Rejected by the library |
| Multiple outputs | Native output surfaces | Same rendered content mirrored to selected outputs |
| Pointer interaction | Community renderer dependent | Not forwarded through the capture bridge |

Wallpaper Engine has no official Linux desktop version. Its Windows executable
cannot directly become a Wayland wallpaper surface. The experimental bridge
runs it on an isolated Xvfb display, captures its dedicated virtual viewport,
then displays the stream through native Wayland background layers. It uses
WineD3D and software encoding, caps capture at 30 FPS, and may use substantial
CPU. Fresh installations select the official backend with Steam-managed launching, as a Wallpaper Engine companion. Complete the one-time Steam setup before applying a wallpaper. The native backend remains available from the renderer selector and avoids the experimental capture path.

## Requirements

The integration was developed on Linux Mint 22.3 / Ubuntu 24.04, Hyprland 0.56.2
with Lua configuration, Caelestia 2.5.0, Quickshell 0.3.1 and Qt 6.11.2. Other
versions have not been validated.

- Python 3.10+, PyGObject and GTK 3.
- A running Hyprland session with `hyprctl` and `Hyprland` on PATH.
- Quickshell (`qs`) with the Qt Multimedia QML module built for the same Qt.
- The existing Caelestia background and `~/.config/caelestia/hypr-user.lua`.
- Steam and a legitimate Wallpaper Engine installation for proprietary projects
  and renderer assets. Neither is required to browse ordinary local media.

On Mint / Ubuntu, install the basic Python GUI dependencies with:

```bash
sudo apt-get --no-remove install python3 python3-gi gir1.2-gtk-3.0
```

Install compatible Hyprland, Caelestia, Quickshell and Qt separately. This project
does not install a compositor, modify your display manager, or replace your login
session. For private Qt installations, set `NW_QT_PREFIX=/path/to/qt`; for a custom
Quickshell executable, set `NW_QUICKSHELL=/path/to/qs`. The existing
`~/.local/state/caelestia-mint/qt-prefix` setup is also recognized. Without an
explicit Qt prefix, Quickshell uses its system Qt search paths.

## Install

Clone this repository or extract a release source archive to a permanent folder.
The launcher refers to that folder; do not delete it after installation.

```bash
cd ninetales-wallpapers
python3 install.py
ninetales-wallpapers doctor
ninetales-wallpapers gui
```

Add `~/.local/bin` to PATH if needed. The installer backs up affected files,
patches the supported Caelestia background, adds the application launcher and
**Super+Alt+W**, and registers startup restoration in the existing Lua user
configuration. It checks Hyprland configuration syntax and restores both modified
configuration files if that check fails. It requires the supported file layout;
review any existing customizations first. Reload Caelestia / Hyprland or log out
and back in to activate the integration.

For native scenes, build the external community renderer:

```bash
bash install-renderer.sh
```

This script downloads third-party source, installs build dependencies using
`sudo`, and compiles with two jobs by default (`NW_BUILD_JOBS` overrides it).
Package transactions use `--no-remove`. It also applies a tested local geometry
patch for projects whose first material texture is smaller than the declared
model. A previous renderer library is retained before replacement. See
[architecture](docs/architecture.md) and [third-party notices](THIRD_PARTY_NOTICES.md).

For the optional official backend, follow [the Proton setup](docs/proton.md).

## Steam Workshop

Open **Steam Workshop** in the app, subscribe to a wallpaper, and let Steam finish
its download. Subscribing is not an immediate local download: Steam can queue or
pause Workshop content. Use **Downloads** to resume it. Completed projects under
`steamapps/workshop/content/431960` appear automatically on the next library scan.
Temporary downloads are never treated as installed projects. Steam manages
subscriptions, ownership, authentication and downloads; this app does not use a
Steam password or download items through an unofficial API.

Additional local folders and media files can be added with **Add**. Changing your
static wallpaper in Caelestia returns wallpaper control to Caelestia.

## Settings and Steam playtime

Open the gear button for **General**, **Playback**, **Steam**, **Library** and
**Diagnostics**. Playback settings are validated and applied when saved; language
changes rebuild the window immediately. Removing a library folder does not delete
its files. Diagnostics show renderer discovery and offer access to local logs.

With **Launch through Steam** enabled for the official backend, the supervisor
asks Steam to launch application **431960**. A one-time launch option, shown with
copy and properties buttons in **Settings → Steam**, runs our wrapper for the
lifetime of the real official renderer. This gives Steam ownership of the launch
rather than assuming that setting an AppID environment variable records playtime.
Ordinary Play in Steam without a pending request passes through to Steam's original
launcher command. The companion app must select **Official · Proton** and apply a
wallpaper to use its background bridge; selecting Native does not record Steam
time merely because the launch option is installed. The interface displays the
active launch source and only displays Steam's cached recorded minutes; it never writes a
playtime counter. Account-side recording and synchronization are controlled by Steam
and remain outside this application's control. A live scene session was observed in Steam's tracked-process log and its cached time increased during testing.

When **Start wallpaper when opening the app** is enabled, opening the GUI restores
the selected wallpaper. On the first official-engine start, the installed default
Deep Space project is preferred if there is no selection. Setup must still be
completed in Steam. Closing the GUI leaves wallpaper playback running; use **Static
wallpaper** or Steam's Stop action to end that renderer session. Direct Proton
launching remains available by disabling **Launch through Steam**, without a
playtime-tracking guarantee. See [Steam integration](docs/steam.md).

## Command line

```bash
ninetales-wallpapers scan
ninetales-wallpapers doctor
ninetales-wallpapers apply /path/to/project --backend native --output eDP-1
ninetales-wallpapers apply /path/to/project --backend proton --fps 24
ninetales-wallpapers pause
ninetales-wallpapers stop
ninetales-wallpapers status
```

Settings live in `$XDG_CONFIG_HOME/ninetales-wallpapers/config.json` and runtime
state / logs in `$XDG_STATE_HOME/ninetales-wallpapers/` (standard home-directory
fallbacks apply). `renderer.log` contains player diagnostics. Configuration
includes local paths; review it before sharing. The experimental Proton prefix
is stored separately under `~/.local/share/ninetales-wallpapers/proton/`.

## Desktop repairs on Mint

If Steam reports that it cannot open X11 from a Hyprland session, the optional
repair helper installs a standalone user-local launcher that resolves the current
session's Xwayland display and authentication path. A candidate is used only if
an X11 connection succeeds. It does not guess `:0`, alter X server access control,
restart Xwayland, or reuse the renderer's private Xvfb display. It also imports
DISPLAY / XAUTHORITY with the existing desktop activation environment on the next
login. Connection probing uses `xdpyinfo` from `x11-utils`.

```bash
python3 scripts/repair-desktop.py --steam-only
```

To repair Caelestia's private-Qt icon lookup as well, run the helper without that
flag. This requires the matching Qt SDK and a C++ compiler. See
[integrations/caelestia-icons](integrations/caelestia-icons/README.md).
It verifies the module before installing it, backs up modified files, and adds
standard icon search paths inside Caelestia. No application icons are replaced
with hand-drawn images. Its standalone Steam launch diagnostic is stored at
`~/.local/state/steam-mint/last-launch.json` and contains routing metadata, not
cookies or credentials.

## Uninstall

```bash
python3 uninstall.py
```

The uninstaller removes this application's marked Caelestia / Hyprland changes,
launcher and desktop entry while retaining user wallpapers, source files, logs,
settings, renderer and Proton prefix. It backs up removed configuration. It is
intended for the same supported Caelestia layout as the installer.

## Development and releases

```bash
python3 -m unittest discover -s tests -v
python3 scripts/build-release.py
# Optional, with playback dependencies installed:
python3 scripts/test-stream.py
```

The release builder creates source `.tar.gz` and `.zip` archives and SHA-256
checksums in `dist/`. These are source distributions, not self-contained binaries.
No paid executables, Workshop projects, user settings, Steam data or character
sprites are included. See [CONTRIBUTING.md](CONTRIBUTING.md),
[CHANGELOG.md](CHANGELOG.md), and [release notes](docs/release-notes.md).

A GitHub Actions workflow runs the unit tests. A separate tag-triggered workflow
builds and publishes prerelease assets for `v0.5.3a1`. The local helper
`scripts/publish.sh` can create a public repository and initial prerelease using
an authenticated GitHub CLI; it never asks for a token on the command line.

On Mint / Ubuntu, `bash scripts/github-setup.sh --publish` can download the distro's
GitHub CLI package, extract it into the user account without sudo, open browser
login, configure Git credentials, and run the publication helper. It requires
network access and your interactive GitHub authorization; no password or token is
stored in this repository. The `workflow` OAuth scope is needed to push the included
GitHub Actions workflows. This helper creates a public repository in the authenticated
account if no origin exists; it never force-pushes.

## License and credits

Original project code is under the [MIT license](LICENSE). Dependencies and
wallpaper content retain their own licenses. No proprietary renderer or content
is redistributed. The name refers to a personal desktop theme; Pokémon and
Ninetales belong to their respective rights holders. No character artwork is
bundled. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Reference: Wallpaper Engine's [Linux support statement](https://help.wallpaperengine.io/en/functionality/linuxmacos.html)
and [documented command controls](https://help.wallpaperengine.io/en/functionality/cli.html).
