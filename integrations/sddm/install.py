#!/usr/bin/env python3
"""Install this reviewed SDDM bundle; never restart the display manager."""
import configparser
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    if os.geteuid() != 0:
        raise ValueError('Ejecuta este instalador mediante sudo.')
    if Path('/etc/X11/default-display-manager').read_text().strip() != '/usr/bin/sddm':
        raise ValueError('Este equipo no está usando SDDM; no se ha cambiado el gestor de sesiones.')
    bundle = Path(__file__).resolve().parent
    theme = bundle / 'theme'
    manifest = json.loads((bundle / 'manifest.json').read_text())
    actual = {str(p.relative_to(theme)) for p in theme.rglob('*') if p.is_file()}
    if actual != set(manifest['files']) or any(p.is_symlink() for p in theme.rglob('*')):
        raise ValueError('El contenido del tema no coincide con el paquete preparado.')
    for relative, expected in manifest['files'].items():
        file = theme / relative
        if not file.resolve().is_relative_to(theme.resolve()) or hashlib.sha256(file.read_bytes()).hexdigest() != expected:
            raise ValueError('El paquete ha cambiado; prepáralo otra vez desde la app.')
    packages = ['qml-module-qtquick-controls', 'qml-module-qtquick-layouts', 'qml-module-qtgraphicaleffects']
    if manifest.get('video'):
        packages += ['qml-module-qtmultimedia', 'gstreamer1.0-libav', 'gstreamer1.0-plugins-good']
    subprocess.run(['apt-get', '--no-remove', 'install', *packages], check=True)
    destination = Path('/usr/share/sddm/themes/ninetales-glass')
    conf = Path('/etc/sddm.conf.d/99-ninetales-theme.conf')
    if destination.is_symlink() or conf.is_symlink():
        raise ValueError('El destino contiene un enlace inesperado.')
    backup = Path(tempfile.mkdtemp(prefix='ninetales-login-', dir='/var/backups'))
    previous_theme = destination.exists()
    previous_conf = conf.exists()
    if previous_theme:
        shutil.copytree(destination, backup / 'theme')
    if previous_conf:
        shutil.copyfile(conf, backup / 'theme.conf')
    rollback = '''#!/bin/sh
set -eu
cd -- "$(dirname -- "$0")"
rm -rf -- /usr/share/sddm/themes/ninetales-glass
rm -f -- /etc/sddm.conf.d/99-ninetales-theme.conf
'''
    if previous_theme:
        rollback += 'cp -a -- ./theme /usr/share/sddm/themes/ninetales-glass\n'
    if previous_conf:
        rollback += 'cp -a -- ./theme.conf /etc/sddm.conf.d/99-ninetales-theme.conf\n'
    (backup / 'rollback.sh').write_text(rollback)
    (backup / 'rollback.sh').chmod(0o700)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix='.ninetales-', dir=destination.parent))
    try:
        shutil.copytree(theme, staged, dirs_exist_ok=True)
        for file in staged.rglob('*'):
            file.chmod(0o755 if file.is_dir() else 0o644)
        staged.chmod(0o755)
        if destination.exists():
            shutil.rmtree(destination)
        staged.rename(destination)
        conf.parent.mkdir(parents=True, exist_ok=True)
        conf.write_text('[Theme]\nCurrent=ninetales-glass\n')
        conf.chmod(0o644)
    except Exception:
        subprocess.run(['/bin/sh', str(backup / 'rollback.sh')], check=True)
        raise
    finally:
        if staged.exists():
            shutil.rmtree(staged)
    print('Pantalla de inicio de sesión instalada. Se mostrará al cerrar sesión o reiniciar.')
    print('No se ha interrumpido la sesión actual.')
    print('Para restaurar el tema anterior: sudo sh ' + str(backup / 'rollback.sh'))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('Instalación detenida: ' + str(error), file=sys.stderr)
        sys.exit(1)
