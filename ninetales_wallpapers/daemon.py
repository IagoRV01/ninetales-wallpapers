from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import sys
import threading
import time

from . import core, __version__


def layer_outputs(layers, pid):
    result = []

    def contains(value):
        if isinstance(value, dict):
            if value.get('pid') == pid and value.get('mapped', True):
                return True
            return any(contains(v) for v in value.values())
        return isinstance(value, list) and any(contains(v) for v in value)

    for output, data in layers.items():
        if contains(data):
            result.append(output)
    return result


def on_battery():
    sources = Path('/sys/class/power_supply')
    try:
        for source in sources.iterdir():
            if (source / 'type').read_text().strip() == 'Battery':
                if (source / 'status').read_text().strip() == 'Discharging':
                    return True
    except OSError:
        pass
    return False


def pause_reason(config, outputs, screens, active):
    if config.get('manual_paused'):
        return 'Pausado por ti'
    if config.get('pause_battery') and on_battery():
        return 'Pausado para ahorrar batería'
    selected = [s for s in screens if s.get('name') in outputs]
    if selected and all(s.get('dpmsStatus') is False for s in selected):
        return 'Pantalla apagada'
    if config.get('pause_fullscreen', True) and active.get('fullscreen', 0) >= 2:
        if any(s.get('id') == active.get('monitor') for s in selected):
            return 'Aplicación a pantalla completa'
    return ''


