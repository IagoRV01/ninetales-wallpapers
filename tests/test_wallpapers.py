import json
from pathlib import Path
import signal
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from ninetales_wallpapers import core
from ninetales_wallpapers.daemon import Daemon, layer_outputs, pause_reason


class Environment(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.patches = [patch.object(core, name, value) for name, value in {
            'HOME': self.home, 'CONFIG_DIR': self.home / 'config', 'CONFIG': self.home / 'config/config.json',
            'STATE_DIR': self.home / 'state', 'STATUS': self.home / 'state/runtime.json',
        }.items()]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def project(self, path='project', kind='scene', **values):
        root = self.home / path
        root.mkdir(parents=True, exist_ok=True)
        (root / 'project.json').write_text(json.dumps(dict(type=kind, file='scene.json', title='Ninetales', **values)))
        return root


class LibraryTests(Environment):
    def test_vdf_preserves_unicode_and_quoted_paths(self):
        value = core.parse_vdf('"libraryfolders" { "1" { "path" "/disco Vídeos/A \\"B\\"" } }')
        self.assertEqual(value['libraryfolders']['1']['path'], '/disco Vídeos/A "B"')

    def test_invalid_vdf_is_rejected(self):
        for text in ('"a" { "b" "c"', '}', '"a"'):
            with self.assertRaises(ValueError):
                core.parse_vdf(text)

    def test_multiple_steam_libraries_and_custom_install_name(self):
        steam = self.home / '.local/share/Steam'
        (steam / 'steamapps').mkdir(parents=True)
        second = self.home / 'Juegos y fondos'
        (second / 'steamapps/common/Mis Fondos/assets').mkdir(parents=True)
        (steam / 'steamapps/libraryfolders.vdf').write_text('"libraryfolders" { "1" { "path" "' + str(second) + '" } }')
        (second / 'steamapps/appmanifest_431960.acf').write_text('"AppState" { "installdir" "Mis Fondos" }')
        libraries = core.steam_libraries(self.home)
        self.assertEqual(set(libraries), {steam, second})
        self.assertEqual(core.find_assets(libraries), second / 'steamapps/common/Mis Fondos/assets')

    def test_empty_library_path_does_not_scan_current_directory(self):
        steam = self.home / '.local/share/Steam'
        (steam / 'steamapps').mkdir(parents=True)
        (steam / 'steamapps/libraryfolders.vdf').write_text('"libraryfolders" { "1" {} }')
        self.assertEqual(core.steam_libraries(self.home), [steam])

    def test_scene_allows_resources_inside_package(self):
        root = self.project()
        (root / 'scene.pkg').write_bytes(b'fixture')
        wall = core.wallpaper_from_path(root)
        self.assertEqual(wall.kind, 'scene')
        self.assertEqual(wall.media, '')

    def test_legacy_examples_infer_scene_without_running_executables(self):
        root = self.project()
        data = json.loads((root / 'project.json').read_text())
        del data['type']
        (root / 'project.json').write_text(json.dumps(data))
        self.assertEqual(core.wallpaper_from_path(root).kind, 'scene')
        data['file'] = 'sheep.exe'
        (root / 'project.json').write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            core.wallpaper_from_path(root)

    def test_default_wallpapers_are_discovered(self):
        library = self.home / 'Steam'
        self.project('Steam/steamapps/common/wallpaper_engine/projects/defaultprojects/deep_space')
        walls, errors = core.scan_library({'files': [], 'library_paths': []}, [library])
        self.assertEqual(len(walls), 1)
        self.assertEqual(walls[0].title, 'Ninetales')
        self.assertFalse(errors)

    def test_project_cannot_read_preview_outside_its_folder(self):
        root = self.project(preview='../secret.txt')
        with self.assertRaisesRegex(ValueError, 'fuera'):
            core.wallpaper_from_path(root)

    def test_project_cannot_read_video_outside_its_folder(self):
        root = self.project(kind='video')
        data = json.loads((root / 'project.json').read_text())
        data['file'] = '../secret.mp4'
        (root / 'project.json').write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'fuera'):
            core.wallpaper_from_path(root)

    def test_media_uri_encodes_spaces_hash_and_unicode(self):
        file = self.home / 'Vídeo #1 "a".mp4'
        file.write_bytes(b'fixture')
        data = core.wallpaper_from_path(file).as_dict()
        self.assertIn('%23', data['media_uri'])
        self.assertIn('%22', data['media_uri'])
        self.assertNotIn(' ', data['media_uri'])

    def test_scan_deduplicates_steam_and_manual_folder(self):
        library = self.home / 'Steam'
        root = self.project('Steam/steamapps/workshop/content/431960/12345')
        walls, errors = core.scan_library({'files': [], 'library_paths': [str(root)]}, [library])
        self.assertEqual(len(walls), 1)
        self.assertEqual(walls[0].workshop_id, '12345')
        self.assertFalse(errors)

    def test_unsupported_projects_report_errors_without_hiding_valid_ones(self):
        valid = self.home / 'clip.webm'
        valid.write_bytes(b'fixture')
        invalid = self.project('bad', kind='application')
        walls, errors = core.scan_library({'files': [str(valid), str(invalid)], 'library_paths': []}, [])
        self.assertEqual(len(walls), 1)
        self.assertEqual(len(errors), 1)

    def test_scene_command_keeps_paths_as_arguments_and_targets_each_output(self):
        root = self.project('a $(touch NO) "quoted"')
        wall = core.wallpaper_from_path(root)
        cmd = core.scene_command(wall, core.DEFAULTS, ['eDP-1', 'HDMI-A-1'], self.home / 'assets', '/motor')
        self.assertEqual(cmd.count(wall.path), 2)
        self.assertEqual(cmd[cmd.index('--bg') + 1], str(root))
        self.assertIn('--silent', cmd)
        self.assertEqual(cmd.count('--screen-root'), 2)
        self.assertEqual(cmd[cmd.index('--layer') + 1], 'background')
        self.assertIn('--no-fullscreen-pause', cmd)
        self.assertEqual(cmd.count('--scaling'), 2)
        for index, arg in enumerate(cmd):
            if arg == '--scaling':
                self.assertEqual(cmd[index - 2], '--bg')

    def test_scene_rejects_missing_assets_and_bad_settings(self):
        wall = core.wallpaper_from_path(self.project())
        with self.assertRaisesRegex(ValueError, 'Steam'):
            core.scene_command(wall, core.DEFAULTS, ['eDP-1'], None, '/motor')
        with self.assertRaisesRegex(ValueError, 'FPS'):
            core.scene_command(wall, {'fps': 999}, ['eDP-1'], self.home, '/motor')


