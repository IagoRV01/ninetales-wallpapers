import io
import json
import os
import subprocess
import sys
from pathlib import Path
import signal
import string
import time
import unittest
from unittest.mock import Mock, patch

from ninetales_wallpapers import core, i18n, steam_integration as steam
from test_wallpapers import Environment


class TranslationTests(unittest.TestCase):
    def tearDown(self):
        i18n.configure('es')

    def test_all_four_catalogs_have_identical_keys_and_placeholders(self):
        directory = Path(i18n.__file__).parent / 'locales'
        catalogs = {lang: json.loads((directory / (lang + '.json')).read_text()) for lang in ('es', 'en', 'fr', 'pt')}
        formatter = string.Formatter()
        for lang, catalog in catalogs.items():
            self.assertEqual(set(catalog), set(catalogs['es']), lang)
            for source, translated in catalog.items():
                fields = lambda text: {name for _, name, _, _ in formatter.parse(text) if name}
                self.assertTrue(translated.strip(), (lang, source))
                self.assertEqual(fields(source), fields(translated), (lang, source))

    def test_regional_locale_detection_and_fallback(self):
        self.assertEqual(i18n.resolve_language('auto', {'LANGUAGE': 'fr_FR:en', 'LANG': 'es_ES.UTF-8'}), 'fr')
        self.assertEqual(i18n.resolve_language('auto', {'LC_ALL': 'pt_BR.UTF-8'}), 'pt')
        self.assertEqual(i18n.resolve_language('auto', {'LANG': 'C.UTF-8'}), 'en')
        self.assertEqual(i18n.resolve_language('es', {'LANG': 'en_US'}), 'es')

    def test_switching_language_and_supervisor_template_translation(self):
        for lang, settings in (('en', 'Settings'), ('fr', 'Paramètres'), ('pt', 'Definições'), ('es', 'Ajustes')):
            i18n.configure(lang)
            self.assertEqual(i18n.t('Ajustes'), settings)
            message = i18n.localize('Preparando Ninetales "冰"…')
            self.assertIn('Ninetales "冰"', message)
        i18n.configure('en')
        self.assertEqual(i18n.t('{count} fondos', count=12), '12 wallpapers')
        self.assertEqual(i18n.localize('Technical codec message #12'), 'Technical codec message #12')


