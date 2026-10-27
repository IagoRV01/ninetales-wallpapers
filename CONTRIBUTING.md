# Contributing

Use Python 3.10 or newer. Runtime GUI dependencies are system PyGObject / GTK 3;
the core unit suite uses only Python's standard library.

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q ninetales_wallpapers install.py uninstall.py scripts
bash -n install-renderer.sh scripts/publish.sh
```

Do not upload Steam prefixes, registries, Workshop files, proprietary executables,
user configuration, logs containing personal paths, or character artwork. Small
synthetic metadata and media fixtures should be generated inside temporary folders.

Describe desktop versions and the backend when reporting playback bugs. Redact
private paths from diagnostics. Separate dependency discovery, renderer startup,
frame readiness and successful desktop presentation in test reports. Passing unit
tests is not evidence of working GPU / compositor integration.

With playback dependencies installed, `python3 scripts/test-stream.py` checks
real FFmpeg encoding, two independent FIFOs and two actual Qt video decoders
without a display or proprietary fixtures.

The optional GUI test uses a private Xvfb display and a temporary application state:

```bash
dbus-run-session -- /usr/bin/python3 scripts/test-gui.py
```

It requires PyGObject / GTK 3 and Xvfb, never starts Steam, and checks all six
settings pages and language switching. It is a separate CI job; socket-restricted
sandboxes cannot run it. Translation catalogs must have identical message IDs and
preserve named placeholders in all languages.

To check a prepared SDDM bundle without touching the login configuration:

```bash
python3 scripts/test-login.py /path/to/prepared/bundle --screenshot /tmp/login-preview.png
```

It uses the installed Qt 5 `sddm-greeter` in offscreen test mode, first with the
production models and then a synthetic authentication backend. It exercises
session selection, password clearing and retry and saves a rendered screenshot.
This does not verify a real PAM login or GPU-rendered blur. Test bundles and
screenshots can contain personal artwork: keep them outside the source tree.

Changes to subprocess management must preserve argv-based execution, private-prefix
cleanup, failover to static wallpaper and the absence of automatic restart loops.
Test affected lifecycle behavior before proposing renderer or supervisor changes.
