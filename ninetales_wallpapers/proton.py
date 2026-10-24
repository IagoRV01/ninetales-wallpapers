"""Discovery and command planning for the optional, experimental Windows backend."""
from __future__ import annotations

import os
import json
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
        executables += [engine / 'wallpaper64.exe', engine / 'distribution/wallpaper64.exe']
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


def prepare_application(found, config, directory):
    """Assemble the resource layout expected by an uninstalled Steam distribution.

    Steam's Windows launcher normally installs distribution executables beside
    assets. Running that executable inside distribution makes relative resources
    disappear. Use an exact local copy and resource links; never alter Steam files.
    """
    source = Path(found['exe'])
    if source.parent.name != 'distribution':
        return found
    engine = source.parent.parent
    if not (engine / 'assets/shaders/HLSL/dx11fallback.vert').is_file():
        raise ValueError('Faltan recursos de Wallpaper Engine. Verifica sus archivos en Steam.')
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / source.name
    if not target.is_file() or target.stat().st_size != source.stat().st_size or target.stat().st_mtime_ns != source.stat().st_mtime_ns:
        staged = directory / ('.' + source.name + '.new')
        shutil.copy2(source, staged)
        os.replace(staged, target)
    for name, origin in [('bin', source.parent / 'bin'), ('plugins', source.parent / 'plugins'),
                         *[(n, engine / n) for n in ('assets', 'projects', 'ui', 'locale', 'locales')]]:
        if not origin.is_dir():
            continue
        link = directory / name
        if link.is_symlink():
            if link.resolve() == origin.resolve():
                continue
            link.unlink()
        elif link.exists():
            raise ValueError('La carpeta del motor contiene un recurso no administrado: ' + name)
        link.symlink_to(origin.resolve(), target_is_directory=True)
    config_path = directory / 'config.json'
    data = core.read_json(config_path, None)
    if not isinstance(data, dict):
        data = core.read_json(engine / 'config.json', {})
    data['?installdirectory'] = windows_path(directory)
    user = data.setdefault('steamuser', {}).setdefault('general', {}).setdefault('user', {})
    user.update(fps=min(int(config.get('fps', 30)), 30), playbackfocus='run',
                playbackfullscreen='run', playbackmaximized='run', playbacksleep='run')
    core.atomic_json(config_path, data)
    return {**found, 'exe': str(target)}


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


def control_command(found, *args):
    # Controls address the existing Wine instance. Proton's game-launch verb adds
    # a Steam bootstrap whose lifetime can match the running renderer instead of
    # the short-lived control command. runinprefix invokes Wine directly.
    return [found['proton'], 'runinprefix', found['exe'], '-control', *args]


def open_command(found, wall, title, width, height):
    source = Path(wall.path) / 'project.json' if Path(wall.path).is_dir() else Path(wall.path)
    return control_command(found, 'openWallpaper', '-file', windows_path(source),
                   '-playInWindow', title, '-width', str(width), '-height', str(height), '-x', '0', '-y', '0', '-borderless')


def capture_environment(wine_env):
    # System capture tools must not load Steam runtime or Wine library overrides.
    env = dict(wine_env)
    for key in ('LD_PRELOAD', 'LD_LIBRARY_PATH', 'QT_PLUGIN_PATH', 'QML_IMPORT_PATH', 'QML2_IMPORT_PATH'):
        env.pop(key, None)
    return env


def capture_command(display, window, width, height, fps, fifos):
    if window is not None and (not isinstance(window, str) or not window.startswith('0x')):
        raise ValueError('Invalid capture window')
    if not 1 <= int(fps) <= 60 or not 1 <= width <= 16384 or not 1 <= height <= 16384:
        raise ValueError('Invalid capture dimensions or framerate')
    targets = '|'.join('[f=mpegts:onfail=abort]' + str(p) for p in fifos)
    if not targets:
        raise ValueError('No capture streams')
    window_args = ['-window_id', window] if window is not None else []
    return ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'warning', '-y',
            '-f', 'x11grab', '-draw_mouse', '0', '-framerate', str(fps),
            '-video_size', f'{width}x{height}', *window_args, '-i', display,
            '-an', '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'zerolatency',
            '-pix_fmt', 'yuv420p', '-g', str(fps), '-bf', '0',
            '-map', '0:v:0', '-f', 'tee', targets]