class Daemon:
    def __init__(self):
        self.child = None
        self.official = False
        self.launch_source = 'native'
        self.paused = False
        self.ready = set()
        self.events = queue.Queue()
        self.running = True
        self.current = None
        self.outputs = []
        self.title = ''
        self.started = 0
        self.failed = None
        self.startup_wallpaper = self.caelestia_wallpaper()
        self.state = dict(status='espera', detail='Selecciona un fondo.', active=False)
        self.session = os.environ.get('HYPRLAND_INSTANCE_SIGNATURE', '')

    def session_alive(self):
        runtime = os.environ.get('XDG_RUNTIME_DIR')
        return bool(runtime and self.session and
                    (Path(runtime) / 'hypr' / self.session / '.socket.sock').is_socket())

    @staticmethod
    def caelestia_wallpaper():
        try:
            return (core.HOME / '.local/state/caelestia/wallpaper/path.txt').read_text().strip()
        except OSError:
            return ''

    def publish(self):
        core.atomic_json(core.STATUS, {**self.state, 'heartbeat': time.time() * 1000,
                         'ready_outputs': sorted(self.ready), 'output': core.load_config().get('output', '*'),
                         'title': self.title, 'paused': self.paused, 'pid': os.getpid(),
                         'session': self.session, 'version': __version__, 'launch_source': self.launch_source})

    def stop_child(self):
        if self.child is not None:
            if self.child.poll() is None:
                try:
                    if self.paused:
                        os.killpg(self.child.pid, signal.SIGCONT)
                    if self.official:
                        self.child.terminate()
                    else:
                        os.killpg(self.child.pid, signal.SIGTERM)
                    self.child.wait(timeout=15 if self.official else 4)
                except subprocess.TimeoutExpired:
                    os.killpg(self.child.pid, signal.SIGKILL)
                    self.child.wait(timeout=2)
                except ProcessLookupError:
                    pass
            self.child = None
        self.paused = False
        self.ready.clear()
        self.state['active'] = False
        self.publish()

    def read_output(self, process):
        with (core.STATE_DIR / 'renderer.log').open('a') as log:
            for line in process.stdout:
                log.write(line)
                log.flush()
                if 'NW_READY:' in line:
                    self.events.put((process.pid, line.split('NW_READY:', 1)[1].strip()))
                elif 'NW_ERROR:' in line:
                    self.events.put((process.pid, '!error:' + line.split('NW_ERROR:', 1)[1].strip()))

    def start(self, config, screens):
        self.stop_child()
        self.ready.clear()
        wall = core.wallpaper_from_path(Path(config['selection']['path']))
        requested = config.get('output', '*')
        self.outputs = [s['name'] for s in screens if requested == '*' or s.get('name') == requested]
        if not self.outputs:
            raise ValueError('El monitor seleccionado no está conectado.')
        self.title = wall.title
        self.official = config.get('backend', 'native') == 'proton'
        self.launch_source = 'steam' if self.official and config.get('steam_tracking', True) else 'proton' if self.official else 'native'
        if self.official:
            from .proton import validate
            validate(config)
            if config.get('steam_tracking', True):
                from .steam_integration import validate as validate_steam
                validate_steam()
            module = 'steam_integration' if config.get('steam_tracking', True) else 'proton_bridge'
            command = [sys.executable, '-m', 'ninetales_wallpapers.' + module]
            env = dict(os.environ)
        elif wall.kind in ('scene', 'web'):
            command = core.scene_command(wall, config, self.outputs, core.find_assets())
            env = dict(os.environ)
            # Los plugins Qt privados de Caelestia no pertenecen a este motor.
            for key in ('QT_PLUGIN_PATH', 'QML_IMPORT_PATH', 'QML2_IMPORT_PATH', 'QT_QPA_PLATFORMTHEME'):
                env.pop(key, None)
        else:
            core.qt_environment()
            command = [core.quickshell_path(), '--no-color', '-p', str(core.PROJECT / 'player/shell.qml')]
            env = core.qt_environment()
        self.child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                      text=True, bufsize=1, start_new_session=True, env=env,
                                      cwd=core.HOME, close_fds=True)
        threading.Thread(target=self.read_output, args=(self.child,), daemon=True).start()
        self.started = time.monotonic()
        self.state = dict(status='cargando', detail='Preparando ' + wall.title + '…', active=False)
        self.failed = None
        self.startup_wallpaper = self.caelestia_wallpaper()
        self.publish()

    def run(self):
        core.STATE_DIR.mkdir(parents=True, exist_ok=True)
        with (core.STATE_DIR / 'daemon.lock').open('w') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return
            for sig in (signal.SIGTERM, signal.SIGINT):
                signal.signal(sig, lambda *_: setattr(self, 'running', False))
            last_publish = 0
            try:
                while self.running:
                    if not self.session_alive():
                        break
                    config = core.load_config()
                    screens = core.monitors() if config.get('selection') else []
                    outputs = tuple(s['name'] for s in screens if config.get('output', '*') in ('*', s['name']))
                    signature = json.dumps({k: config.get(k) for k in
                                           ('selection', 'output', 'fps', 'muted', 'scaling', 'generation', 'backend', 'official_exe', 'proton_path', 'steam_tracking')}, sort_keys=True) + repr(outputs)
                    if signature != self.current:
                        self.current = signature
                        self.failed = None
                        if config.get('selection'):
                            try:
                                self.start(config, screens)
                            except (OSError, ValueError) as error:
                                self.stop_child()
                                self.failed = signature
                                self.state = dict(status='error', detail=str(error), active=False)
                        else:
                            self.stop_child()
                            self.state = dict(status='espera', detail='Fondo de Caelestia activo.', active=False)
                    if self.child:
                        while not self.events.empty():
                            pid, output = self.events.get_nowait()
                            if self.child and pid == self.child.pid and output.startswith('!error:'):
                                self.stop_child()
                                self.failed = signature
                                self.state = dict(status='error', active=False, detail=output[7:])
                                self.publish()
                            if self.child and pid == self.child.pid and output in self.outputs:
                                self.ready.add(output)
                        if not self.child:
                            time.sleep(0.5)
                            continue
                        code = self.child.poll()
                        if code is not None:
                            self.stop_child()
                            self.failed = signature
                            self.state = dict(status='error', active=False,
                                              detail=f'El reproductor terminó ({code}). Se conserva el fondo de Caelestia. Consulta renderer.log.')
                        else:
                            # Hyprland sólo enumera una capa cuando ya hay una superficie presentada.
                            self.ready.update(layer_outputs(core.hypr_json('layers', {}), self.child.pid))
                            if not self.ready and time.monotonic() - self.started > (240 if self.official else 60):
                                self.stop_child()
                                self.failed = signature
                                self.state = dict(status='error', active=False,
                                                  detail='El reproductor no presentó un fondo a tiempo. Consulta renderer.log.')
                            else:
                                reason = pause_reason(config, self.outputs, screens, core.hypr_json('activewindow', {}))
                                if self.ready and bool(reason) != self.paused:
                                    try:
                                        if self.official:
                                            os.kill(self.child.pid, signal.SIGUSR1 if reason else signal.SIGUSR2)
                                        else:
                                            os.killpg(self.child.pid, signal.SIGSTOP if reason else signal.SIGCONT)
                                        self.paused = bool(reason)
                                    except ProcessLookupError:
                                        pass
                                self.state = dict(status='pausado' if self.paused else 'activo' if self.ready else 'cargando',
                                                  active=bool(self.ready), detail=reason or self.title)
                        # Elegir un fondo estático en Caelestia devuelve el control a la shell.
                        if self.child and self.caelestia_wallpaper() != self.startup_wallpaper:
                            core.save_config(selection=None)
                    if time.monotonic() - last_publish >= 2:
                        self.publish()
                        last_publish = time.monotonic()
                    time.sleep(0.5)
            finally:
                self.stop_child()
                self.state = dict(status='detenido', detail='Gestor detenido; fondo de Caelestia restaurado.', active=False)
                self.publish()
