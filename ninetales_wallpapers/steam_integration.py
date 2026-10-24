"""Steam-owned launch lifecycle for the user's official Wallpaper Engine renderer.

A Steam launch option runs our bridge as the game's wrapper. Merely setting an
AppID or running Proton directly is never described as Steam playtime tracking.
"""
from __future__ import annotations

import os
from pathlib import Path
import secrets
import shlex
import signal
import subprocess
import threading
import time

from . import core

REQUEST = core.STATE_DIR / 'steam-request.json'
RUNTIME = core.STATE_DIR / 'steam-bridge.json'
SESSION_ENV = ('WAYLAND_DISPLAY', 'HYPRLAND_INSTANCE_SIGNATURE', 'XDG_RUNTIME_DIR',
               'DISPLAY', 'DBUS_SESSION_BUS_ADDRESS', 'NW_QT_PREFIX', 'NW_QUICKSHELL')


def launch_options():
    return shlex.quote(str(core.HOME / '.local/bin/ninetales-wallpapers')) + ' steam-wrapper -- %command%'


def preferences():
    """Select the most-recent account, without exposing account names or credentials."""
    for library in core.steam_libraries():
        candidates = list((library / 'userdata').glob('*/config/localconfig.vdf'))
        if len(candidates) == 1:
            return candidates[0]
        try:
            users = core.parse_vdf((library / 'config/loginusers.vdf').read_text()).get('users', {})
            for account, data in users.items():
                if isinstance(data, dict) and data.get('MostRecent') == '1' and account.isdigit():
                    path = library / 'userdata' / str(int(account) - 76561197960265728) / 'config/localconfig.vdf'
                    if path.is_file():
                        return path
        except (OSError, ValueError, AttributeError):
            pass
    return None


def info():
    path = preferences()
    app = {}
    if path:
        try:
            data = core.parse_vdf(path.read_text())
            for key in ('UserLocalConfigStore', 'Software', 'Valve', 'Steam', 'apps', '431960'):
                data = next((v for k, v in data.items() if k.casefold() == key.casefold()), {})
            app = data
        except (OSError, ValueError, AttributeError):
            pass
    options = app.get('LaunchOptions', '')
    minutes = app.get('Playtime', app.get('playtime'))
    try:
        minutes = max(0, int(minutes)) if minutes is not None else None
    except (ValueError, TypeError):
        minutes = None
    return {'configured': options == launch_options(), 'launch_options': launch_options(),
            'playtime_minutes': minutes}


def validate():
    from . import proton
    proton.validate()
    if not info()['configured']:
        raise ValueError('Configura primero el inicio desde Steam en Ajustes → Steam.')


def bridge_signal(state, sig):
    pid = state.get('pid')
    if not isinstance(pid, int) or pid <= 1:
        return False
    proc = Path('/proc') / str(pid)
    try:
        argv = (proc / 'cmdline').read_bytes().split(b'\0')
        if proc.stat().st_uid != os.getuid() or b'ninetales_wallpapers' not in argv or b'steam-wrapper' not in argv:
            return False
        os.kill(pid, sig)
        return True
    except (OSError, ProcessLookupError):
        return False


def supervise():
    validate()
    request_id = secrets.token_hex(24)
    core.atomic_json(REQUEST, {'id': request_id, 'created': time.time(),
                              'environment': {key: os.environ[key] for key in SESSION_ENV if key in os.environ}})
    core.open_steam('wallpaper-engine')
    running = True
    paused = None

    def stop(*_):
        nonlocal running
        running = False

    def pause(sig, _):
        nonlocal paused
        paused = sig

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGUSR1, pause)
    signal.signal(signal.SIGUSR2, pause)
    ready = set()
    started = time.monotonic()
    connected = False
    try:
        while running:
            state = core.read_json(RUNTIME, {})
            if state.get('request_id') == request_id:
                connected = True
                if time.time() - state.get('heartbeat', 0) > 10:
                    raise ValueError('La sesión de Wallpaper Engine en Steam dejó de responder.')
                if state.get('error'):
                    raise ValueError(state['error'])
                if state.get('stopped'):
                    raise ValueError('Wallpaper Engine se cerró desde Steam.')
                for output in state.get('ready_outputs', []):
                    if output not in ready:
                        print('NW_READY:' + output, flush=True)
                        ready.add(output)
                if paused is not None:
                    bridge_signal(state, paused)
                    paused = None
            if not connected and time.monotonic() - started > 100:
                raise ValueError('Steam no inició la integración. Detén Wallpaper Engine en Steam, revisa sus opciones de lanzamiento y vuelve a aplicar.')
            time.sleep(0.5)
    finally:
        # Invalidate the request before stopping its wrapper; a delayed launch must not run it.
        if core.read_json(REQUEST, {}).get('id') == request_id:
            REQUEST.unlink(missing_ok=True)
        state = core.read_json(RUNTIME, {})
        if state.get('request_id') == request_id:
            bridge_signal(state, signal.SIGTERM)
            until = time.monotonic() + 12
            while time.monotonic() < until:
                final = core.read_json(RUNTIME, {})
                if final.get('request_id') != request_id or final.get('stopped'):
                    break
                time.sleep(0.2)


def wrapper(command):
    # Steam supplies its genuine launch command after '--'. We use the detected
    # official renderer instead of the Windows launcher UI; keep this wrapper alive
    # for the renderer lifetime so Steam owns the launch/process relationship.
    if not command or os.environ.get('SteamAppId') != '431960':
        raise ValueError('Abre Wallpaper Engine desde Steam con las opciones indicadas en Ajustes.')
    request = core.read_json(REQUEST, {})
    if not request.get('id') or not 0 <= time.time() - request.get('created', 0) < 180:
        raise ValueError('Abre primero Ninetales Wallpapers y aplica un fondo con el motor oficial.')
    environment = request.get('environment', {})
    for key in SESSION_ENV:
        if key in environment and isinstance(environment[key], str):
            os.environ[key] = environment[key]
    os.environ['NW_STEAM_BRIDGE'] = '1'
    runtime = os.environ.get('XDG_RUNTIME_DIR', '')
    session = os.environ.get('HYPRLAND_INSTANCE_SIGNATURE', '')
    if not runtime or not session or not (Path(runtime) / 'hypr' / session / '.socket.sock').is_socket():
        raise ValueError('La solicitud no pertenece a una sesión activa de Hyprland.')
    from .proton_bridge import Bridge
    state = {'request_id': request['id'], 'pid': os.getpid(), 'ready_outputs': [],
             'stopped': False, 'error': '', 'launch_source': 'steam'}
    lock = threading.Lock()
    finished = threading.Event()

    def ready(output):
        with lock:
            if output not in state['ready_outputs']:
                state['ready_outputs'].append(output)

    def publish():
        while not finished.is_set():
            with lock:
                core.atomic_json(RUNTIME, {**state, 'heartbeat': time.time()})
            finished.wait(1)

    thread = threading.Thread(target=publish, daemon=True)
    thread.start()
    try:
        Bridge(on_ready=ready).run()
    except InterruptedError:
        pass
    except Exception as error:
        state['error'] = str(error)
        raise
    finally:
        finished.set()
        thread.join(timeout=2)
        with lock:
            core.atomic_json(RUNTIME, {**state, 'stopped': True, 'heartbeat': time.time()})


def main():
    try:
        supervise()
    except (OSError, ValueError) as error:
        print('NW_ERROR:' + str(error), flush=True)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
