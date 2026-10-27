"""Duck only wallpaper playback streams while another application is audible."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import time

APP_ID = 'io.github.iago.NinetalesWallpapers'


def renderer_environment(env):
    pipewire = env.get('PIPEWIRE_PROPS', '').strip()
    if pipewire.startswith('{') and pipewire.endswith('}'):
        pipewire = pipewire[1:-1]
    return {**env,
            'PULSE_PROP': env.get('PULSE_PROP', '') + ' application.id=' + APP_ID,
            'PIPEWIRE_PROPS': '{ ' + pipewire + ' application.id="' + APP_ID + '" }'}


def descendant(pid, roots):
    """Follow parent IDs; a generic Wine/Steam process name is never enough."""
    seen = set()
    while pid > 1 and pid not in seen:
        if pid in roots:
            return True
        seen.add(pid)
        try:
            data = (Path('/proc') / str(pid) / 'stat').read_text()
            pid = int(data.rsplit(')', 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            break
    return False


def owned(stream, roots):
    props = stream.get('properties', {})
    if props.get('application.id') == APP_ID:
        return True
    try:
        return descendant(int(props.get('application.process.id', 0)), roots)
    except (ValueError, TypeError):
        return False


def audible(stream):
    if stream.get('corked', True) or stream.get('mute', False):
        return False
    if stream.get('properties', {}).get('media.role', '').lower() in ('event', 'notification'):
        return False
    return any(channel.get('value', 0) > 0 for channel in stream.get('volume', {}).values())


def identity(stream):
    props = stream.get('properties', {})
    return (stream.get('client'), props.get('application.process.id'), props.get('object.serial'))


class WallpaperAudio:
    def __init__(self):
        self.changed = {}
        self.hold_until = 0
        self.auto_muted = False
        self.error = ''

    def poll(self, config, roots):
        try:
            result = subprocess.run(['pactl', '--format=json', 'list', 'sink-inputs'],
                                    capture_output=True, text=True, timeout=2)
            if result.returncode:
                raise OSError('Audio server unavailable')
            streams = json.loads(result.stdout)
            if not isinstance(streams, list):
                raise ValueError('Invalid audio stream list')
            now = time.monotonic()
            mine = [stream for stream in streams if owned(stream, roots)]
            if any(audible(stream) for stream in streams if not owned(stream, roots)):
                self.hold_until = now + 1
            self.auto_muted = bool(config.get('auto_mute', True) and now < self.hold_until)
            current = {s['index']: identity(s) for s in mine}
            self.changed = {key: value for key, value in self.changed.items() if current.get(key) == value}
            failed = False
            for stream in mine:
                index = stream['index']
                mute = bool(config.get('muted', True) or self.auto_muted)
                # Never unmute a stream that was already muted by the user.
                if not mute and index not in self.changed:
                    continue
                if mute == stream.get('mute', False):
                    continue
                response = subprocess.run(['pactl', 'set-sink-input-mute', str(index), '1' if mute else '0'],
                                          capture_output=True, text=True, timeout=2)
                if response.returncode == 0:
                    if mute:
                        self.changed[index] = identity(stream)
                    else:
                        self.changed.pop(index, None)
                else:
                    failed = True
            self.error = 'No se ha podido cambiar el silencio del fondo.' if failed else ''
        except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, TypeError):
            self.error = 'No se puede comprobar el audio de otras aplicaciones.'

    def status(self):
        return {'auto_muted': self.auto_muted, 'audio_error': self.error}
