# Ninetales Wallpapers 0.5.2a1

A prerelease of the GTK wallpaper browser and supervisor for Hyprland with
Caelestia. Includes native media playback, a community scene-renderer adapter,
Workshop monitoring and an experimental official Windows renderer through Proton.

## New in this version

- Fix Steam Play without a companion request: execute the original Steam launch
  command instead of rejecting it. A real child-process regression test checks
  argument handling and exit-status propagation.
- Distinguish native playback from Steam-owned official playback in the interface.
- Save official-renderer startup output and early wrapper errors for diagnosis.

- Verified selection of the current desktop Xwayland display for Steam launches.
- A backed-up user-local Steam launcher repair, without changing X server permissions.
- A Caelestia QML extension that restores icon search paths for private Qt builds;
  eight representative installed icons successfully resolve and decode.

- Steam-managed official-renderer sessions through a one-time launch option.
- Cached Steam playtime display; the application never modifies recorded playtime.
- Startup playback, with an installed default project on first official use.
- Settings pages for General, Playback, Steam, Library and Diagnostics.
- Spanish, English, French and Portuguese interfaces, with immediate language changes.
- A user-local GitHub CLI installation and browser-authentication helper.

## Installation

Extract a source archive to a permanent folder, install the documented runtime
dependencies, then run `python3 install.py`. Complete the one-time launch option
shown in Settings → Steam before using Steam-managed playback. See `README.md`,
`docs/proton.md` and `docs/steam.md`. Archives do not bundle Python, Qt, Quickshell,
Proton, Wallpaper Engine or wallpaper content.

## Verification and limits

The 64 Python tests pass, including Steam request lifecycle, prefix isolation,
translation completeness and placeholder checks. Real FFmpeg encoding to two FIFOs
and decoding through two Qt Multimedia players passed. Six C++ assertions cover
the community renderer geometry helper.

A private-display GUI test is supplied and configured in CI; the local sandbox
prevents creating its D-Bus / X11 sockets, so it has not run successfully here.
Official renderer playback through Steam and changes to account-side playtime
have not been verified end to end in a live session. The capture bridge is
software-heavy, capped at 30 FPS, mirrors selected displays and does not forward
pointer interaction. Native playback remains an alternative. No general
cross-distribution or full Windows feature compatibility is claimed.

SHA-256 checksums are supplied in `SHA256SUMS`. No proprietary executables,
Workshop content, user state, credentials or character art are distributed.
