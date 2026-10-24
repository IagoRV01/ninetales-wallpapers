#!/usr/bin/env python3
"""Retirar únicamente los cambios del gestor; conservar fondos y recursos."""
from pathlib import Path
import os
import re
import shutil
import signal
import time

from ninetales_wallpapers import core

core.save_config(selection=None, autostart=False)
status = core.status()
pid = status.get('pid')
if isinstance(pid, int) and pid > 1:
    process = Path('/proc') / str(pid)
    try:
        args = (process / 'cmdline').read_bytes().split(b'\0')
        if b'ninetales_wallpapers' in args and b'daemon' in args and process.stat().st_uid == os.getuid():
            os.kill(pid, signal.SIGTERM)
            time.sleep(1)
    except (OSError, ProcessLookupError):
        pass
backup = core.STATE_DIR / 'backups' / ('desinstalar-' + str(time.time_ns()))
backup.mkdir(parents=True)
background = core.HOME / '.config/quickshell/caelestia/modules/background/Background.qml'
source = background.read_text()
if 'NINETALES_NATIVE_WALLPAPER' in source:
    shutil.copy2(background, backup / 'Background.qml')
    source = re.sub(r'        // NINETALES_NATIVE_WALLPAPER:.*?(?=        screen: modelData)', '', source, flags=re.S)
    source = source.replace('WlrLayershell.layer: win.effectiveWallpaperEnabled ?', 'WlrLayershell.layer: contentItem.Config.background.wallpaperEnabled ?')
    source = source.replace('color: win.effectiveWallpaperEnabled ?', 'color: contentItem.Config.background.wallpaperEnabled ?')
    source = source.replace('active: win.effectiveWallpaperEnabled', 'active: Config.background.wallpaperEnabled')
    if 'FileView {' not in source:
        source = source.replace('import Quickshell.Io\n', '')
    background.write_text(source)
user = core.HOME / '.config/caelestia/hypr-user.lua'
source = user.read_text()
if '-- NINETALES_WALLPAPERS_BEGIN' in source:
    shutil.copy2(user, backup / 'hypr-user.lua')
    source = re.sub(r'\n-- NINETALES_WALLPAPERS_BEGIN\n.*?-- NINETALES_WALLPAPERS_END\n', '\n', source, flags=re.S)
    user.write_text(source)
for file in (core.HOME / '.local/share/applications/io.github.iago.NinetalesWallpapers.desktop',
             core.HOME / '.local/bin/ninetales-wallpapers'):
    if file.exists():
        shutil.copy2(file, backup / file.name)
        file.unlink()
print('Gestor retirado. Se conservan el proyecto, tus fondos, los recursos y el motor de escenas.')
print('Copia de los archivos retirados:', backup)
