from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import time

HOME = Path.home()
CONFIG_DIR = Path(os.environ.get('XDG_CONFIG_HOME', HOME / '.config')) / 'ninetales-wallpapers'
STATE_DIR = Path(os.environ.get('XDG_STATE_HOME', HOME / '.local/state')) / 'ninetales-wallpapers'
CONFIG = CONFIG_DIR / 'config.json'
STATUS = STATE_DIR / 'runtime.json'
PROJECT = Path(__file__).resolve().parent.parent
MEDIA = {'.mp4', '.webm', '.mkv', '.mov', '.m4v', '.avi'}
IMAGES = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}
DEFAULTS = dict(selection=None, output='*', fps=30, muted=True, scaling='fill',
                manual_paused=False, pause_fullscreen=True, pause_battery=False,
                autostart=True, library_paths=[], files=[], generation=0, backend='proton', language='auto', steam_tracking=True, steam_on_open=True,
                auto_mute=True, login_avatar='', login_wallpaper='')


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def load_config():
    value = read_json(CONFIG, {})
    return {**DEFAULTS, **value} if isinstance(value, dict) else dict(DEFAULTS)


def save_config(**changes):
    conf = load_config()
    conf.update(changes)
    atomic_json(CONFIG, conf)
    return conf


def status():
    state = read_json(STATUS, {})
    if not isinstance(state, dict):
        state = {}
    if time.time() * 1000 - state.get('heartbeat', 0) > 15000:
        return dict(active=False, status='detenido', detail='El gestor de fondos no está en ejecución.')
    return state


def parse_vdf(text: str):
    """Leer KeyValues de Steam sin tratar sus cadenas como código."""
    tokens = re.findall(r'"(?:\\.|[^"\\])*"|[{}]|//[^\n]*', text)
    tokens = [t for t in tokens if not t.startswith('//')]
    index = 0

    def string(t):
        if not t.startswith('"'):
            raise ValueError('KeyValues no válido')
        return t[1:-1].replace('\\"', '"').replace('\\\\', '\\')

    def obj(nested=False):
        nonlocal index
        result = {}
        while index < len(tokens):
            token = tokens[index]
            index += 1
            if token == '}':
                if not nested:
                    raise ValueError('Llave inesperada')
                return result
            key = string(token)
            if index == len(tokens):
                raise ValueError('Falta un valor')
            token = tokens[index]
            index += 1
            result[key] = obj(True) if token == '{' else string(token)
        if nested:
            raise ValueError('Falta cerrar una llave')
        return result
    return obj()


def steam_libraries(home: Path = HOME):
    candidates = [home / '.local/share/Steam', home / '.steam/steam',
                  home / '.var/app/com.valvesoftware.Steam/.local/share/Steam',
                  home / '.var/app/com.valvesoftware.Steam/data/Steam',
                  home / 'snap/steam/common/.local/share/Steam']
    result = set()
    for path in candidates:
        if not path.is_dir():
            continue
        result.add(path.resolve())
        try:
            folders = parse_vdf((path / 'steamapps/libraryfolders.vdf').read_text()).get('libraryfolders', {})
            for key, value in folders.items():
                if key.isdigit():
                    value = value.get('path', '') if isinstance(value, dict) else value
                    if not isinstance(value, str) or not value:
                        continue
                    library = Path(value).expanduser()
                    if library.is_dir():
                        result.add(library.resolve())
        except (OSError, ValueError, AttributeError):
            pass
    return sorted(result)


def engine_directories(libraries=None):
    result = set()
    for library in steam_libraries() if libraries is None else libraries:
        dirs = ['wallpaper_engine', 'Wallpaper Engine']
        try:
            manifest = parse_vdf((library / 'steamapps/appmanifest_431960.acf').read_text())
            installed = manifest.get('AppState', {}).get('installdir')
            if installed:
                dirs.insert(0, installed)
        except (OSError, ValueError):
            pass
        for directory in dirs:
            root = library / 'steamapps/common' / directory
            if root.is_dir():
                result.add(root.resolve())
    return sorted(result)


def find_assets(libraries=None):
    configured = load_config().get('assets_dir')
    if configured and Path(configured).is_dir():
        return Path(configured).resolve()
    for root in engine_directories(libraries):
        if (root / 'assets').is_dir():
            return (root / 'assets').resolve()
    return None


