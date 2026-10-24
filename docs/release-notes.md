# Ninetales Wallpapers 0.5.0a1

A prerelease of the GTK wallpaper browser and supervisor for Hyprland with
Caelestia. Includes native media playback, a community scene-renderer adapter,
Workshop monitoring and an experimental official Windows renderer through Proton.

## New in this version

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

The 53 Python tests pass, including Steam request lifecycle, prefix isolation,
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
