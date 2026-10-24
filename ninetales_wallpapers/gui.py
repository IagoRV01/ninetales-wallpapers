from __future__ import annotations

from pathlib import Path
import subprocess
import threading

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk, Pango

from . import core
from .i18n import LANGUAGES, configure, localize, t

LABELS = {'video': 'Vídeo', 'scene': 'Escena animada', 'web': 'Interactivo', 'gif': 'GIF', 'image': 'Imagen'}
CSS = b'''
window.nw-app { background: #151222; color: #f6f3fc; font-size: 14px; }
.nw-app headerbar { background: #1d1930; border-bottom: 1px solid #3b334f; box-shadow: none; }
.nw-app label { color: #f6f3fc; }
.nw-app .title { font-size: 23px; font-weight: 700; color: #e5defa; }
.nw-app .section-title { font-size: 18px; font-weight: 700; }
.nw-app .muted { color: #bcb4d0; font-size: 13px; }
.nw-app .tile-title { font-size: 15px; font-weight: 600; }
.nw-app .tile-kind { font-size: 12px; color: #bcb4d0; }
button { background-image: none; background-color: #2b253d; color: #f6f3fc; border: 1px solid #514662; border-radius: 10px; min-height: 28px; padding: 7px 12px; box-shadow: none; text-shadow: none; }
button:hover { background-color: #3b3253; border-color: #8c7db4; }
button:active { background-color: #4b3e67; }
button:disabled, button:disabled label { color: #82798f; background-color: #221e2e; border-color: #3a3347; }
button label { color: inherit; }
button.primary { background-color: #c5b9f2; color: #20182e; border-color: #c5b9f2; font-weight: 700; font-size: 15px; min-height: 36px; }
button.primary:hover { background-color: #d7cdf8; }
.nw-app button.primary label { color: #20182e; }
button.primary:disabled { background-color: #39304b; color: #94899e; border-color: #4c405f; }
.nw-app button.primary:disabled label { color: #94899e; }
entry { background: #211c30; color: #f6f3fc; border: 1px solid #514662; border-radius: 10px; padding: 10px; caret-color: #e5defa; }
entry:focus { border-color: #c5b9f2; }
entry selection { background-color: #5b479e; color: white; }
popover, menu { background: #252036; color: #f6f3fc; border-color: #514662; }
menuitem { padding: 8px; color: #f6f3fc; }
menuitem:hover { background: #5b479e; }
.nw-app .library { background: #151222; }
.nw-app .wallpaper-card { background: #231d32; border: 2px solid #3c334e; border-radius: 12px; padding: 10px; }
.nw-app flowboxchild { padding: 0; border-radius: 12px; }
.nw-app flowboxchild:hover .wallpaper-card { border-color: #8e80b3; background: #2d2540; }
.nw-app flowboxchild:selected .wallpaper-card { border-color: #c5b9f2; background: #3c3056; }
.nw-app flowboxchild:selected { background: transparent; outline: none; }
.nw-app .inspector { background: #211b30; border: 1px solid #40364f; border-radius: 16px; padding: 18px; }
.nw-app .preview { background: #120f1c; border: 1px solid #4a3d5e; border-radius: 10px; }
.nw-app separator { background: #463952; min-height: 1px; }
.nw-app switch { background: #514662; border-color: #6c5b83; }
.nw-app switch:checked { background: #8874bf; border-color: #b8a6e9; }
.nw-app switch slider { background: #eee7fc; border: none; }
.nw-app expander title { padding: 8px 0; color: #d2c7e7; }
.nw-app .status { color: #d0c5e3; font-size: 13px; }
.nw-app .notice { background: #3c3056; border-radius: 10px; padding: 12px; }
'''


def label(text='', style=None, wrap=False):
    widget = Gtk.Label(label=text, xalign=0)
    if style:
        widget.get_style_context().add_class(style)
    widget.set_line_wrap(wrap)
    widget.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
    return widget