def project_file(root: Path, filename: str):
    """Los metadatos de un fondo no pueden señalar fuera de su carpeta."""
    path = (root / filename).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('El proyecto apunta fuera de su carpeta: ' + filename)
    return path


@dataclass
class Wallpaper:
    path: str
    title: str
    kind: str
    media: str = ''
    preview: str = ''
    workshop_id: str = ''

    def as_dict(self):
        return {**asdict(self), 'media_uri': Path(self.media).as_uri() if self.media else ''}


def wallpaper_from_path(path: Path):
    path = path.expanduser().resolve()
    if path.is_file() and path.name == 'project.json':
        path = path.parent
    if path.is_dir():
        project = read_json(path / 'project.json', None)
        if not isinstance(project, dict):
            raise ValueError('No contiene un project.json de Wallpaper Engine.')
        kind = str(project.get('type', '')).lower()
        # Los ejemplos antiguos de Wallpaper Engine pueden omitir el tipo.
        if not project.get('type'):
            suffix = Path(str(project.get('file', ''))).suffix.lower()
            kind = 'scene' if suffix == '.json' else 'web' if suffix in ('.html', '.htm') else 'video' if suffix in MEDIA else ''
        if kind not in ('video', 'scene', 'web'):
            raise ValueError('Tipo de proyecto no compatible: ' + kind)
        media = project_file(path, str(project.get('file', '')))
        if kind == 'video' and not media.is_file():
            raise ValueError('Falta el vídeo del proyecto.')
        preview = project_file(path, str(project.get('preview', 'preview.jpg')))
        return Wallpaper(str(path), str(project.get('title') or path.name), kind,
                         str(media) if kind == 'video' else '', str(preview) if preview.is_file() else '',
                         path.name if path.name.isdigit() else '')
    if not path.is_file():
        raise ValueError('El archivo no existe.')
    suffix = path.suffix.lower()
    kind = 'video' if suffix in MEDIA else 'gif' if suffix == '.gif' else 'image' if suffix in IMAGES else ''
    if not kind:
        raise ValueError('Elige un proyecto de Wallpaper Engine, vídeo, GIF o imagen.')
    return Wallpaper(str(path), path.stem, kind, str(path), str(path) if kind != 'video' else '')


def initial_wallpaper(libraries=None):
    """Use an installed default project for the first official-engine launch."""
    for engine in engine_directories(libraries):
        folder = engine / 'projects/defaultprojects'
        candidates = [folder / 'deep_space/project.json', *sorted(folder.glob('*/project.json'))]
        for path in candidates:
            try:
                return wallpaper_from_path(path)
            except (OSError, ValueError):
                continue
    return None


def scan_library(config=None, libraries=None):
    conf = load_config() if config is None else config
    libraries = steam_libraries() if libraries is None else libraries
    paths = []
    for library in libraries:
        paths.extend((library / 'steamapps/workshop/content/431960').glob('*/project.json'))
    for engine in engine_directories(libraries):
        for group in ('defaultprojects', 'myprojects'):
            paths.extend((engine / 'projects' / group).glob('*/project.json'))
    folders = [HOME / 'Pictures/Wallpapers', *map(Path, conf.get('library_paths', []))]
    for folder in folders:
        if not folder.is_dir():
            continue
        if (folder / 'project.json').is_file():
            paths.append(folder)
            continue
        # Sólo las carpetas añadidas; no recorrer Steam ni todo el disco por accidente.
        for root, dirs, files in os.walk(folder, followlinks=False):
            if len(Path(root).relative_to(folder).parts) >= 3:
                dirs[:] = []
            if 'project.json' in files:
                paths.append(Path(root))
                dirs[:] = []
            else:
                paths.extend(Path(root) / f for f in files if Path(f).suffix.lower() in MEDIA | IMAGES | {'.gif'})
            if len(paths) >= 10000:
                break
    paths.extend(map(Path, conf.get('files', [])))
    found, errors = {}, []
    for path in paths:
        try:
            wall = wallpaper_from_path(path)
            found[wall.path] = wall
        except (ValueError, OSError) as error:
            errors.append(f'{path}: {error}')
    return sorted(found.values(), key=lambda w: w.title.casefold()), errors