class WorkshopTests(Environment):
    def manifest(self, library, text):
        p = library / 'steamapps/workshop/appworkshop_431960.acf'
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def test_pending_download_is_visible_but_partial_files_are_not_playable(self):
        library = self.home / 'Steam'
        self.manifest(library, '"AppWorkshop" { "NeedsDownload" "1" "WorkshopItemDetails" { "123" {} } }')
        self.project('Steam/steamapps/workshop/downloads/431960/123')
        state = core.workshop_status([library])
        self.assertEqual(state['pending'], 1)
        self.assertEqual(state['installed'], 0)
        walls, _ = core.scan_library({'files': [], 'library_paths': []}, [library])
        self.assertFalse(walls)

    def test_completed_download_appears_on_the_next_scan(self):
        library = self.home / 'Steam'
        conf = {'files': [], 'library_paths': []}
        before, _ = core.scan_library(conf, [library])
        self.project('Steam/steamapps/workshop/content/431960/123')
        self.manifest(library, '"AppWorkshop" { "NeedsDownload" "0" "WorkshopItemDetails" { "123" {} } "WorkshopItemsInstalled" { "123" {} } }')
        after, _ = core.scan_library(conf, [library])
        self.assertNotEqual(core.library_revision(before), core.library_revision(after))
        self.assertEqual(after[0].workshop_id, '123')
        state = core.workshop_status([library])
        self.assertEqual(state['installed'], 1)
        self.assertEqual(state['pending'], 0)
        self.assertEqual(state['queue'], 'idle')

    def test_paused_and_resumed_workshop_jobs_are_recognized(self):
        library = self.home / 'Steam'
        self.manifest(library, '"AppWorkshop" { "NeedsDownload" "1" "WorkshopItemDetails" { "123" {} } }')
        log = library / 'logs/workshop_log.txt'
        log.parent.mkdir()
        log.write_text('[AppID 431960] Starting Workshop download job\n[AppID 431960] Update canceled: Disabled (Suspended)\n[AppID 431960] Subscribed to item 999\n')
        self.assertEqual(core.workshop_status([library])['queue'], 'paused')
        with log.open('a') as out:
            out.write('[AppID 431960] Starting Workshop download job\n')
        self.assertEqual(core.workshop_status([library])['queue'], 'downloading')

    def test_old_cached_subscriptions_do_not_show_as_pending(self):
        library = self.home / 'Steam'
        self.manifest(library, '"AppWorkshop" { "NeedsDownload" "0" "WorkshopItemDetails" { "123" {} } }')
        self.assertEqual(core.workshop_status([library])['pending'], 0)

    def test_incomplete_manifest_does_not_crash_monitoring(self):
        library = self.home / 'Steam'
        self.manifest(library, '"AppWorkshop" {')
        self.assertEqual(core.workshop_status([library])['queue'], 'idle')

    def test_changed_preview_updates_the_library_revision(self):
        preview = self.home / 'preview.jpg'
        preview.write_bytes(b'fixture')
        wall = core.Wallpaper('/wallpaper', 'Title', 'scene', preview=str(preview))
        before = core.library_revision([wall])
        import os
        stamp = preview.stat().st_mtime_ns + 1000000
        os.utime(preview, ns=(stamp, stamp))
        self.assertNotEqual(before, core.library_revision([wall]))

    def test_workshop_and_downloads_open_through_the_native_client(self):
        launcher = self.home / '.local/bin/steam'
        launcher.parent.mkdir(parents=True)
        launcher.write_text('#!/bin/sh\n')
        launcher.chmod(0o755)
        with patch('ninetales_wallpapers.core.subprocess.Popen') as launch, \
             patch('ninetales_wallpapers.desktop.desktop_environment', return_value={'DISPLAY': ':3'}):
            core.open_steam('workshop')
            self.assertEqual(launch.call_args.args[0], [str(launcher), 'steam://openurl/https://steamcommunity.com/app/431960/workshop/'])
            core.open_steam('downloads')
            self.assertEqual(launch.call_args.args[0], [str(launcher), 'steam://open/downloads'])
        with self.assertRaises(ValueError):
            core.open_steam('arbitrary://command')