class Window(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title='Ninetales Wallpapers')
        self.get_style_context().add_class('nw-app')
        self.set_default_size(1120, 760)
        self.set_icon_name('preferences-desktop-wallpaper')
        self.config = core.load_config()
        configure(self.config.get('language', 'auto'))
        self.wallpapers = []
        self.selected_path = (self.config.get('selection') or {}).get('path')
        self.last_status = None
        self.library_revision = None
        self.thumbnails = {}
        self.shown_limit = 60
        self.closed = False
        self.connect('destroy', lambda *_: setattr(self, 'closed', True))

        header = Gtk.HeaderBar(title='Ninetales Wallpapers', subtitle=t('Tu escritorio, en movimiento'))
        header.set_show_close_button(True)
        self.set_titlebar(header)
        add = Gtk.MenuButton(label=t('Añadir'))
        self.add_menu(add, [(t('Archivo de vídeo o imagen…'), lambda: self.add_source(False)),
                            (t('Carpeta de fondos…'), lambda: self.add_source(True))])
        header.pack_start(add)
        settings = Gtk.Button.new_from_icon_name('emblem-system-symbolic', Gtk.IconSize.BUTTON)
        settings.set_tooltip_text(t('Ajustes'))
        settings.connect('clicked', lambda *_: self.show_settings())
        header.pack_end(settings)
        self.refresh_button = Gtk.Button.new_from_icon_name('view-refresh-symbolic', Gtk.IconSize.BUTTON)
        self.refresh_button.set_tooltip_text(t('Actualizar fondos'))
        self.refresh_button.connect('clicked', lambda *_: self.refresh())
        header.pack_end(self.refresh_button)
        workshop = Gtk.Button(label='Steam Workshop')
        workshop.connect('clicked', lambda *_: self.open_steam('workshop'))
        header.pack_end(workshop)
        downloads = Gtk.Button(label=t('Descargas'))
        downloads.set_tooltip_text(t('Comprobar o reanudar las descargas en Steam'))
        downloads.connect('clicked', lambda *_: self.open_steam('downloads'))
        header.pack_end(downloads)

        layout = Gtk.Box(spacing=20, margin=18)
        self.add(layout)
        library = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, hexpand=True)
        layout.pack_start(library, True, True, 0)
        heading = Gtk.Box(spacing=10)
        heading.pack_start(label(t('Tu biblioteca'), 'section-title'), True, True, 0)
        self.count = label('', 'muted')
        heading.pack_end(self.count, False, False, 0)
        library.pack_start(heading, False, False, 0)
        tools = Gtk.Box(spacing=10)
        self.search = Gtk.SearchEntry(placeholder_text=t('Buscar un fondo'), hexpand=True)
        self.search.connect('search-changed', lambda *_: self.filter())
        tools.pack_start(self.search, True, True, 0)
        self.filter_type = Gtk.ComboBoxText()
        self.filter_type.append('', t('Todos'))
        for kind, name in LABELS.items():
            self.filter_type.append(kind, t(name))
        self.filter_type.set_active(0)
        self.filter_type.connect('changed', lambda *_: self.filter())
        tools.pack_start(self.filter_type, False, False, 0)
        library.pack_start(tools, False, False, 0)
        self.workshop_banner = Gtk.Box(spacing=12)
        self.workshop_banner.get_style_context().add_class('notice')
        self.workshop_banner.set_no_show_all(True)
        self.workshop_text = label('', wrap=True)
        self.workshop_text.set_max_width_chars(62)
        self.workshop_banner.pack_start(self.workshop_text, True, True, 0)
        resume = Gtk.Button(label=t('Abrir descargas'))
        resume.set_valign(Gtk.Align.CENTER)
        resume.connect('clicked', lambda *_: self.open_steam('downloads'))
        self.workshop_banner.pack_end(resume, False, False, 0)
        library.pack_start(self.workshop_banner, False, False, 0)
        self.flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.SINGLE, homogeneous=True,
                                row_spacing=12, column_spacing=12,
                                min_children_per_line=1, max_children_per_line=4,
                                valign=Gtk.Align.START)
        self.flow.connect('selected-children-changed', self.selection_changed)
        self.flow.connect('child-activated', lambda *_: self.apply())
        scroll = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        scroll.get_style_context().add_class('library')
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.flow)
        library.pack_start(scroll, True, True, 0)
        self.empty = label(t('Buscando fondos…'), 'muted', True)
        self.empty.set_no_show_all(True)
        library.pack_start(self.empty, False, False, 0)
        self.more = Gtk.Button(label=t('Mostrar más fondos'))
        self.more.set_no_show_all(True)
        self.more.connect('clicked', self.show_more)
        library.pack_start(self.more, False, False, 0)

        sidebar_scroll = Gtk.ScrolledWindow(vexpand=True)
        sidebar_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sidebar_scroll.set_size_request(338, -1)
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        sidebar.get_style_context().add_class('inspector')
        sidebar_scroll.add(sidebar)
        layout.pack_end(sidebar_scroll, False, False, 0)
        self.preview = Gtk.Image.new_from_icon_name('preferences-desktop-wallpaper', Gtk.IconSize.DIALOG)
        preview_frame = Gtk.Frame(shadow_type=Gtk.ShadowType.NONE)
        preview_frame.get_style_context().add_class('preview')
        preview_frame.set_size_request(300, 172)
        preview_frame.add(self.preview)
        sidebar.pack_start(preview_frame, False, False, 0)
        self.selected_label = label(t('Elige un fondo'), 'title', True)
        self.selected_label.set_max_width_chars(22)
        sidebar.pack_start(self.selected_label, False, False, 0)
        self.metadata = label(t('Selecciona una miniatura de la biblioteca.'), 'muted', True)
        self.metadata.set_max_width_chars(32)
        sidebar.pack_start(self.metadata, False, False, 0)
        self.apply_button = Gtk.Button(label=t('Aplicar fondo'))
        self.apply_button.get_style_context().add_class('primary')
        self.apply_button.set_sensitive(False)
        self.apply_button.connect('clicked', lambda *_: self.apply())
        sidebar.pack_start(self.apply_button, False, False, 0)
        playback = Gtk.Box(spacing=8, homogeneous=True)
        self.pause = Gtk.Button(label=t('Pausar'))
        self.pause.connect('clicked', self.toggle_pause)
        playback.pack_start(self.pause, True, True, 0)
        stop = Gtk.Button(label=t('Fondo estático'))
        stop.set_tooltip_text(t('Volver al fondo de Caelestia'))
        stop.connect('clicked', lambda *_: self.stop())
        playback.pack_start(stop, True, True, 0)
        sidebar.pack_start(playback, False, False, 0)
        self.status_label = label('', 'status', True)
        self.status_label.set_max_width_chars(32)
        sidebar.pack_start(self.status_label, False, False, 0)
        sidebar.pack_start(Gtk.Separator(), False, False, 2)

        self.backend = Gtk.ComboBoxText()
        self.backend.append('native', t('Nativo · recomendado'))
        self.backend.append('proton', t('Oficial · Proton (experimental)'))
        self.backend.set_active_id(self.config.get('backend', 'native'))
        self.backend.set_tooltip_text(t('El motor oficial usa una pantalla virtual; requiere Xvfb y puede consumir más CPU.'))
        self.field(sidebar, t('Motor'), self.backend)

        self.output = Gtk.ComboBoxText()
        self.output.append('*', t('Todas las pantallas'))
        screens = core.monitors()
        for screen in screens:
            self.output.append(screen['name'], screen['name'])
        requested = self.config.get('output', '*')
        if requested != '*' and requested not in [s['name'] for s in screens]:
            self.output.append(requested, t('{output} (desconectada)', output=requested))
        self.output.set_active_id(requested)
        self.field(sidebar, t('Pantalla'), self.output)
        self.scaling = Gtk.ComboBoxText()
        for value, text in [('fill', t('Rellenar la pantalla')), ('fit', t('Ajustar sin recortar')), ('stretch', t('Estirar'))]:
            self.scaling.append(value, text)
        self.scaling.set_active_id(self.config.get('scaling', 'fill'))
        self.field(sidebar, t('Cómo encaja'), self.scaling)
        self.autostart = self.switch(sidebar, t('Recordar al iniciar'), 'autostart', True)
        advanced = Gtk.Expander(label=t('Más opciones'))
        advanced_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, margin_top=10)
        advanced.add(advanced_box)
        sidebar.pack_start(advanced, False, False, 0)
        self.fps = Gtk.ComboBoxText()
        for fps in (15, 24, 30, 60):
            self.fps.append(str(fps), str(fps) + ' FPS')
        self.fps.set_active_id(str(self.config.get('fps', 30)))
        self.field(advanced_box, t('Fluidez de las escenas'), self.fps)
        self.sound = self.switch(advanced_box, t('Sonido'), 'muted', True, invert=True)
        self.fullscreen = self.switch(advanced_box, t('Pausar a pantalla completa'), 'pause_fullscreen', True)
        self.battery = self.switch(advanced_box, t('Ahorrar batería'), 'pause_battery', False)
        self.notice = label('', 'muted', True)
        self.notice.set_no_show_all(True)
        self.notice.set_max_width_chars(32)
        sidebar.pack_start(self.notice, False, False, 0)
        GLib.timeout_add_seconds(1, self.update_status)
        GLib.timeout_add_seconds(5, self.watch_downloads)
        self.refresh()
        self.update_status()

    def show_settings(self, page='general'):
        from . import steam_integration, __version__
        import json
        conf = core.load_config()
        dialog = Gtk.Dialog(title=t('Ajustes'), transient_for=self, modal=True)
        dialog.get_style_context().add_class('nw-app')
        dialog.set_default_size(700, 650)
        dialog.add_button(t('Cancelar'), Gtk.ResponseType.CANCEL)
        dialog.add_button(t('Guardar'), Gtk.ResponseType.OK)
        notebook = Gtk.Notebook(margin=16)
        dialog.get_content_area().pack_start(notebook, True, True, 0)
        pages = {}

        def tab(key, title):
            scroll = Gtk.ScrolledWindow()
            scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16, margin=18)
            scroll.add(box)
            pages[key] = notebook.append_page(scroll, Gtk.Label(label=t(title)))
            return box

        def combo(parent, title, values, selected):
            widget = Gtk.ComboBoxText()
            for key, text in values:
                widget.append(key, text)
            widget.set_active_id(str(selected))
            self.field(parent, t(title), widget)
            return widget

        def check(parent, title, active):
            widget = Gtk.CheckButton(label=t(title))
            widget.set_active(bool(active))
            parent.pack_start(widget, False, False, 0)
            return widget

        general = tab('general', t('General'))
        language = combo(general, t('Idioma'), [(key, t(name) if key == 'auto' else name) for key, name in LANGUAGES.items()], conf.get('language', 'auto'))
        on_open = check(general, t('Iniciar el fondo al abrir la app'), conf.get('steam_on_open', True))
        autostart = check(general, t('Recordar al iniciar'), conf.get('autostart', True))
        general.pack_start(label('Ninetales Wallpapers ' + __version__, 'muted'), False, False, 0)

        playback = tab('playback', t('Reproducción'))
        backend = combo(playback, t('Motor'), [('native', t('Nativo · recomendado')),
                        ('proton', t('Oficial · Proton (experimental)'))], conf.get('backend', 'native'))
        fps = combo(playback, t('Fluidez de las escenas'), [(str(n), str(n) + ' FPS') for n in (15, 24, 30, 60)], conf.get('fps', 30))
        scaling = combo(playback, t('Cómo encaja'), [('fill', t('Rellenar la pantalla')),
                        ('fit', t('Ajustar sin recortar')), ('stretch', t('Estirar'))], conf.get('scaling', 'fill'))
        sound = check(playback, t('Sonido'), not conf.get('muted', True))
        fullscreen = check(playback, t('Pausar a pantalla completa'), conf.get('pause_fullscreen', True))
        battery = check(playback, t('Ahorrar batería'), conf.get('pause_battery', False))

        steam = tab('steam', 'Steam')
        tracking = check(steam, t('Iniciar mediante Steam'), conf.get('steam_tracking', True))
        steam.pack_start(label(t('Steam registra el uso cuando inicia el motor oficial. Abrir el .exe directamente no garantiza el recuento de horas.'), wrap=True), False, False, 0)
        details = steam_integration.info()
        status = label(t('Configurado') if details['configured'] else t('Pendiente de configurar'), 'section-title')
        steam.pack_start(status, False, False, 0)
        minutes = details['playtime_minutes']
        steam.pack_start(label(t('Tiempo registrado por Steam: {hours} h {minutes} min', hours=minutes // 60, minutes=minutes % 60)
                              if minutes is not None else t('Steam aún no ofrece un tiempo registrado.'), 'muted', True), False, False, 0)
        instructions = label(t('1. Copia esta opción. 2. En Steam, abre Propiedades de Wallpaper Engine. 3. Pégala en Opciones de lanzamiento. 4. Detén Wallpaper Engine y aplica el fondo desde esta app.'), wrap=True)
        instructions.set_max_width_chars(65)
        steam.pack_start(instructions, False, False, 0)
        option = Gtk.Entry(text=steam_integration.launch_options(), editable=False)
        steam.pack_start(option, False, False, 0)
        copy = Gtk.Button(label=t('Copiar opción de lanzamiento'))
        copy.connect('clicked', lambda *_: Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(option.get_text(), -1))
        steam.pack_start(copy, False, False, 0)
        properties = Gtk.Button(label=t('Abrir propiedades en Steam'))
        properties.connect('clicked', lambda *_: self.open_steam('properties'))
        steam.pack_start(properties, False, False, 0)
        verify = Gtk.Button(label=t('Comprobar integración'))
        def check_steam(*_):
            good = steam_integration.info()['configured']
            status.set_text(t('Configurado') if good else t('Pendiente de configurar'))
            self.message(t('La opción está configurada en Steam. Aplica un fondo con el motor oficial para iniciar la sesión.') if good else
                         t('Steam todavía no ha guardado esta opción. Pégala en sus propiedades y cierra la ventana de propiedades.'))
        verify.connect('clicked', check_steam)
        steam.pack_start(verify, False, False, 0)

        library = tab('library', t('Biblioteca'))
        library.pack_start(label(t('Carpetas añadidas'), 'section-title'), False, False, 0)
        folders = Gtk.ComboBoxText()
        for path in conf.get('library_paths', []):
            folders.append(path, path)
        folders.set_active(0)
        library.pack_start(folders, False, False, 0)
        remove = Gtk.Button(label=t('Quitar carpeta'))
        remove.set_tooltip_text(t('La carpeta se quitará de la biblioteca; sus archivos se conservan.'))
        def remove_folder(*_):
            path = folders.get_active_id()
            if path:
                current = core.load_config().get('library_paths', [])
                core.save_config(library_paths=[p for p in current if p != path])
                folders.remove(folders.get_active())
                folders.set_active(0)
                self.refresh()
        remove.connect('clicked', remove_folder)
        library.pack_start(remove, False, False, 0)
        add_folder = Gtk.Button(label=t('Carpeta de fondos…'))
        def add_library_folder(*_):
            self.add_source(True)
            folders.remove_all()
            for path in core.load_config().get('library_paths', []):
                folders.append(path, path)
            folders.set_active(0)
        add_folder.connect('clicked', add_library_folder)
        library.pack_start(add_folder, False, False, 0)
        assets = Gtk.Button(label=t('Carpeta de Wallpaper Engine…'))
        assets.connect('clicked', lambda *_: self.choose_assets())
        library.pack_start(assets, False, False, 0)
        if not core.renderer_path():
            install = Gtk.Button(label=t('Instalar motor de escenas…'))
            install.connect('clicked', lambda *_: self.install_renderer())
            library.pack_start(install, False, False, 0)

        diagnostics = tab('diagnostics', t('Diagnóstico'))
        from . import proton
        report = json.dumps({'version': __version__, 'official_renderer': proton.discover(),
                             'native_renderer': core.renderer_path(),
                             'steam_launch_configured': details['configured']}, ensure_ascii=False, indent=2)
        view = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        view.get_buffer().set_text(report)
        diagnostics.pack_start(view, True, True, 0)
        logs = Gtk.Button(label=t('Abrir registros'))
        def open_logs(*_):
            core.STATE_DIR.mkdir(parents=True, exist_ok=True)
            Gio.AppInfo.launch_default_for_uri(core.STATE_DIR.as_uri(), None)
        logs.connect('clicked', open_logs)
        diagnostics.pack_start(logs, False, False, 0)
        dialog.show_all()
        notebook.set_current_page(pages.get(page, 0))
        while dialog.run() == Gtk.ResponseType.OK:
            settings = dict(language=language.get_active_id() or 'auto', steam_on_open=on_open.get_active(),
                            autostart=autostart.get_active(), backend=backend.get_active_id() or 'native',
                            fps=int(fps.get_active_id() or '30'), scaling=scaling.get_active_id() or 'fill',
                            muted=not sound.get_active(), pause_fullscreen=fullscreen.get_active(),
                            pause_battery=battery.get_active(), steam_tracking=tracking.get_active())
            playback_keys = ('backend', 'fps', 'scaling', 'muted', 'steam_tracking')
            current = core.load_config()
            try:
                if current.get('selection') and (any(current.get(k) != settings[k] for k in playback_keys) or
                        (settings['backend'] == 'proton' and settings['steam_tracking'] and steam_integration.info()['configured'] and
                         core.status().get('launch_source') != 'steam')):
                    core.apply(current['selection']['path'], **settings)
                else:
                    core.save_config(**settings)
            except (ValueError, OSError) as error:
                self.message(localize(str(error)))
                continue
            dialog.destroy()
            self.get_application().rebuild_window()
            return
        dialog.destroy()

    def add_menu(self, button, entries):
        popover = Gtk.Popover(relative_to=button)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin=10)
        for text, action in entries:
            item = Gtk.Button(label=text)
            item.connect('clicked', lambda _, fn=action: (popover.popdown(), fn()))
            box.pack_start(item, False, False, 0)
        popover.add(box)
        box.show_all()
        button.set_popover(popover)

    @staticmethod
    def field(parent, text, widget):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.pack_start(label(text, 'muted'), False, False, 0)
        box.pack_start(widget, False, False, 0)
        parent.pack_start(box, False, False, 0)

    def switch(self, parent, text, key, default, invert=False):
        box = Gtk.Box(spacing=12)
        box.pack_start(label(text, wrap=True), True, True, 0)
        widget = Gtk.Switch(valign=Gtk.Align.CENTER, halign=Gtk.Align.END)
        widget.set_active(not self.config.get(key, default) if invert else self.config.get(key, default))
        widget.connect('notify::active', lambda w, _: core.save_config(**{key: not w.get_active() if invert else w.get_active()}))
        box.pack_end(widget, False, False, 0)
        parent.pack_start(box, False, False, 0)
        return widget

    def message(self, text):
        dialog = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.INFO,
                                   buttons=Gtk.ButtonsType.NONE, text=text)
        dialog.add_button(t('Cerrar'), Gtk.ResponseType.CLOSE)
        dialog.run()
        dialog.destroy()

    def refresh(self, quiet=False):
        if self.closed or not self.refresh_button.get_sensitive():
            return
        self.refresh_button.set_sensitive(False)
        if not quiet:
            self.empty.set_text(t('Buscando fondos…'))
            self.empty.set_visible(True)

        def scan():
            try:
                walls, errors = core.scan_library()
                downloads = core.workshop_status()
                GLib.idle_add(self.scan_ready, walls, errors, downloads, quiet)
            except Exception as error:
                GLib.idle_add(self.scan_ready, self.wallpapers, [str(error)], {}, quiet)
        threading.Thread(target=scan, daemon=True).start()

    def scan_ready(self, walls, errors, downloads, quiet=False):
        if self.closed:
            return False
        self.wallpapers = walls
        self.refresh_button.set_sensitive(True)
        revision = core.library_revision(walls)
        if revision != self.library_revision or not quiet:
            self.library_revision = revision
            self.filter()
        queue = downloads.get('queue', 'idle')
        messages = {
            'paused': t('Steam tiene la descarga de Workshop pausada. Reanúdala en Steam; los fondos aparecerán aquí al terminar.'),
            'downloading': t('Steam está descargando tus fondos de Workshop. Se añadirán automáticamente cuando terminen.'),
            'pending': t('Hay fondos de Workshop pendientes en Steam. Abre Descargas para comprobar o reanudar la cola.'),
        }
        self.workshop_text.set_text(messages.get(queue, ''))
        self.workshop_banner.set_visible(queue in messages)
        if queue in messages:
            for child in self.workshop_banner.get_children():
                child.show_all()
        missing = not core.renderer_path() or not core.find_assets()
        self.notice.set_text(t('Para usar escenas, instala el motor y Wallpaper Engine desde Steam.') if missing else '')
        self.notice.set_visible(missing)
        if errors:
            core.STATE_DIR.mkdir(parents=True, exist_ok=True)
            (core.STATE_DIR / 'biblioteca.log').write_text('\n'.join(errors))
        return False

    def watch_downloads(self):
        if self.closed:
            return False
        self.refresh(quiet=True)
        return True

    def open_steam(self, section):
        try:
            core.open_steam(section)
        except (OSError, ValueError) as error:
            self.message(localize(str(error)))

    def thumbnail(self, wall, width=204, height=116):
        if not wall.preview:
            return None
        try:
            key = (wall.preview, Path(wall.preview).stat().st_mtime_ns, width, height)
            if key not in self.thumbnails:
                self.thumbnails[key] = GdkPixbuf.Pixbuf.new_from_file_at_scale(wall.preview, width, height, True)
            return self.thumbnails[key]
        except (GLib.Error, OSError):
            return None

    def make_card(self, wall):
        child = Gtk.FlowBoxChild()
        child.wallpaper = wall
        child.set_tooltip_text(wall.title)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.get_style_context().add_class('wallpaper-card')
        preview = Gtk.Image()
        preview.set_size_request(204, 116)
        pixbuf = self.thumbnail(wall)
        if pixbuf:
            preview.set_from_pixbuf(pixbuf)
        else:
            preview.set_from_icon_name('video-x-generic' if wall.kind == 'video' else 'preferences-desktop-wallpaper', Gtk.IconSize.DIALOG)
        box.pack_start(preview, False, False, 0)
        title = label(wall.title, 'tile-title')
        title.set_ellipsize(Pango.EllipsizeMode.END)
        title.set_max_width_chars(22)
        box.pack_start(title, False, False, 0)
        box.pack_start(label(t(LABELS[wall.kind]), 'tile-kind'), False, False, 0)
        child.add(box)
        return child

    def filter(self):
        if self.closed:
            return
        query = self.search.get_text().casefold().strip()
        kind = self.filter_type.get_active_id() or ''
        selected = self.selected_path
        for child in self.flow.get_children():
            self.flow.remove(child)
        visible = [w for w in self.wallpapers if query in w.title.casefold() and (not kind or w.kind == kind)]
        self.count.set_text(t(t('{count} fondo') if len(visible) == 1 else t('{count} fondos'), count=len(visible)))
        selected_child = None
        for wall in visible[:self.shown_limit]:
            child = self.make_card(wall)
            self.flow.add(child)
            if wall.path == selected:
                selected_child = child
        self.flow.show_all()
        if selected_child:
            self.flow.select_child(selected_child)
        else:
            self.selected_path = None
            self.apply_button.set_sensitive(False)
            self.selected_label.set_text(t('Elige un fondo'))
            self.metadata.set_text(t('Selecciona una miniatura de la biblioteca.'))
            self.preview.set_from_icon_name('preferences-desktop-wallpaper', Gtk.IconSize.DIALOG)
        self.empty.set_text(t('No hay coincidencias.') if not visible and self.wallpapers else
                            t('Añade un archivo o descarga un fondo desde Steam Workshop.') if not visible else '')
        self.empty.set_visible(not visible)
        self.more.set_visible(len(visible) > self.shown_limit)

    def show_more(self, *_):
        self.shown_limit += 60
        self.filter()

    def selection(self):
        children = self.flow.get_selected_children()
        return children[0].wallpaper if children else None

    def selection_changed(self, *_):
        wall = self.selection()
        self.apply_button.set_sensitive(bool(wall))
        if not wall:
            return
        self.selected_path = wall.path
        self.selected_label.set_text(wall.title)
        source = 'Steam Workshop' if wall.workshop_id else t('Incluido en Wallpaper Engine') if '/defaultprojects/' in wall.path else t('Archivo local')
        self.metadata.set_text(t(LABELS[wall.kind]) + ' · ' + source)
        pixbuf = self.thumbnail(wall, 300, 172)
        if pixbuf:
            self.preview.set_from_pixbuf(pixbuf)
        else:
            self.preview.set_from_icon_name('video-x-generic', Gtk.IconSize.DIALOG)

    def apply(self):
        wall = self.selection()
        if wall is None:
            return
        try:
            core.apply(wall.path, backend=self.backend.get_active_id() or 'native', output=self.output.get_active_id() or '*',
                       scaling=self.scaling.get_active_id() or 'fill',
                       fps=int(self.fps.get_active_id() or '30'), muted=not self.sound.get_active(),
                       pause_fullscreen=self.fullscreen.get_active(), pause_battery=self.battery.get_active(),
                       autostart=self.autostart.get_active())
            self.status_label.set_text(t('Preparando {title}…', title=wall.title))
        except (ValueError, OSError) as error:
            self.message(localize(str(error)))

    def toggle_pause(self, *_):
        core.save_config(manual_paused=not core.load_config().get('manual_paused', False))
        try:
            if core.load_config().get('selection'):
                core.ensure_daemon()
        except (ValueError, OSError) as error:
            self.message(localize(str(error)))

    def stop(self):
        core.save_config(selection=None, manual_paused=False)
        try:
            core.ensure_daemon()
            self.status_label.set_text(t('Restaurando el fondo estático…'))
        except (ValueError, OSError) as error:
            self.message(localize(str(error)))

    def update_status(self):
        if self.closed:
            return False
        state = core.status()
        phase = state.get('status', 'detenido')
        detail = localize(state.get('detail', ''))
        paused = core.load_config().get('manual_paused', False)
        summary = (phase, detail, paused, state.get('launch_source'))
        if summary != self.last_status:
            text = {'activo': t('Reproduciendo'), 'pausado': t('En pausa'), 'cargando': t('Cargando'),
                    'espera': t('Fondo estático'), 'detenido': t('Listo para aplicar'), 'error': t('No se pudo aplicar')}.get(phase, phase)
            if state.get('launch_source') == 'steam':
                text += ' · Steam'
            self.status_label.set_text(text + ('\n' + detail if detail and phase not in ('espera', 'detenido') else ''))
            self.pause.set_label(t('Reanudar') if paused else t('Pausar'))
            self.pause.set_sensitive(bool(core.load_config().get('selection')))
            self.last_status = summary
        return True

    def add_source(self, folder):
        dialog = Gtk.FileChooserDialog(title=t('Añadir carpeta de fondos') if folder else t('Añadir un fondo'),
                                      transient_for=self,
                                      action=Gtk.FileChooserAction.SELECT_FOLDER if folder else Gtk.FileChooserAction.OPEN)
        dialog.add_buttons(t('Cancelar'), Gtk.ResponseType.CANCEL, t('Añadir'), Gtk.ResponseType.OK)
        if dialog.run() == Gtk.ResponseType.OK:
            path = dialog.get_filename()
            key = 'library_paths' if folder else 'files'
            values = core.load_config().get(key, [])
            if path and path not in values:
                core.save_config(**{key: [*values, path]})
            self.refresh()
        dialog.destroy()

    def choose_assets(self):
        dialog = Gtk.FileChooserDialog(title=t('Carpeta de Wallpaper Engine'), transient_for=self,
                                      action=Gtk.FileChooserAction.SELECT_FOLDER)
        dialog.add_buttons(t('Cancelar'), Gtk.ResponseType.CANCEL, t('Usar carpeta'), Gtk.ResponseType.OK)
        if dialog.run() == Gtk.ResponseType.OK:
            path = Path(dialog.get_filename())
            if (path / 'assets').is_dir():
                path /= 'assets'
            core.save_config(assets_dir=str(path))
            self.refresh()
        dialog.destroy()

    def install_renderer(self):
        try:
            subprocess.Popen(['kitty', '--title', t('Instalar motor de Wallpaper Engine'),
                              'bash', str(core.PROJECT / 'install-renderer.sh')], start_new_session=True)
        except OSError as error:
            self.message(localize(str(error)))