def library_revision(wallpapers):
    """Detectar cambios sin reconstruir la galería cada vez que se sondea Steam."""
    result = []
    for wall in wallpapers:
        preview_stamp = 0
        try:
            if wall.preview:
                preview_stamp = Path(wall.preview).stat().st_mtime_ns
        except OSError:
            pass
        result.append((wall.path, wall.title, wall.kind, wall.media, wall.preview, preview_stamp))
    return tuple(result)


def workshop_status(libraries=None):
    """Leer el estado local de Steam; nunca tratar descargas parciales como fondos."""
    libraries = steam_libraries() if libraries is None else libraries
    installed, pending = set(), set()
    queue_state = 'pending'
    newest_log = 0
    for library in libraries:
        workshop = library / 'steamapps/workshop'
        try:
            manifest = parse_vdf((workshop / 'appworkshop_431960.acf').read_text()).get('AppWorkshop', {})
        except (OSError, ValueError):
            manifest = {}
        content = workshop / 'content/431960'
        complete = {p.parent.name for p in content.glob('*/project.json')}
        installed.update(complete)
        needs_download = manifest.get('NeedsDownload') == '1' or manifest.get('NeedsUpdate') == '1'
        if needs_download:
            details = manifest.get('WorkshopItemDetails', {})
            if isinstance(details, dict):
                pending.update(set(details) - complete)
            pending.update(p.name for p in (workshop / 'downloads/431960').glob('*') if p.is_dir() and p.name not in complete)
            if not pending:
                pending.add('unknown')
        log = library / 'logs/workshop_log.txt'
        try:
            stamp = log.stat().st_mtime_ns
            if stamp < newest_log:
                continue
            with log.open('rb') as inp:
                inp.seek(max(0, log.stat().st_size - 131072))
                lines = inp.read().decode(errors='replace').splitlines()
            mode = 'pending'
            for line in lines:
                if '[AppID 431960]' not in line:
                    continue
                if 'Starting Workshop download job' in line:
                    mode = 'downloading'
                elif 'Update canceled:' in line or 'Download paused' in line:
                    mode = 'paused'
                elif 'Workshop download finished' in line:
                    mode = 'pending'
            queue_state, newest_log = mode, stamp
        except OSError:
            pass
    return dict(installed=len(installed), pending=len(pending - installed),
                queue=queue_state if pending - installed else 'idle')


def open_steam(section='workshop'):
    urls = {'workshop': 'steam://openurl/https://steamcommunity.com/app/431960/workshop/',
            'wallpaper-engine': 'steam://rungameid/431960',
            'properties': 'steam://gameproperties/431960',
            'downloads': 'steam://open/downloads'}
    if section not in urls:
        raise ValueError('Sección de Steam no válida.')
    launcher = HOME / '.local/bin/steam'
    if not launcher.is_file() or not os.access(launcher, os.X_OK):
        found = shutil.which('steam')
        if not found and Path('/usr/games/steam').is_file():
            found = '/usr/games/steam'
        if not found:
            raise ValueError('No se encuentra Steam. Ábrelo desde tu lanzador de aplicaciones.')
        launcher = Path(found)
    from .desktop import desktop_environment
    env = desktop_environment()
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with (STATE_DIR / 'steam-launch.log').open('a') as log:
        subprocess.Popen([str(launcher), urls[section]], stdout=log, stderr=log, env=env,
                         start_new_session=True, close_fds=True)


def renderer_path():
    for path in (HOME / '.local/bin/linux-wallpaperengine',):
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    return shutil.which('linux-wallpaperengine')


def quickshell_path():
    binary = os.environ.get('NW_QUICKSHELL') or shutil.which('qs')
    if not binary or not Path(binary).is_file():
        raise ValueError('Quickshell no está instalado; define NW_QUICKSHELL si está fuera de PATH.')
    return binary


