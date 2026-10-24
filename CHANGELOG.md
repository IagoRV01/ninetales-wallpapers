# Changelog

## 0.5.1a1 — 2026-10-24

- Resolve Steam's X11 display from the current Hyprland session's Xwayland process,
  verifying the connection before replacing inherited display / authentication values.
- Preserve failed-probe environments and ignore other users, other sessions and Xvfb.
- Repair the user-local Steam launcher and next-login activation environment.
- Add a scoped QML extension for private Qt icon search paths; verify icon decoding
  before installing it. No global preload or application icon replacement is used.

## 0.5.0a1 — 2026-10-24

- Add Steam-owned official-renderer sessions using a documented launch-option
  wrapper pattern; read cached Steam playtime without modifying it.
- Add startup playback and an installed default project for first official launch.
- Add a five-page settings window for language, playback, Steam, folders and diagnostics.
- Translate the interface into Spanish, English, French and Portuguese (143 messages).
- Add Steam lifecycle and translation tests, an optional private-display GUI check,
  and a GitHub CLI installation / browser-authentication helper.
- Keep direct Proton and native playback available. Steam-owned official rendering,
  account-side playtime updates and the GUI smoke test remain unverified in the
  restricted development session; this is still a prerelease.

## 0.4.0a1 — 2026-10-24

- Add an experimental official-renderer option using the installed Windows
  executable and Proton, alongside the native backend.
- Add a private-display capture bridge, separate prefix, output streams,
  startup checks and coordinated pause / cleanup.
- Replace stale supervisors on upgrade and support custom Qt / Quickshell paths.
- Prepare English documentation, tests, source archives and GitHub release tools.
- Official renderer playback remains unverified end to end; this is a prerelease.

## 0.3.0 — 2026-10-24

- Observe Workshop queues and completed projects; refresh the library automatically.
- Add a Steam Downloads action and paused-download guidance.
- Improve contrast in the primary playback action.

## 0.2.0 — 2026-10-24

- Simplify the GTK gallery and playback controls.
- Correct declared-model geometry in the external native scene renderer.
- Keep static wallpaper visible until the replacement layer is ready.

## 0.1.0 — 2026-10-24

- Initial personal-desktop integration: native media playback, community scene
  renderer, Steam library discovery, output controls and Caelestia startup.
