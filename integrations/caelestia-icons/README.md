# Private Qt icon search-path repair

Some private Qt / Quickshell installations initialize their icon theme search paths
with only the Qt resource directory (`:/icons`). Selecting Mint-Y-Purple alone is
then insufficient: installed icons can still appear as missing-image tiles.

This small QML extension initializes QIcon with the user's and system's standard
icon directories. It preserves the chosen theme, includes `/usr/share/pixmaps`,
and supplies Papirus (when installed) or hicolor as a fallback. Importing the
module affects only the Caelestia process; no preload library or global Qt plugin
path is injected into Steam or child applications.

The desktop repair helper builds it with the same private Qt SDK as Caelestia,
verifies actual icon decoding in a temporary import tree, then atomically installs
the shared library and adds one import to the shell. Existing files are backed up.
The source and module definition are distributed; generated binaries are not.

```bash
python3 scripts/repair-desktop.py
```

The SDK is read from `NW_QT_PREFIX` or the existing
`~/.local/state/caelestia-mint/qt-prefix`. A C++ compiler and that SDK's headers / moc
are required. Rebuild after changing the Qt installation. No login session or
display server is restarted. The helper can repair Steam alone without building
the icon extension:

```bash
python3 scripts/repair-desktop.py --steam-only
```