def qt_environment():
    env = dict(os.environ)
    env.pop('QT_QPA_PLATFORMTHEME', None)
    if env.get('NW_STEAM_BRIDGE'):
        for key in ('LD_PRELOAD', 'LD_LIBRARY_PATH'):
            env.pop(key, None)
    configured = os.environ.get('NW_QT_PREFIX')
    if not configured:
        try:
            configured = (HOME / '.local/state/caelestia-mint/qt-prefix').read_text().strip()
        except OSError:
            pass
    if configured:
        qt = Path(configured).expanduser()
        if not (qt / 'qml/QtMultimedia').is_dir():
            raise ValueError('QtMultimedia no está instalado en el prefijo Qt configurado.')
        env['QML_IMPORT_PATH'] = str(qt / 'qml')
        env['QT_PLUGIN_PATH'] = str(qt / 'plugins')
    # Without a private prefix, Quickshell uses its own system Qt search paths.
    env['NW_CONFIG'] = str(CONFIG)
    quickshell_path()
    return env


def hypr_json(command, default):
    try:
        result = subprocess.run(['hyprctl', '-j', command], capture_output=True, text=True, timeout=2)
        return json.loads(result.stdout) if result.returncode == 0 else default
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return default


def monitors():
    return hypr_json('monitors', [])


def scene_command(wallpaper: Wallpaper, config, outputs, assets: Path | None, binary=None):
    binary = binary or renderer_path()
    if not binary:
        raise ValueError('Falta el motor de escenas. Pulsa «Instalar motor de escenas».')
    if not assets:
        raise ValueError('Instala Wallpaper Engine desde Steam para disponer de sus recursos (assets).')
    fps = int(config.get('fps', 30))
    if fps not in (15, 24, 30, 60):
        raise ValueError('FPS no válido.')
    scaling = config.get('scaling', 'fill')
    if scaling not in ('fill', 'fit', 'stretch'):
        raise ValueError('Ajuste de imagen no válido.')
    command = [binary, '--assets-dir', str(assets), '--fps', str(fps),
               '--layer', 'background', '--no-fullscreen-pause']
    if config.get('muted', True):
        command.append('--silent')
    for output in outputs:
        command.extend(['--screen-root', output, '--bg', wallpaper.path, '--scaling', scaling])
    if not outputs:
        raise ValueError('No hay monitores Wayland disponibles.')
    return command


def ensure_daemon():
    session = os.environ.get('HYPRLAND_INSTANCE_SIGNATURE')
    if not session or not os.environ.get('WAYLAND_DISPLAY'):
        raise ValueError('Abre el gestor dentro de tu sesión de Hyprland.')
    # Dejar que el supervisor de una sesión anterior cierre sus reproductores.
    from . import __version__
    stopping = False
    for _ in range(36):
        current = status()
        if current.get('status') == 'detenido':
            break
        if current.get('session') == session:
            if current.get('version') == __version__:
                return
            if not stopping:
                pid = current.get('pid')
                if not isinstance(pid, int) or pid <= 1:
                    raise ValueError('No se puede identificar el gestor anterior.')
                proc = Path('/proc') / str(pid)
                try:
                    argv = (proc / 'cmdline').read_bytes().split(b'\0')
                    if proc.stat().st_uid != os.getuid() or b'ninetales_wallpapers' not in argv or b'daemon' not in argv:
                        raise ValueError('El PID anterior no pertenece al gestor de fondos.')
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    break
                stopping = True
        time.sleep(0.5)
    else:
        raise ValueError('El gestor de la sesión anterior todavía se está cerrando. Prueba de nuevo en unos segundos.')
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with (STATE_DIR / 'daemon.log').open('a') as log:
        subprocess.Popen([str(HOME / '.local/bin/ninetales-wallpapers'), 'daemon'],
                         stdout=log, stderr=log, start_new_session=True,
                         cwd=HOME, close_fds=True)


def apply(path: str, **settings):
    wall = wallpaper_from_path(Path(path))
    config = {**load_config(), **settings}
    backend = config.get('backend', 'native')
    if backend not in ('native', 'proton'):
        raise ValueError('Motor no válido.')
    if backend == 'proton':
        from .proton import validate
        validate(config)
        if config.get('steam_tracking', True):
            from .steam_integration import validate as validate_steam
            validate_steam()
    elif wall.kind in ('scene', 'web'):
        scene_command(wall, config, ['comprobacion'], find_assets())
    else:
        qt_environment()
    save_config(selection=wall.as_dict(), manual_paused=False, generation=time.time_ns(), **settings)
    ensure_daemon()
    return wall
