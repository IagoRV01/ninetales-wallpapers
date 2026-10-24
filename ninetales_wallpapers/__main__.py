import argparse
import json
import sys

from . import core


def main():
    parser = argparse.ArgumentParser(description='Ninetales Wallpapers · Wallpaper Engine nativo para Hyprland')
    sub = parser.add_subparsers(dest='command')
    sub.add_parser('gui', help='Abrir el selector gráfico')
    sub.add_parser('daemon', help='Ejecutar el supervisor de fondos')
    sub.add_parser('autostart', help='Restaurar el último fondo al iniciar Hyprland')
    sub.add_parser('scan', help='Listar los fondos de Steam y las carpetas locales')
    sub.add_parser('status', help='Mostrar el estado del reproductor')
    sub.add_parser('stop', help='Volver al fondo de Caelestia')
    sub.add_parser('pause', help='Pausar o reanudar manualmente')
    sub.add_parser('doctor', help='Comprobar motor, recursos, Qt y bibliotecas')
    wrapper = sub.add_parser('steam-wrapper', help='Steam launch option entry point')
    wrapper.add_argument('steam_command', nargs=argparse.REMAINDER)
    apply = sub.add_parser('apply', help='Aplicar un archivo o carpeta de Workshop')
    apply.add_argument('path')
    apply.add_argument('--backend', choices=('native', 'proton'), default=None)
    apply.add_argument('--output', default='*')
    apply.add_argument('--fps', type=int, choices=(15, 24, 30, 60), default=30)
    apply.add_argument('--sound', action='store_true')
    apply.add_argument('--scaling', choices=('fill', 'fit', 'stretch'), default='fill')
    args = parser.parse_args()
    try:
        if args.command in (None, 'gui'):
            from .gui import main as gui
            return gui()
        if args.command == 'steam-wrapper':
            from .steam_integration import wrapper as run_wrapper
            command = args.steam_command
            return run_wrapper(command[1:] if command and command[0] == '--' else command) or 0
        elif args.command == 'daemon':
            from .daemon import Daemon
            Daemon().run()
        elif args.command == 'autostart':
            if core.load_config().get('autostart', True):
                core.ensure_daemon()
        elif args.command == 'scan':
            walls, errors = core.scan_library()
            print(json.dumps({'wallpapers': [w.as_dict() for w in walls], 'errors': errors}, ensure_ascii=False, indent=2))
        elif args.command == 'status':
            print(json.dumps(core.status(), ensure_ascii=False, indent=2))
        elif args.command == 'apply':
            wall = core.apply(args.path, backend=args.backend or core.load_config()['backend'], output=args.output, fps=args.fps, muted=not args.sound, scaling=args.scaling)
            print('Fondo solicitado:', wall.title, '· Comprueba su estado con ninetales-wallpapers status.')
        elif args.command == 'stop':
            core.save_config(selection=None, manual_paused=False)
            core.ensure_daemon()
            print('Restaurando el fondo de Caelestia.')
        elif args.command == 'pause':
            paused = not core.load_config().get('manual_paused', False)
            core.save_config(manual_paused=paused)
            core.ensure_daemon()
            print('Pausa manual:', paused)
        elif args.command == 'doctor':
            try:
                core.qt_environment()
                qt = 'listo'
            except ValueError as error:
                qt = str(error)
            print(json.dumps({'qt_multimedia': qt, 'steam_integration': __import__('ninetales_wallpapers.steam_integration', fromlist=['info']).info(), 'motor_oficial': __import__('ninetales_wallpapers.proton', fromlist=['discover']).discover(), 'motor_escenas': core.renderer_path(),
                              'assets': str(core.find_assets() or ''),
                              'bibliotecas_steam': list(map(str, core.steam_libraries())),
                              'monitores': [m['name'] for m in core.monitors()],
                              'estado': core.status()}, ensure_ascii=False, indent=2))
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
