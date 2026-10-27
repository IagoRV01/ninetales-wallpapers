#!/usr/bin/env python3
"""Render a prepared theme with the installed SDDM in offscreen test mode.

Uses a synthetic login backend. Never authenticates, changes SDDM configuration,
starts a session, or invokes any power action. Requires an existing local bundle.
"""
import argparse
import configparser
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

PROJECT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('bundle', type=Path)
    parser.add_argument('--screenshot', type=Path, required=True)
    args = parser.parse_args()
    args.screenshot = args.screenshot.resolve()
    args.screenshot.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='nw-greeter-test-') as directory:
        root = Path(directory)
        theme = root / 'theme'
        shutil.copytree(args.bundle / 'theme', theme)
        conf = configparser.ConfigParser(interpolation=None)
        conf.optionxform = str
        conf.read(theme / 'theme.conf')
        conf['General']['PreviewPath'] = str(args.screenshot)
        with (theme / 'theme.conf').open('w') as output:
            conf.write(output)
        environment = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
                           QT_PLUGIN_PATH='/usr/lib/x86_64-linux-gnu/qt5/plugins',
                           QML2_IMPORT_PATH='/usr/lib/x86_64-linux-gnu/qt5/qml')
        for key in ('QT_QPA_PLATFORMTHEME', 'QML_IMPORT_PATH', 'WAYLAND_DISPLAY'):
            environment.pop(key, None)

        def launch(seconds):
            with (root / 'greeter.log').open('w+') as log:
                process = subprocess.Popen(['sddm-greeter', '--test-mode', '--theme', str(theme)],
                                           env=environment, stdout=log, stderr=subprocess.STDOUT)
                try:
                    deadline = time.monotonic() + seconds
                    while process.poll() is None and time.monotonic() < deadline:
                        time.sleep(0.1)
                        log.seek(0)
                        if 'LOGIN_CHECK_PASS' in log.read():
                            break
                finally:
                    if process.poll() is None:
                        process.terminate()
                    process.wait(timeout=5)
                log.seek(0)
                return log.read()

        # Check the actual production Main.qml against SDDM's real context/models.
        production = launch(1)
        assert 'Fallback to embedded theme' not in production and 'Adding view' in production, production
        assert 'Cannot assign' not in production and 'ReferenceError' not in production, production
        shutil.copyfile(PROJECT / 'integrations/sddm/Preview.qml', theme / 'Main.qml')
        preview = launch(6)
        assert 'LOGIN_CHECK_PASS' in preview and 'LOGIN_CHECK_FAIL' not in preview, preview
        assert args.screenshot.is_file(), 'Screenshot missing'
        args.screenshot.with_suffix('.log').write_text(production + '\n' + preview)
        print('PASS: production SDDM context, profile image, session choice, password clearing, error and retry; screenshot at ' + str(args.screenshot))


if __name__ == '__main__':
    main()