class SteamIntegrationTests(Environment):
    def setUp(self):
        super().setUp()
        self.request_patch = patch.object(steam, 'REQUEST', core.STATE_DIR / 'request.json')
        self.runtime_patch = patch.object(steam, 'RUNTIME', core.STATE_DIR / 'bridge.json')
        self.request_patch.start()
        self.runtime_patch.start()

    def tearDown(self):
        self.runtime_patch.stop()
        self.request_patch.stop()
        super().tearDown()

    def preference_file(self, options, playtime='125'):
        file = self.home / 'localconfig.vdf'
        escaped = options.replace('\\', '\\\\').replace('"', '\\"')
        file.write_text('"UserLocalConfigStore" { "Software" { "Valve" { "Steam" { "apps" { "431960" { "LaunchOptions" "' + escaped + '" "Playtime" "' + playtime + '" } } } } } }')
        return file

    def test_detects_real_launch_options_and_reads_playtime_without_writing_it(self):
        file = self.preference_file(steam.launch_options())
        before = file.read_bytes()
        with patch.object(steam, 'preferences', return_value=file):
            info = steam.info()
        self.assertTrue(info['configured'])
        self.assertEqual(info['playtime_minutes'], 125)
        self.assertEqual(file.read_bytes(), before)

    def test_missing_configuration_and_corrupt_playtime_are_not_reported_as_tracking(self):
        file = self.preference_file('unrelated wrapper %command%', 'bad')
        with patch.object(steam, 'preferences', return_value=file):
            info = steam.info()
        self.assertFalse(info['configured'])
        self.assertIsNone(info['playtime_minutes'])

    def test_launch_wrapper_requires_a_steam_launch(self):
        with patch.dict(os.environ, {'SteamAppId': '0'}):
            with self.assertRaisesRegex(ValueError, 'Steam'):
                steam.wrapper(['/Steam/launcher.exe'])
        self.assertFalse(steam.RUNTIME.exists())

    def test_play_in_steam_without_companion_request_preserves_genuine_command(self):
        command = ['/Steam/steam-launch-wrapper', '--', '/Steam/Proton Experimental/proton',
                   'waitforexitandrun', '/Steam/wallpaper_engine/launcher.exe', '-run', 'wallpaper64.exe']
        core.save_config(backend='native')
        before = core.CONFIG.read_bytes()
        with patch.dict(os.environ, {'SteamAppId': '431960'}), \
             patch('ninetales_wallpapers.steam_integration.os.execvpe', return_value=0) as run:
            self.assertEqual(steam.wrapper(command), 0)
        self.assertEqual(run.call_args.args[:2], (command[0], command))
        self.assertEqual(core.CONFIG.read_bytes(), before)
        self.assertFalse(steam.RUNTIME.exists())

    def test_expired_request_also_preserves_steam_play(self):
        core.atomic_json(steam.REQUEST, {'id': 'expired', 'created': time.time() - 500})
        with patch.dict(os.environ, {'SteamAppId': '431960'}), \
             patch('ninetales_wallpapers.steam_integration.os.execvpe', return_value=17):
            self.assertEqual(steam.wrapper(['/Steam/launcher.exe']), 17)

    def test_cli_wrapper_preserves_real_child_arguments_and_exit_status(self):
        env = dict(os.environ, XDG_CONFIG_HOME=str(self.home / 'isolated-config'),
                   XDG_STATE_HOME=str(self.home / 'isolated-state'), SteamAppId='431960')
        result = subprocess.run([sys.executable, '-m', 'ninetales_wallpapers', 'steam-wrapper', '--',
                                 sys.executable, '-c', 'import sys; print(sys.argv[1]); sys.exit(7)',
                                 'STEAM ARGUMENT WITH SPACES'], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertEqual(result.stdout.strip(), 'STEAM ARGUMENT WITH SPACES')

    def test_wrapper_reports_frames_and_final_state_from_its_own_request(self):
        core.atomic_json(steam.REQUEST, {'id': 'fixture-request', 'created': time.time(),
                         'environment': {'XDG_RUNTIME_DIR': str(self.home / 'runtime'),
                                         'HYPRLAND_INSTANCE_SIGNATURE': 'fixture'}})
        def make_bridge(on_ready, output=None):
            output.write('OFFICIAL_RENDERER_LOG_FIXTURE\n')
            return Mock(run=lambda: on_ready('eDP-1'))
        with patch.dict(os.environ, {'SteamAppId': '431960'}), \
             patch.object(Path, 'is_socket', return_value=True), \
             patch('ninetales_wallpapers.proton_bridge.Bridge', side_effect=make_bridge):
            steam.wrapper(['/Steam/proton', 'waitforexitandrun', '/Steam/launcher.exe'])
        state = core.read_json(steam.RUNTIME, {})
        self.assertEqual(state['request_id'], 'fixture-request')
        self.assertEqual(state['ready_outputs'], ['eDP-1'])
        self.assertEqual(state['launch_source'], 'steam')
        self.assertTrue(state['stopped'])
        self.assertIn('OFFICIAL_RENDERER_LOG_FIXTURE', (core.STATE_DIR / 'official-renderer.log').read_text())

    def test_never_signals_an_unrelated_same_user_process(self):
        with patch('ninetales_wallpapers.steam_integration.os.kill') as kill:
            self.assertFalse(steam.bridge_signal({'pid': os.getpid()}, signal.SIGTERM))
            kill.assert_not_called()

    def test_tracking_validation_requires_the_real_steam_hook(self):
        with patch('ninetales_wallpapers.proton.validate'), patch.object(steam, 'info', return_value={'configured': False}):
            with self.assertRaisesRegex(ValueError, 'Steam'):
                steam.validate()

    def test_initial_official_wallpaper_comes_only_from_a_completed_installed_default(self):
        library = self.home / 'Steam'
        expected = self.project('Steam/steamapps/common/wallpaper_engine/projects/defaultprojects/deep_space')
        wall = core.initial_wallpaper([library])
        self.assertEqual(wall.path, str(expected))
        self.assertEqual(wall.kind, 'scene')

    def test_initial_official_wallpaper_does_not_use_partial_downloads(self):
        library = self.home / 'Steam'
        self.project('Steam/steamapps/workshop/downloads/431960/123')
        self.assertIsNone(core.initial_wallpaper([library]))

    def test_stale_other_launch_cannot_report_readiness(self):
        def old_launch(_):
            core.atomic_json(steam.RUNTIME, {'request_id': 'previous-launch', 'heartbeat': time.time(),
                                           'pid': 12345, 'ready_outputs': ['eDP-1']})
        output = io.StringIO()
        with patch.object(steam, 'validate'), patch.object(core, 'open_steam', side_effect=old_launch), \
             patch('ninetales_wallpapers.steam_integration.signal.signal'), \
             patch('ninetales_wallpapers.steam_integration.time.monotonic', side_effect=[0, 101]), \
             patch.object(steam, 'bridge_signal') as kill, patch('sys.stdout', output):
            with self.assertRaisesRegex(ValueError, 'Steam'):
                steam.supervise()
        self.assertEqual(output.getvalue(), '')
        kill.assert_not_called()
        self.assertFalse(steam.REQUEST.exists())

    def test_qt_player_drops_steam_library_injection(self):
        with patch.dict(os.environ, {'NW_STEAM_BRIDGE': '1', 'LD_PRELOAD': '/Steam/overlay.so', 'LD_LIBRARY_PATH': '/Steam/libs'}), \
             patch.object(core, 'quickshell_path', return_value='/qs'):
            env = core.qt_environment()
        self.assertNotIn('LD_PRELOAD', env)
        self.assertNotIn('LD_LIBRARY_PATH', env)

    def test_direct_proton_opt_out_does_not_require_the_steam_hook(self):
        project = self.project()
        with patch('ninetales_wallpapers.proton.validate'), patch.object(steam, 'validate') as validate, \
             patch.object(core, 'ensure_daemon'):
            core.apply(str(project), backend='proton', steam_tracking=False)
        validate.assert_not_called()
        self.assertFalse(core.load_config()['steam_tracking'])

    def test_supervisor_launches_steam_and_reports_only_acknowledged_output_frames(self):
        def open_steam(section):
            self.assertEqual(section, 'wallpaper-engine')
            request = core.read_json(steam.REQUEST, {})
            core.atomic_json(steam.RUNTIME, {'request_id': request['id'], 'heartbeat': time.time(),
                                           'pid': 12345, 'ready_outputs': ['eDP-1']})
        stdout = io.StringIO()
        def stop_loop(_):
            state = core.read_json(steam.RUNTIME, {})
            state.update(stopped=True, error='fixture-stop')
            core.atomic_json(steam.RUNTIME, state)
        with patch.object(steam, 'validate'), patch.object(core, 'open_steam', side_effect=open_steam), \
             patch('ninetales_wallpapers.steam_integration.signal.signal'), \
             patch('ninetales_wallpapers.steam_integration.time.sleep', side_effect=stop_loop), \
             patch.object(steam, 'bridge_signal', return_value=True), patch('sys.stdout', stdout):
            with self.assertRaisesRegex(ValueError, 'fixture-stop'):
                steam.supervise()
        self.assertEqual(stdout.getvalue().count('NW_READY:eDP-1'), 1)
        self.assertFalse(steam.REQUEST.exists())


if __name__ == '__main__':
    unittest.main()
