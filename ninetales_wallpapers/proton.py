"""Discovery and command planning for the optional, experimental Windows backend."""
from __future__ import annotations

import os
from pathlib import Path
import shutil

from . import core


def windows_path(path):
    return 'Z:' + str(Path(path).resolve()).replace('/', '\\')


def discover(config=None, libraries=None):
    conf = core.load_config() if config is None else config
    libraries = core.steam_libraries() if libraries is None else libraries
    executables = [Path(conf['official_exe']).expanduser()] if conf.get('official_exe') else []
    for engine in core.engine_directories(libraries):
        executables += [engine / 'distribution/wallpaper64.exe', engine / 'wallpaper64.exe']
    runners = [Path(conf['proton_path']).expanduser()] if conf.get('proton_path') else []
    for library in libraries:
        common = library / 'steamapps/common'
        runners += [common / 'Proton - Experimental/proton']
        runners += sorted(common.glob('Proton */proton'), reverse=True)
        runners += sorted((library / 'compatibilitytools.d').glob('*/proton'), reverse=True)
    steam = next((p for p in libraries if (p / 'steam.sh').is_file()), libraries[0] if libraries else None)
    return dict(exe=next((str(p.resolve()) for p in executables if p.is_file()), ''),
                proton=next((str(p.resolve()) for p in runners if p.is_file() and os.access(p, os.X_OK)), ''),
                steam=str(steam or ''),
                dependencies={name: shutil.which(name) or '' for name in ('Xvfb', 'xauth', 'xwininfo', 'ffmpeg')})


def validate(config=None):
    found = discover(config)
    missing = [name for name, path in found['dependencies'].items() if not path]
    if not found['exe']:
        missing.append('Wallpaper Engine de Steam (wallpaper64.exe)')
    if not found['proton']:
        missing.append('Proton de Steam')
    if missing:
        raise ValueError('Motor oficial: falta ' + ', '.join(missing) + '. Consulta docs/proton.md.')
    core.qt_environment()
    core.quickshell_path()
    return found


def environment(found, display, authority, prefix):
    env = dict(os.environ)
    for key in ('QT_PLUGIN_PATH', 'QML_IMPORT_PATH', 'QML2_IMPORT_PATH', 'QT_QPA_PLATFORMTHEME',
                'WAYLAND_DISPLAY', 'WINEPREFIX', 'WINESERVER', 'WINELOADER', 'LD_PRELOAD'):
        env.pop(key, None)
    env.update(DISPLAY=display, XAUTHORITY=str(authority), WINEPREFIX=str(prefix / 'pfx'),
               STEAM_COMPAT_DATA_PATH=str(prefix), STEAM_COMPAT_CLIENT_INSTALL_PATH=found['steam'],
               SteamAppId='431960', SteamGameId='431960', STEAM_COMPAT_APP_ID='431960',
               PROTON_USE_WINED3D='1', LIBGL_ALWAYS_SOFTWARE='1', PROTON_NO_ESYNC='1', PROTON_NO_FSYNC='1',
               WINEDLLOVERRIDES='winewayland.drv=d', WINEDEBUG='-all')
    return env


def engine_cwd(found):
    directory = Path(found['exe']).parent
    return directory.parent if directory.name == 'distribution' else directory


def command(found, *args):
    # argv is never passed through a shell. In particular, Workshop paths are data.
    return [found['proton'], 'run', found['exe'], *args]


def open_command(found, wall, title, width, height):
    source = Path(wall.path) / 'project.json' if Path(wall.path).is_dir() else Path(wall.path)
    return command(found, '-control', 'openWallpaper', '-file', windows_path(source),
                   '-playInWindow', title, '-width', str(width), '-height', str(height), '-borderless')


def capture_command(display, window, width, height, fps, fifos):
    if not isinstance(window, str) or not window.startswith('0x'):
        raise ValueError('Invalid capture window')
    if not 1 <= int(fps) <= 60 or not 1 <= width <= 16384 or not 1 <= height <= 16384:
        raise ValueError('Invalid capture dimensions or framerate')
    targets = '|'.join('[f=mpegts:onfail=abort]' + str(p) for p in fifos)
    if not targets:
        raise ValueError('No capture streams')
    return ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'warning', '-y',
            '-f', 'x11grab', '-draw_mouse', '0', '-framerate', str(fps),
            '-video_size', f'{width}x{height}', '-window_id', window, '-i', display,
            '-an', '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'zerolatency',
            '-pix_fmt', 'yuv420p', '-g', str(fps), '-bf', '0',
            '-map', '0:v:0', '-f', 'tee', targets]
