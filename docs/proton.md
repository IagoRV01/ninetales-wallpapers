# Experimental official renderer through Proton

This option invokes the Windows `wallpaper64.exe` from your own Steam installation.
It is not an official Linux port. The bridge has unit coverage and its stream has
been decoded successfully through Qt Multimedia, and a complete live-desktop run with
the Snowpoint City - Eevee scene has now been verified on the development system. A successful dependency check is
not a successful playback test.

## Setup

1. Install Steam and purchase / install Wallpaper Engine. Let all downloads finish.
2. Install Proton Experimental from Steam's Tools library. Start Wallpaper Engine
   through Steam once so its Windows prerequisites and prefix can be initialized.
3. On Mint / Ubuntu, install the capture dependencies:

   ```bash
   sudo apt-get --no-remove --no-install-recommends install xvfb xauth x11-utils ffmpeg
   ```

4. Close and reopen Ninetales Wallpapers after updating its code. Run
   `ninetales-wallpapers doctor` and check `motor_oficial` for executable paths.
5. Complete **Settings → Steam** using [steam.md](steam.md). Select the official
   renderer, choose a wallpaper and apply. Disable **Launch through Steam** only
   if you want direct Proton execution without a playtime guarantee.
   The first start may take several minutes while a separate prefix is prepared.

The official renderer is the default for fresh installations. The native backend remains available in the same menu. Selecting it and applying
again closes the bridge and returns to native playback. Missing official-backend
dependencies are reported before the saved wallpaper selection is changed.

If discovery misses a custom installation, add absolute `official_exe` and
`proton_path` strings to the application's `config.json`. `proton_path` points at
the executable `proton` script, not its directory. Restart playback after editing.

## How it works

- One bridge holds a lock for its private Proton prefix. If Steam has an existing
  Wallpaper Engine prefix, a separate copy is seeded once. DOS drive symlinks are
  copied as links rather than followed. The Steam prefix is not modified.
- Xvfb allocates a private display with cookie authentication and TCP disabled.
  The bridge removes the Wayland display variable from its Windows environment.
- Proton starts the installed renderer. Its documented `openWallpaper` control
  opens a uniquely named, borderless window at the selected output resolution.
- FFmpeg captures the dedicated virtual viewport, including Wine-rendered child windows. One H.264 encoder writes independent
  MPEG-TS FIFOs for each selected output. Qt Multimedia decodes those streams into
  Quickshell Wayland background surfaces. The user's desktop is never captured.
- Readiness is reported only when a video frame arrives. Caelestia keeps its static
  wallpaper until that report, and returns on timeout or failure.
- Pause sends the official pause/play control and pauses/resumes the capture.
  Shutdown stops children and addresses Wine's server only for the private prefix.

See the upstream [command line documentation](https://help.wallpaperengine.io/en/functionality/cli.html)
for the renderer control interface.

## Current limits

- Xvfb uses WineD3D rather than assuming Vulkan support. Rendering can fall back to
  software. Software H.264 encoding adds latency, CPU use and a small quality loss.
- Capture is capped at 30 FPS even if the GUI requests 60 FPS.
- Selected outputs mirror the same content; independent per-monitor projects and
  pointer interaction are not implemented.
- No promise of Windows scene, web, codec, audio visualizer or Steamworks parity.
  Some projects may show a black window, require Windows components, or fail.
- Audio, if enabled, comes from the official renderer. The Wayland stream is silent.
- A newly created prefix without Steam's prerequisites may need additional setup.
- The copied prefix occupies additional disk space and persists across runs.
- The proprietary program may still write its own installation settings or logs;
  a separate prefix does not isolate files inside the shared Steam installation.
- The application rejects executable/application project types. Treat community
  wallpaper content as software and choose projects you trust.

## Troubleshooting

Run `ninetales-wallpapers doctor`, then inspect
`~/.local/state/ninetales-wallpapers/renderer.log`. A missing Xvfb entry needs the
package above. A missing executable means Steam has not installed Wallpaper
Engine in a recognized library. A missing Proton entry needs a compatibility tool
installed through Steam. If a Windows window never appears, select the native
backend; do not remove or edit Steam's prefix in an attempt to repair the bridge.

An inactive background after an error is intentional: Caelestia's wallpaper is
kept visible. No automatic crash loop or repeated Windows restart is attempted.

## Installed application layout and startup checks

In the tested Steam installation, the executable was under `distribution/` while
its assets were in the parent folder. Running that file in place left HLSL shaders
and materials unresolved and caused a WineD3D crash. The bridge now assembles a
private application directory with an exact local executable copy and links to the
installed resources. Its own configuration controls framerate and leaves automatic
fullscreen pausing to our supervisor. Steam's installation is not modified.

Main startup uses Proton's `run` verb. Commands targeting that existing renderer
use `runinprefix`; using the game-launch verb for short controls could wait for the
whole session and incorrectly report a control timeout. Xauthority and stream files
are retained until their owning processes have exited.

Before starting the visible layer, the bridge checks the wallpaper window and
private viewport. A black wallpaper window is rejected even if a Windows crash
dialog makes the rest of the viewport nonblack. Diagnostic PNGs are saved in user
state, never in the release archives. No real desktop or other application is captured.
