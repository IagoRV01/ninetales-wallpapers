"""Experimental Proton -> private X11 window -> native Wayland background bridge.

Never captures the user's display. Every child, prefix and stream belongs to this bridge.
"""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import re
import select
import secrets
import shutil
import signal
import subprocess
import tempfile
import threading
import time

from . import core, proton


class Bridge:
    def __init__(self, on_ready=None):
        self.on_ready = on_ready
        self.frame_error = None
        self.running = True
        self.pause_requested = False
        self.paused = False
        self.children = []
        self.env = None
        self.found = None
        self.root = core.HOME / '.local/share/ninetales-wallpapers/proton'
        self.prefix = self.root / 'compatdata'

    def launch(self, argv, **kwargs):
        process = subprocess.Popen(argv, close_fds=True, **kwargs)
        self.children.append(process)
        return process

    def sleep(self, seconds):
        until = time.monotonic() + seconds
        while self.running and time.monotonic() < until:
            time.sleep(0.1)
        if not self.running:
            raise InterruptedError('Bridge stopped')

    def control(self, *args):
        p = self.launch(proton.command(self.found, '-control', *args), env=self.env,
                        cwd=proton.engine_cwd(self.found))
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.terminate()
            raise ValueError('El motor oficial no responde al control.')
        if p.returncode:
            raise ValueError('El motor oficial rechazó el comando de control.')

    def seed_prefix(self):
        if (self.prefix / 'pfx').is_dir():
            return
        # Preserve DOS drive symlinks; never follow the Z: mapping into the host.
        seed = next((p / 'steamapps/compatdata/431960' for p in core.steam_libraries()
                     if (p / 'steamapps/compatdata/431960/pfx').is_dir()), None)
        self.root.mkdir(parents=True, exist_ok=True)
        if seed:
            with tempfile.TemporaryDirectory(prefix='seed-', dir=self.root) as temp:
                staging = Path(temp) / 'compatdata'
                staging.mkdir()
                shutil.copytree(seed / 'pfx', staging / 'pfx', symlinks=True)
                for name in ('version', 'tracked_files', 'config_info'):
                    if (seed / name).is_file():
                        shutil.copy2(seed / name, staging / name)
                # A failed/interrupted copy cannot become the active prefix.
                if self.prefix.exists():
                    self.prefix.rmdir()
                staging.rename(self.prefix)
        else:
            self.prefix.mkdir(parents=True, exist_ok=True)

    def cleanup(self):
        # Wine may detach from the parent process group. Only address our private prefix.
        if self.env and self.found:
            wineserver = Path(self.found['proton']).parent / 'files/bin/wineserver'
            if wineserver.is_file():
                try:
                    subprocess.run([str(wineserver), '-k'], env=self.env, timeout=3,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except (OSError, subprocess.TimeoutExpired):
                    pass
        for child in reversed(self.children):
            if child.poll() is None:
                try:
                    child.send_signal(signal.SIGCONT)
                    child.terminate()
                    child.wait(timeout=1)
                except (ProcessLookupError, subprocess.TimeoutExpired):
                    try:
                        child.kill()
                        child.wait(timeout=1)
                    except (ProcessLookupError, subprocess.TimeoutExpired):
                        pass

    def run(self):
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / 'bridge.lock').open('w') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError('Ya hay un puente Proton activo.')
            for sig in (signal.SIGTERM, signal.SIGINT):
                signal.signal(sig, lambda *_: setattr(self, 'running', False))
            signal.signal(signal.SIGUSR1, lambda *_: setattr(self, 'pause_requested', True))
            signal.signal(signal.SIGUSR2, lambda *_: setattr(self, 'pause_requested', False))
            try:
                self.play()
            finally:
                self.cleanup()

    def play(self):
        config = core.load_config()
        self.found = proton.validate(config)
        wall = core.wallpaper_from_path(Path(config['selection']['path']))
        screens = [s for s in core.monitors() if config.get('output', '*') in ('*', s['name'])]
        if not screens:
            raise ValueError('No hay monitores disponibles.')
        # A single private render is mirrored to the selected outputs; no desktop capture.
        width = max(int(s['width']) for s in screens)
        height = max(int(s['height']) for s in screens)
        width += width % 2
        height += height % 2
        fps = min(int(config.get('fps', 30)), 30)
        self.seed_prefix()
        with tempfile.TemporaryDirectory(prefix='nw-proton-') as temporary:
            temp = Path(temporary)
            authority = temp / 'Xauthority'
            authority.touch(mode=0o600)
            cookie = secrets.token_hex(16)
            # A wildcard-family Xauthority record permits Xvfb's dynamically allocated display.
            import struct
            def field(data):
                return struct.pack('>H', len(data)) + data
            authority.write_bytes(struct.pack('>H', 65535) + field(b'') + field(b'') +
                                  field(b'MIT-MAGIC-COOKIE-1') + field(bytes.fromhex(cookie)))
            read_fd, write_fd = os.pipe()
            try:
                xvfb = self.launch(['Xvfb', '-displayfd', str(write_fd), '-screen', '0',
                                    f'{width}x{height}x24', '-noreset', '-nolisten', 'tcp', '-auth', str(authority)],
                                   pass_fds=(write_fd,))
                os.close(write_fd)
                write_fd = -1
                if not select.select([read_fd], [], [], 10)[0]:
                    raise ValueError('Xvfb no inició una pantalla virtual.')
                number = os.read(read_fd, 64).decode().strip()
                if not number.isdigit():
                    raise ValueError('Xvfb devolvió una pantalla no válida.')
            finally:
                os.close(read_fd)
                if write_fd >= 0:
                    os.close(write_fd)
            # Keep the same server cookie and add the now-known display number
            # for clients whose Xauthority lookup requires an exact number.
            authority.write_bytes(struct.pack('>H', 65535) + field(b'') + field(number.encode()) +
                                  field(b'MIT-MAGIC-COOKIE-1') + field(bytes.fromhex(cookie)))
            display = ':' + number
            self.env = proton.environment(self.found, display, authority, self.prefix)
            self.launch(proton.command(self.found, '-silent'), env=self.env,
                        cwd=proton.engine_cwd(self.found))
            title = 'NinetalesWallpaper-' + secrets.token_hex(8)
            window = None
            deadline = time.monotonic() + 100
            next_open = time.monotonic() + 8
            while self.running and time.monotonic() < deadline:
                if xvfb.poll() is not None:
                    raise ValueError('La pantalla virtual se cerró.')
                if time.monotonic() >= next_open:
                    self.launch(proton.open_command(self.found, wall, title, width, height),
                                env=self.env, cwd=proton.engine_cwd(self.found))
                    next_open = time.monotonic() + 15
                tree = subprocess.run(['xwininfo', '-display', display, '-root', '-tree'],
                                      env=self.env, capture_output=True, text=True, timeout=3)
                match = re.search(r'(0x[0-9a-fA-F]+) "' + re.escape(title) + r'"', tree.stdout)
                if match:
                    window = match.group(1)
                    break
                self.sleep(1)
            if not window:
                raise ValueError('Proton no abrió el fondo oficial. Consulta renderer.log; puedes volver al motor nativo.')
            self.control('mute' if config.get('muted', True) else 'unmute')
            streams = {s['name']: temp / f'wallpaper-{i}.ts' for i, s in enumerate(screens)}
            for fifo in streams.values():
                os.mkfifo(fifo, 0o600)
            # Encode once, then send an independent stream to each output decoder.
            player_env = core.qt_environment()
            player_env['NW_STREAMS'] = json.dumps({name: p.as_uri() for name, p in streams.items()})
            capture = self.launch(proton.capture_command(display, window, width, height, fps, streams.values()), env=self.env)
            player = self.launch([core.quickshell_path(), '--no-color', '-p', str(core.PROJECT / 'player/shell.qml')],
                                 env=player_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            def read_frames():
                for line in player.stdout:
                    print(line, end='', flush=True)
                    if 'NW_ERROR:' in line:
                        self.frame_error = line.split('NW_ERROR:', 1)[1].strip()
                    if self.on_ready and 'NW_READY:' in line:
                        output = line.split('NW_READY:', 1)[1].strip()
                        if output in streams:
                            self.on_ready(output)
            threading.Thread(target=read_frames, daemon=True).start()
            while self.running:
                if self.frame_error:
                    raise ValueError(self.frame_error)
                for name, process in (('Xvfb', xvfb), ('captura', capture), ('reproductor', player)):
                    if process.poll() is not None:
                        raise ValueError(f'El proceso {name} se cerró ({process.returncode}).')
                if self.pause_requested != self.paused:
                    if self.pause_requested:
                        self.control('pause')
                        capture.send_signal(signal.SIGSTOP)
                    else:
                        capture.send_signal(signal.SIGCONT)
                        self.control('play')
                    self.paused = self.pause_requested
                self.sleep(0.25)


def main():
    try:
        Bridge().run()
    except InterruptedError:
        pass
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print('NW_ERROR:' + str(error), flush=True)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
