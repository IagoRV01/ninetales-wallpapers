#!/usr/bin/env python3
"""Instalar el gestor en el usuario actual, sin privilegios de administrador."""
from datetime import datetime
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
HOME = Path.home()
sys.path.insert(0, str(ROOT))
from ninetales_wallpapers import core


def install():
    core.qt_environment()
    backup = core.STATE_DIR / 'backups' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup.mkdir(parents=True)
    background = HOME / '.config/quickshell/caelestia/modules/background/Background.qml'
    user = HOME / '.config/caelestia/hypr-user.lua'
    for file in (background, user):
        target = backup / file.relative_to(HOME)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, target)
    previous = core.STATE_DIR / 'backup-actual'
    original = core.STATE_DIR / 'backup-original'
    if not original.exists():
        original.write_text(previous.read_text() if previous.exists() else str(backup) + '\n')
    previous.write_text(str(backup) + '\n')
    source = background.read_text()
    if 'NINETALES_NATIVE_WALLPAPER' not in source:
        if source.count('contentItem.Config.background.wallpaperEnabled') != 2 or source.count('active: Config.background.wallpaperEnabled') != 1:
            raise RuntimeError('La estructura de Caelestia cambió; se requiere revisar la integración.')
        source = source.replace('import Quickshell\n', 'import Quickshell\nimport Quickshell.Io\n')
        marker = '        required property ShellScreen modelData\n'
        assert marker in source
        source = source.replace(marker, marker + '''
        // NINETALES_NATIVE_WALLPAPER: ocultar el fondo sólo tras presentar uno nuevo.
        property var nativeWallpaperState: ({})
        property double nativeWallpaperNow: Date.now()
        readonly property bool nativeWallpaperActive: nativeWallpaperState.active === true
            && nativeWallpaperNow - (nativeWallpaperState.heartbeat ?? 0) < 15000
            && (nativeWallpaperState.ready_outputs ?? []).includes(modelData.name)
        readonly property bool effectiveWallpaperEnabled: contentItem.Config.background.wallpaperEnabled && !nativeWallpaperActive
        mask: nativeWallpaperActive ? nativeWallpaperInputMask : null

        Region { id: nativeWallpaperInputMask }
        FileView {
            path: `${Quickshell.env("XDG_STATE_HOME") || Quickshell.env("HOME") + "/.local/state"}/ninetales-wallpapers/runtime.json`
            printErrors: false
            watchChanges: true
            onFileChanged: reload()
            onLoaded: {
                try { win.nativeWallpaperState = JSON.parse(text()); }
                catch (error) { win.nativeWallpaperState = ({}); }
            }
            onLoadFailed: win.nativeWallpaperState = ({})
        }
        Timer {
            interval: 2000
            running: true
            repeat: true
            onTriggered: win.nativeWallpaperNow = Date.now()
        }
''')
        # Sólo reemplazar las condiciones originales, conservando la nueva propiedad.
        source = source.replace('WlrLayershell.layer: contentItem.Config.background.wallpaperEnabled ?',
                                'WlrLayershell.layer: win.effectiveWallpaperEnabled ?')
        source = source.replace('color: contentItem.Config.background.wallpaperEnabled ?',
                                'color: win.effectiveWallpaperEnabled ?')
        source = source.replace('active: Config.background.wallpaperEnabled', 'active: win.effectiveWallpaperEnabled')
        background.write_text(source)

    source = user.read_text()
    if '-- NINETALES_WALLPAPERS_BEGIN' not in source:
        user.write_text(source + '''
-- NINETALES_WALLPAPERS_BEGIN
hl.on("hyprland.start", function()
    hl.exec_cmd(os.getenv("HOME") .. "/.local/bin/ninetales-wallpapers autostart")
end)
hl.bind("SUPER + ALT + W", hl.dsp.exec_cmd(os.getenv("HOME") .. "/.local/bin/ninetales-wallpapers gui"))
-- NINETALES_WALLPAPERS_END
''')
    check = subprocess.run(['Hyprland', '--verify-config', '-c', str(HOME / '.config/hypr/hyprland.lua')],
                           capture_output=True, text=True, timeout=30)
    (core.STATE_DIR / 'validacion-hyprland.log').write_text(check.stdout + check.stderr)
    if check.returncode or 'config ok' not in check.stdout:
        for file in (background, user):
            shutil.copy2(backup / file.relative_to(HOME), file)
        raise RuntimeError('Falló la validación de Hyprland. Se restauraron los archivos anteriores.')
    launcher = HOME / '.local/bin/ninetales-wallpapers'
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text('#!/usr/bin/env bash\nexport PYTHONPATH=' + shlex.quote(str(ROOT)) +
                        '${PYTHONPATH:+:$PYTHONPATH}\nexec /usr/bin/python3 -m ninetales_wallpapers "$@"\n')
    launcher.chmod(0o755)
    desktop = HOME / '.local/share/applications/io.github.iago.NinetalesWallpapers.desktop'
    desktop.parent.mkdir(parents=True, exist_ok=True)
    sprite = HOME / '.local/share/fastfetch/ninetales-alola-shiny/ninetales.png'
    desktop.write_text(f'''[Desktop Entry]
Type=Application
Name=Ninetales Wallpapers
Comment=Fondos de Wallpaper Engine, vídeos y GIF para Hyprland
Exec={launcher} gui
Icon={sprite if sprite.is_file() else 'preferences-desktop-wallpaper'}
Terminal=false
Categories=Settings;DesktopSettings;
Keywords=Wallpaper;Steam;Workshop;Fondo;Animado;Ninetales;
StartupNotify=true
''')
    old_desktop = desktop.with_name('ninetales-wallpapers.desktop')
    if old_desktop.exists() and f'Exec={launcher} gui' in old_desktop.read_text():
        shutil.copy2(old_desktop, backup / old_desktop.name)
        old_desktop.unlink()
    if not core.CONFIG.exists():
        core.save_config()
    if not core.STATUS.exists():
        core.atomic_json(core.STATUS, dict(active=False, status='detenido', heartbeat=0,
                                         ready_outputs=[], detail='Selecciona un fondo.'))
    print('Gestor instalado:', launcher)
    print('Inicio automático configurado. Super+Alt+W abre el selector.')
    print('Copia de seguridad:', backup)


if __name__ == '__main__':
    install()
