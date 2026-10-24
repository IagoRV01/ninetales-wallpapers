#!/usr/bin/env python3
"""Optional GUI smoke test, using private Xvfb, temporary state and a private bus.

Run with: dbus-run-session -- /usr/bin/python3 scripts/test-gui.py
Requires system PyGObject, GTK 3 and Xvfb. It never starts Steam or a renderer.
"""
from contextlib import ExitStack
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    with tempfile.TemporaryDirectory(prefix='nw-gui-test-') as temporary:
        temp = Path(temporary)
        read, write = os.pipe()
        server = subprocess.Popen(['Xvfb', '-displayfd', str(write), '-screen', '0',
                                   '1280x900x24', '-nolisten', 'tcp', '-noreset'],
                                  pass_fds=(write,), stderr=subprocess.PIPE)
        os.close(write)
        try:
            if not select.select([read], [], [], 10)[0]:
                raise RuntimeError('Xvfb startup timeout')
            number = os.read(read, 64).decode().strip()
            if not number.isdigit():
                raise RuntimeError('Xvfb failed: ' + server.stderr.read().decode())
            os.environ.update(DISPLAY=':' + number, GDK_BACKEND='x11')
            os.environ.pop('WAYLAND_DISPLAY', None)
            from ninetales_wallpapers import core, i18n
            from ninetales_wallpapers.gui import Application
            from gi.repository import Gtk, GLib
            with ExitStack() as stack:
                for name, value in {'HOME': temp, 'CONFIG': temp / 'config.json',
                                    'CONFIG_DIR': temp, 'STATE_DIR': temp / 'state',
                                    'STATUS': temp / 'state/runtime.json'}.items():
                    stack.enter_context(patch.object(core, name, value))
                stack.enter_context(patch.object(core, 'steam_libraries', return_value=[]))
                stack.enter_context(patch.object(core, 'monitors', return_value=[]))
                app = Application()
                app.set_application_id('io.github.iago.NinetalesWallpapers.Smoke' + str(os.getpid()))
                app.register(None)
                app.start_requested = True
                core.save_config(language='en', selection=None, backend='native')
                app.do_activate()

                def descendants(widget):
                    yield widget
                    if isinstance(widget, Gtk.Container):
                        for child in widget.get_children():
                            yield from descendants(child)

                for language in ('fr', 'pt', 'es', 'en'):
                    errors = []
                    def change_language():
                        dialog = next((w for w in Gtk.Window.list_toplevels() if isinstance(w, Gtk.Dialog)), None)
                        try:
                            assert dialog is not None, 'Settings dialog missing'
                            assert dialog.get_title() == i18n.t('Ajustes')
                            widgets = list(descendants(dialog))
                            notebook = next(w for w in widgets if isinstance(w, Gtk.Notebook))
                            assert notebook.get_n_pages() == 5, 'Settings pages missing'
                            combos = [w for w in widgets if isinstance(w, Gtk.ComboBoxText)]
                            current = core.load_config()['language']
                            chooser = next(w for w in combos if w.get_active_id() == current)
                            chooser.set_active_id(language)
                            dialog.response(Gtk.ResponseType.OK)
                        except Exception as error:
                            errors.append(error)
                            if dialog:
                                dialog.response(Gtk.ResponseType.CANCEL)
                        return False
                    timer = GLib.timeout_add(300, change_language)
                    app.window.show_settings()
                    if errors:
                        raise errors[0]
                    assert core.load_config()['language'] == language
                    labels = [w.get_text() for w in descendants(app.window) if isinstance(w, Gtk.Label)]
                    assert i18n.t('Tu biblioteca') in labels, language
                app.window.destroy()
                app.quit()
                print('PASS: five settings pages render and all four languages rebuild the UI.')
        finally:
            os.close(read)
            server.terminate()
            server.wait(timeout=3)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