class SupervisorTests(Environment):
    def test_atomic_config_roundtrip_and_invalid_config_fallback(self):
        core.save_config(output='Pantalla Ñ', fps=24)
        self.assertEqual(core.load_config()['output'], 'Pantalla Ñ')
        core.CONFIG.write_text('{')
        self.assertEqual(core.load_config()['fps'], 30)

    def test_stale_heartbeat_never_keeps_wallpaper_active(self):
        core.atomic_json(core.STATUS, {'heartbeat': (time.time() - 60) * 1000, 'active': True, 'status': 'activo'})
        self.assertFalse(core.status()['active'])
        core.atomic_json(core.STATUS, [])
        self.assertFalse(core.status()['active'])

    def test_only_our_mapped_layers_count_as_ready(self):
        data = {'eDP-1': {'levels': {'0': [{'pid': 42, 'mapped': True}]}},
                'HDMI-A-1': {'levels': {'0': [{'pid': 99}]}},
                'DP-1': {'levels': {'0': [{'pid': 42, 'mapped': False}]}}}
        self.assertEqual(layer_outputs(data, 42), ['eDP-1'])

    def test_manual_pause_survives_fullscreen_and_power_changes(self):
        self.assertEqual(pause_reason({'manual_paused': True}, [], [], {}), 'Pausado por ti')

    def test_fullscreen_on_another_monitor_does_not_pause(self):
        screens = [{'name': 'eDP-1', 'id': 0}, {'name': 'HDMI-A-1', 'id': 1}]
        config = {'pause_fullscreen': True}
        self.assertFalse(pause_reason(config, ['eDP-1'], screens, {'fullscreen': 2, 'monitor': 1}))
        self.assertTrue(pause_reason(config, ['eDP-1'], screens, {'fullscreen': 2, 'monitor': 0}))

    def test_battery_pause_is_optional(self):
        with patch('ninetales_wallpapers.daemon.on_battery', return_value=True):
            self.assertTrue(pause_reason({'pause_battery': True}, [], [], {}))
            self.assertFalse(pause_reason({'pause_battery': False}, [], [], {}))

    def test_paused_child_is_continued_before_shutdown(self):
        daemon = Daemon()
        daemon.child = Mock(pid=123)
        daemon.child.poll.return_value = None
        daemon.paused = True
        with patch('ninetales_wallpapers.daemon.os.killpg') as kill:
            daemon.stop_child()
        self.assertEqual(kill.call_args_list[0].args, (123, signal.SIGCONT))
        self.assertEqual(kill.call_args_list[1].args, (123, signal.SIGTERM))
        self.assertFalse(daemon.ready)

    def test_crashed_renderer_does_not_restart_in_a_loop(self):
        daemon = Daemon()
        config = {**core.DEFAULTS, 'selection': {'path': '/fixture'}}
        count = 0

        def start(*_):
            nonlocal count
            count += 1
            daemon.child = Mock(pid=123)
            daemon.child.poll.return_value = 1

        iterations = 0

        def sleep(_):
            nonlocal iterations
            iterations += 1
            if iterations == 3:
                daemon.running = False

        with patch.object(daemon, 'start', side_effect=start), patch.object(core, 'load_config', return_value=config), \
             patch.object(daemon, 'session_alive', return_value=True), \
             patch.object(core, 'monitors', return_value=[{'name': 'eDP-1'}]), \
             patch('ninetales_wallpapers.daemon.time.sleep', side_effect=sleep), \
             patch('ninetales_wallpapers.daemon.signal.signal'):
            daemon.run()
        self.assertEqual(count, 1)
        self.assertFalse(core.status()['active'])

    def test_closing_hyprland_stops_the_supervisor(self):
        daemon = Daemon()
        with patch.object(daemon, 'session_alive', return_value=False), \
             patch('ninetales_wallpapers.daemon.signal.signal'):
            daemon.run()
        state = core.read_json(core.STATUS, {})
        self.assertFalse(state['active'])
        self.assertEqual(state['status'], 'detenido')


if __name__ == '__main__':
    unittest.main()
