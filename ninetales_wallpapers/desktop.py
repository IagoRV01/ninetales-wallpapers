"""Resolve Steam's real Xwayland environment without guessing a display number.

This file also works as a standalone user-local Steam launcher. It never changes
X server access control, reads authentication cookies, or selects another user's
server. The wallpaper renderer's private Xvfb environment is separate.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
import re
import shutil
import subprocess
import sys

QT_PRIVATE = ('QT_PLUGIN_PATH', 'QML_IMPORT_PATH', 'QML2_IMPORT_PATH', 'QT_QPA_PLATFORMTHEME')


def session_pid(env):
    runtime = env.get('XDG_RUNTIME_DIR')
    signature = env.get('HYPRLAND_INSTANCE_SIGNATURE')
    if not runtime or not signature or '/' in signature:
        return None
    try:
        value = (Path(runtime) / 'hypr' / signature / 'hyprland.lock').read_text().splitlines()[0]
        return int(value)
    except (OSError, ValueError, IndexError):
        return None


def xwayland_servers(env, proc_root=Path('/proc'), uid=None):
    uid = os.getuid() if uid is None else uid
    compositor = session_pid(env)
    servers = []
    try:
        processes = proc_root.iterdir()
        for process in processes:
            if not process.name.isdigit():
                continue
            try:
                if process.stat().st_uid != uid or (process / 'comm').read_text().strip() != 'Xwayland':
                    continue
                argv = [a.decode(errors='replace') for a in (process / 'cmdline').read_bytes().split(b'\0') if a]
                display = next((a for a in argv[1:] if re.fullmatch(r':\d+(?:\.\d+)?', a)), None)
                if not display:
                    continue
                values = {}
                for entry in (process / 'environ').read_bytes().split(b'\0'):
                    key, sep, value = entry.partition(b'=')
                    if sep and key in (b'WAYLAND_DISPLAY', b'HYPRLAND_INSTANCE_SIGNATURE'):
                        values[key.decode()] = value.decode(errors='replace')
                parent = next((int(line.split()[1]) for line in (process / 'status').read_text().splitlines()
                               if line.startswith('PPid:')), None)
                score = 0
                if compositor and parent == compositor:
                    score = 3
                elif env.get('HYPRLAND_INSTANCE_SIGNATURE') and values.get('HYPRLAND_INSTANCE_SIGNATURE') == env['HYPRLAND_INSTANCE_SIGNATURE']:
                    score = 3
                elif env.get('WAYLAND_DISPLAY') and values.get('WAYLAND_DISPLAY') == env['WAYLAND_DISPLAY']:
                    score = 2
                # An unscoped server can belong to another login of the same user.
                if not score:
                    continue
                authority = None
                if '-auth' in argv:
                    index = argv.index('-auth') + 1
                    if index < len(argv):
                        authority = argv[index]
                servers.append({'display': display, 'authority': authority, 'score': score})
            except (OSError, ValueError, IndexError):
                continue
    except OSError:
        pass
    return sorted(servers, key=lambda s: s['score'], reverse=True)


def display_works(env):
    probe = shutil.which('xdpyinfo')
    if not probe or not env.get('DISPLAY'):
        return False
    try:
        result = subprocess.run([probe, '-display', env['DISPLAY']], env=env, timeout=2,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def desktop_environment(environ=None, servers=None, probe=None):
    env = dict(os.environ if environ is None else environ)
    for key in QT_PRIVATE:
        env.pop(key, None)
    if not env.get('WAYLAND_DISPLAY') and not env.get('HYPRLAND_INSTANCE_SIGNATURE'):
        return env
    probe = display_works if probe is None else probe
    servers = xwayland_servers(env) if servers is None else servers
    # Prefer the compositor's own server over a stale DISPLAY inherited by a shell
    # or service. Try only authentication paths supplied by that server or session.
    for server in servers:
        authorities = [server['authority']] if server.get('authority') else [env.get('XAUTHORITY'), None]
        for authority in dict.fromkeys(authorities):
            candidate = dict(env, DISPLAY=server['display'])
            if authority:
                candidate['XAUTHORITY'] = authority
            else:
                candidate.pop('XAUTHORITY', None)
            if probe(candidate):
                return candidate
    # Preserve a working inherited display, including compositor-lazy Xwayland.
    if env.get('DISPLAY') and probe(env):
        return env
    # Failed probes (for example, a restricted tool sandbox) are not proof that a
    # different X server or an authentication override should be chosen.
    return env


def main(argv=None):
    original = dict(os.environ)
    servers = xwayland_servers(original) if original.get('WAYLAND_DISPLAY') or original.get('HYPRLAND_INSTANCE_SIGNATURE') else []
    env = desktop_environment(original, servers=servers)
    # Diagnostics contain session routing only, never cookies or credentials.
    try:
        directory = Path(env.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'steam-mint'
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'last-launch.json').write_text(json.dumps({
            'time': time.time(), 'display': env.get('DISPLAY', ''),
            'inherited_display': original.get('DISPLAY', ''),
            'session_xwayland_displays': [server['display'] for server in servers],
            'wayland_display': env.get('WAYLAND_DISPLAY', ''),
            'xauthority_configured': bool(env.get('XAUTHORITY')),
            'session': env.get('HYPRLAND_INSTANCE_SIGNATURE', '')}, indent=2) + '\n')
    except OSError:
        pass
    args = sys.argv[1:] if argv is None else argv
    for candidate in ('/usr/bin/steam', '/usr/games/steam'):
        if Path(candidate).is_file() and os.access(candidate, os.X_OK):
            os.execve(candidate, [candidate, *args], env)
    client = Path.home() / '.local/share/Steam/steam.sh'
    if client.is_file():
        os.execve('/usr/bin/bash', ['/usr/bin/bash', str(client), *args], env)
    print('Steam is not installed. Install the Steam client first.', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
