# Ninetales Wallpapers 0.6.0a1

Wallpaper audio now yields to music and videos in other applications. This
prerelease also adds a personal SDDM welcome screen with a glass panel, circular
profile picture, clock and session selector.

## New in this version

- Automatically mute only the wallpaper while other applications have active
  audio playback. Restore its sound after playback pauses or stops, without
  restarting the wallpaper. Manual mute is preserved.
- Enable or disable automatic muting in Settings → Playback. Audio-server and
  mute-control errors are shown in the playback status.
- Prepare a login wallpaper and profile picture in Settings → Login screen.
  Preview the theme with SDDM's test mode before applying it.
- Use silent videos/GIFs or static images on the welcome screen. Wallpaper Engine
  scene and web projects use their preview image; their renderers do not run
  before login.
- Install the optional SDDM theme explicitly with administrator privileges, with
  an integrity manifest, backup and rollback command. The installer does not
  restart SDDM or end the current desktop session.
- Include the new settings and messages in the Spanish, English, French and
  Portuguese app interfaces. The supplied welcome theme uses Spanish labels.

## Installation and updating

Extract a source archive to a permanent folder, install the runtime dependencies
listed in README.md, then run `python3 install.py`. Keep the source folder in
place: the launcher refers to it. Existing installations can update their source
checkout and reopen the app to load the new supervisor.

Automatic audio muting requires `pactl`, provided by `pulseaudio-utils` on
Ubuntu/Mint, and a working PulseAudio or PipeWire-Pulse session. The optional
welcome screen requires the existing display manager to be SDDM and uses the
system's Qt 5 QML modules. Its separate installer checks dependencies; the main
app installer does not activate or replace the login theme automatically.

## Verification and limits

- 91 Python tests pass locally, including audio ownership, mute restoration,
  manual-mute precedence, recycled stream IDs, login export, installer backups
  and idempotent release publishing with preserved version history.
- The installed SDDM loads the production theme in offscreen test mode. A
  synthetic backend verifies session selection, password clearing, failure and
  retry, with a rendered preview. This is not a real PAM login or GPU blur test.
- Real audio handoff in the desktop session and the video greeter decoder have
  not been verified in the restricted development environment. Audio detection
  uses playback-stream state rather than recording or measuring audio samples.
- The optional GTK/Xvfb settings and language smoke test is supplied in CI; the
  local sandbox does not allow its D-Bus/X11 sockets.

The official Wallpaper Engine renderer through Proton remains experimental and
was previously validated with one installed scene on the development system.
Its capture bridge is software-heavy, capped at 30 FPS, mirrors selected displays
and does not forward pointer interaction. Native playback remains available.

Archives contain source code, documentation and synthetic tests, with SHA-256
checksums in SHA256SUMS. They do not include personal avatars, wallpaper content,
Steam state, credentials, proprietary renderers, Qt, Python or Quickshell.
