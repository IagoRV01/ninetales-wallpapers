#!/usr/bin/env python3
"""Repair the user-local Steam launcher and private-Qt Caelestia icon lookup.

No display server is restarted and no authentication cookie or server ACL is changed.
The icon module requires the same Qt SDK used to build the installed Quickshell.
"""
from datetime import datetime
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
HOME = Path.home()
sys.path.insert(0, str(ROOT))
from ninetales_wallpapers import core


def backup(file, directory):
    if file.is_file():
        destination = directory / file.relative_to(HOME)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, destination)


def repair_steam(directory):
    launcher = HOME / '.local/bin/steam'
    helper = HOME / '.local/lib/steam-mint/launch.py'
    user = HOME / '.config/caelestia/hypr-user.lua'
    for path in (launcher, helper, user):
        backup(path, directory)
    helper.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / 'ninetales_wallpapers/desktop.py', helper)
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text('#!/usr/bin/env bash\nexec /usr/bin/python3 "$HOME/.local/lib/steam-mint/launch.py" "$@"\n')
    launcher.chmod(0o755)
    if user.is_file():
        source = user.read_text()
        old = 'dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP XDG_SESSION_TYPE'
        new = 'dbus-update-activation-environment --systemd DISPLAY XAUTHORITY WAYLAND_DISPLAY HYPRLAND_INSTANCE_SIGNATURE XDG_CURRENT_DESKTOP XDG_SESSION_TYPE'
        if old in source:
            user.write_text(source.replace(old, new))
    print('Steam launcher repaired; desktop Xwayland is resolved when Steam is opened.')


def repair_icons(directory):
    source = ROOT / 'integrations/caelestia-icons'
    qt = Path(os.environ.get('NW_QT_PREFIX') or (HOME / '.local/state/caelestia-mint/qt-prefix').read_text().strip())
    build = directory / 'icon-build'
    build.mkdir()
    shutil.copy2(source / 'iconpaths.cpp', build / 'iconpaths.cpp')
    includes = ['-I' + str(qt / 'include')] + ['-I' + str(qt / 'include' / module) for module in ('QtCore','QtGui','QtQml','QtNetwork')]
    subprocess.run([str(qt / 'libexec/moc'), *includes, str(build / 'iconpaths.cpp'), '-o', str(build / 'iconpaths.moc')], check=True)
    libs = ['-L' + str(qt / 'lib'), '-Wl,-rpath,' + str(qt / 'lib'), '-lQt6Qml', '-lQt6Gui', '-lQt6Core']
    subprocess.run(['g++','-std=c++17','-O2','-shared','-fPIC',*includes,str(build / 'iconpaths.cpp'),*libs,
                    '-o',str(build / 'libminticonpaths.so')], check=True)
    import_root = HOME / '.local/share/caelestia-mint/qml'
    test_root = build / 'qml'
    test_module = test_root / 'CaelestiaMint/Icons'
    test_module.mkdir(parents=True)
    shutil.copy2(build / 'libminticonpaths.so', test_module / 'libminticonpaths.so')
    shutil.copy2(source / 'qmldir', test_module / 'qmldir')
    verify = build / 'verify-icons'
    subprocess.run(['g++','-std=c++17','-fPIC',*includes,str(source / 'verify.cpp'),*libs,'-o',str(verify)], check=True)
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QPA_PLATFORMTHEME='',
               QT_PLUGIN_PATH=str(qt / 'plugins'), QML_IMPORT_PATH=str(qt / 'qml'))
    result = subprocess.run([str(verify), str(test_root)], env=env, capture_output=True, text=True)
    (directory / 'icon-verification.log').write_text(result.stdout + result.stderr)
    print(result.stdout + result.stderr, end='')
    if result.returncode:
        raise RuntimeError('Icon lookup verification failed; installed module and Caelestia shell were not modified.')
    module = import_root / 'CaelestiaMint/Icons'
    module.mkdir(parents=True, exist_ok=True)
    for path in (module / 'libminticonpaths.so', module / 'qmldir'):
        backup(path, directory)
    staged = module / '.libminticonpaths.staged.so'
    shutil.copy2(build / 'libminticonpaths.so', staged)
    os.replace(staged, module / 'libminticonpaths.so')
    shutil.copy2(source / 'qmldir', module / 'qmldir')
    shell = HOME / '.config/quickshell/caelestia/shell.qml'
    backup(shell, directory)
    text = shell.read_text()
    if 'import CaelestiaMint.Icons' not in text:
        shell.write_text(text.replace('import QtQuick\n', 'import QtQuick\nimport CaelestiaMint.Icons 1.0\n', 1))
    print('Caelestia now initializes icon search paths before resolving desktop icons.')


def main():
    directory = core.STATE_DIR / 'backups' / ('desktop-repair-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    directory.mkdir(parents=True)
    repair_steam(directory)
    if '--steam-only' not in sys.argv:
        repair_icons(directory)
    print('Backup:',directory)


if __name__ == '__main__':
    main()