class Application(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='io.github.iago.NinetalesWallpapers')
        self.window = None
        self.start_requested = False

    def do_startup(self):
        Gtk.Application.do_startup(self)
        Gtk.Settings.get_default().set_property('gtk-application-prefer-dark-theme', True)
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_activate(self):
        if self.window is None:
            self.window = Window(self)
            self.window.connect('destroy', self.window_destroyed)
            self.window.show_all()
        self.window.present()
        if not self.start_requested:
            self.start_requested = True
            GLib.idle_add(self.start_wallpaper)

    def start_wallpaper(self):
        conf = core.load_config()
        if not self.window or not conf.get('steam_on_open', True):
            return False
        if not conf.get('selection') and conf.get('backend') == 'proton':
            initial = core.initial_wallpaper()
            if initial:
                conf = core.save_config(selection=initial.as_dict())
                self.window.selected_path = initial.path
        if not conf.get('selection'):
            return False
        try:
            if conf.get('backend') == 'proton' and conf.get('steam_tracking', True):
                from .steam_integration import info
                if not info()['configured']:
                    self.window.show_settings(page='steam')
                    return False
            core.ensure_daemon()
        except (OSError, ValueError) as error:
            self.window.message(localize(str(error)))
        return False

    def rebuild_window(self):
        old = self.window
        self.window = Window(self)
        self.window.connect('destroy', self.window_destroyed)
        self.window.show_all()
        self.window.present()
        old.destroy()

    def window_destroyed(self, window):
        if self.window is window:
            self.window = None


def main():
    return Application().run(['ninetales-wallpapers'])
