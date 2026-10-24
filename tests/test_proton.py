import os
from pathlib import Path
import signal
import tempfile
import unittest
from unittest.mock import Mock, patch

from ninetales_wallpapers import core, proton
from ninetales_wallpapers.proton_bridge import Bridge
from test_wallpapers import Environment


class ProtonTests(Environment):
    def test_discovers_distribution_executable_and_proton_in_external_library(self):
        library = self.home / 'Steam Library'
        exe = library / 'steamapps/common/wallpaper_engine/distribution/wallpaper64.exe'
        runner = library / 'steamapps/common/Proton - Experimental/proton'
        for file in (exe, runner):
            file.parent.mkdir(parents=True, exist_ok=True)
            file.touch()
            file.chmod(0o755)
        found = proton.discover({}, [library])
        self.assertEqual(found['exe'], str(exe))
        self.assertEqual(found['proton'], str(runner))

    def test_windows_paths_and_titles_remain_individual_arguments(self):
        found = {'proton': '/Proton Experimental/proton', 'exe': '/Steam/distribution/wallpaper64.exe'}
        root = self.project('Workshop/123 a $(touch nope)')
        wall = core.wallpaper_from_path(root)
        cmd = proton.open_command(found, wall, 'Private title', 1920, 1080)
        self.assertEqual(cmd[:3], [found['proton'], 'runinprefix', found['exe']])
        self.assertEqual(cmd[cmd.index('-file') + 1], 'Z:' + str(root / 'project.json').replace('/', '\\'))
        self.assertEqual(cmd[cmd.index('-playInWindow') + 1], 'Private title')
        self.assertIn('-borderless', cmd)

    def test_official_validation_failure_preserves_selection(self):
        core.save_config(selection={'path': '/previous'}, backend='native')
        root = self.project()
        with patch.object(proton, 'validate', side_effect=ValueError('Missing Xvfb')):
            with self.assertRaisesRegex(ValueError, 'Xvfb'):
                core.apply(str(root), backend='proton')
        self.assertEqual(core.load_config()['selection'], {'path': '/previous'})
        self.assertEqual(core.load_config()['backend'], 'native')

    def test_invalid_backend_rejected_before_saving(self):
        root = self.project()
        with self.assertRaisesRegex(ValueError, 'Motor'):
            core.apply(str(root), backend='arbitrary')
        self.assertFalse(core.CONFIG.exists())

    def test_private_environment_never_uses_steam_prefix_or_wayland(self):
        prefix = self.home / 'our prefix'
        found = {'steam': '/Steam'}
        with patch.dict(os.environ, {'WAYLAND_DISPLAY': 'wayland-1', 'QT_PLUGIN_PATH': '/wrong', 'WINEPREFIX': '/foreign'}):
            env = proton.environment(found, ':123', self.home / 'authority', prefix)
        self.assertEqual(env['WINEPREFIX'], str(prefix / 'pfx'))
        self.assertEqual(env['STEAM_COMPAT_DATA_PATH'], str(prefix))
        self.assertEqual(env['DISPLAY'], ':123')
        self.assertNotIn('WAYLAND_DISPLAY', env)
        self.assertNotIn('QT_PLUGIN_PATH', env)
        self.assertEqual(env['PROTON_USE_WINED3D'], '1')

    def test_capture_targets_exact_private_window_and_independent_streams(self):
        cmd = proton.capture_command(':123', '0x123', 1920, 1080, 30,
                                    [Path('/private/one.ts'), Path('/private/two.ts')])
        self.assertEqual(cmd[cmd.index('-window_id') + 1], '0x123')
        self.assertEqual(cmd[cmd.index('-i') + 1], ':123')
        self.assertIn('[f=mpegts:onfail=abort]/private/one.ts|[f=mpegts:onfail=abort]/private/two.ts', cmd)
        for dimensions in ((0, 1080), (1920, -1), (20000, 1080)):
            with self.assertRaises(ValueError):
                proton.capture_command(':123', '0x123', *dimensions, 30, [])

    def test_prefix_seed_preserves_symlinks_and_original_registry(self):
        library = self.home / 'Steam'
        seed = library / 'steamapps/compatdata/431960/pfx'
        (seed / 'dosdevices').mkdir(parents=True)
        (seed / 'user.reg').write_text('original')
        (seed / 'dosdevices/z:').symlink_to('/')
        bridge = Bridge()
        with patch.object(core, 'steam_libraries', return_value=[library]):
            bridge.seed_prefix()
        clone = bridge.prefix / 'pfx'
        self.assertTrue((clone / 'dosdevices/z:').is_symlink())
        (clone / 'user.reg').write_text('changed')
        self.assertEqual((seed / 'user.reg').read_text(), 'original')

    def test_failed_proton_start_is_reported_before_waiting_for_a_wallpaper_window(self):
        import io
        project = self.project()
        core.save_config(selection=core.wallpaper_from_path(project).as_dict())
        bridge = Bridge()
        server = Mock()
        server.poll.return_value = None
        startup = Mock(returncode=23)
        startup.poll.return_value = 23
        found = {'proton': '/fixture/proton', 'exe': '/fixture/wallpaper64.exe', 'steam': '/fixture/Steam'}
        def launch(argv, **kwargs):
            if argv[0] == 'Xvfb':
                os.write(kwargs['pass_fds'][0], b'99\n')
                return server
            return startup
        with patch('ninetales_wallpapers.proton.validate', return_value=found), \
             patch.object(core, 'monitors', return_value=[{'name': 'eDP-1', 'width': 1920, 'height': 1080}]), \
             patch.object(bridge, 'seed_prefix'), patch.object(bridge, 'launch', side_effect=launch), \
             patch('ninetales_wallpapers.proton_bridge.subprocess.run', return_value=Mock(returncode=0, stdout='root', stderr='')), \
             patch('sys.stdout', io.StringIO()):
            with self.assertRaisesRegex(ValueError, '23'):
                bridge.play()

    def test_control_commands_do_not_start_another_steam_game_bootstrap(self):
        found = {'proton': '/Proton/proton', 'exe': '/Engine/wallpaper64.exe'}
        self.assertEqual(proton.command(found, '-silent'), ['/Proton/proton', 'run', '/Engine/wallpaper64.exe', '-silent'])
        self.assertEqual(proton.control_command(found, 'unmute'),
                         ['/Proton/proton', 'runinprefix', '/Engine/wallpaper64.exe', '-control', 'unmute'])

    def test_private_display_files_remain_until_process_cleanup_on_failure(self):
        bridge = Bridge()
        seen = []
        directory = None
        def cleanup():
            seen.append(Path(directory).is_dir())
        with patch.object(bridge, 'cleanup', side_effect=cleanup):
            with self.assertRaisesRegex(ValueError, 'fixture'):
                with bridge.virtual_directory() as value:
                    directory = value
                    raise ValueError('fixture')
        self.assertEqual(seen, [True])
        self.assertFalse(Path(directory).exists())

    def test_private_viewport_capture_keeps_the_private_display_and_dimensions(self):
        cmd = proton.capture_command(':99', None, 1920, 1080, 30, [Path('/private/one.ts')])
        self.assertNotIn('-window_id', cmd)
        self.assertEqual(cmd[cmd.index('-i') + 1], ':99')
        self.assertEqual(cmd[cmd.index('-video_size') + 1], '1920x1080')

    def test_capture_does_not_inherit_steam_runtime_libraries(self):
        original = {'DISPLAY': ':99', 'XAUTHORITY': '/private/auth', 'LD_LIBRARY_PATH': '/Steam/runtime', 'LD_PRELOAD': '/Steam/overlay.so'}
        env = proton.capture_environment(original)
        self.assertEqual(env['DISPLAY'], ':99')
        self.assertEqual(env['XAUTHORITY'], '/private/auth')
        self.assertNotIn('LD_LIBRARY_PATH', env)
        self.assertNotIn('LD_PRELOAD', env)
        self.assertIn('LD_LIBRARY_PATH', original)

    def test_black_wallpaper_with_visible_error_dialog_never_starts_the_wayland_player(self):
        import io
        project = self.project()
        core.save_config(selection=core.wallpaper_from_path(project).as_dict())
        ready = Mock()
        bridge = Bridge(on_ready=ready)
        server = Mock(); server.poll.return_value = None
        startup = Mock(); startup.poll.return_value = None
        found = {'proton': '/fixture/proton', 'exe': '/fixture/wallpaper64.exe', 'steam': '/fixture/Steam'}
        token = 'a' * 32
        def launch(argv, **kwargs):
            if argv[0] == 'Xvfb':
                os.write(kwargs['pass_fds'][0], b'99\n')
                return server
            return startup
        tree = Mock(returncode=0, stdout='0x123 "NinetalesWallpaper-' + token + '"', stderr='')
        with patch('ninetales_wallpapers.proton.validate', return_value=found), \
             patch.object(core, 'monitors', return_value=[{'name': 'eDP-1', 'width': 1920, 'height': 1080}]), \
             patch.object(bridge, 'seed_prefix'), patch.object(bridge, 'launch', side_effect=launch) as calls, \
             patch.object(bridge, 'control'), patch.object(bridge, 'sleep'), \
             patch.object(bridge, 'inspect_frame', side_effect=[False, True, False, True]), \
             patch('ninetales_wallpapers.proton_bridge.subprocess.run', return_value=tree), \
             patch('ninetales_wallpapers.proton_bridge.secrets.token_hex', return_value=token), \
             patch('sys.stdout', io.StringIO()):
            with self.assertRaisesRegex(ValueError, 'negra'):
                bridge.play()
        ready.assert_not_called()
        self.assertEqual(calls.call_count, 2)  # Xvfb and official startup only.

    def test_distribution_executable_gets_a_complete_private_resource_layout(self):
        root = self.home / 'Steam/wallpaper_engine'
        exe = root / 'distribution/wallpaper64.exe'
        exe.parent.mkdir(parents=True)
        exe.write_bytes(b'genuine-source-fixture')
        (root / 'distribution/bin').mkdir()
        (root / 'assets/shaders/HLSL').mkdir(parents=True)
        (root / 'assets/shaders/HLSL/dx11fallback.vert').write_text('fixture')
        (root / 'config.json').write_text('{"preserved": true}')
        target = self.home / 'private/application'
        found = proton.prepare_application({'exe': str(exe), 'proton': '/proton'}, {'fps': 60}, target)
        self.assertEqual(Path(found['exe']).read_bytes(), exe.read_bytes())
        self.assertFalse(Path(found['exe']).is_symlink())
        self.assertTrue((target / 'assets/shaders/HLSL/dx11fallback.vert').is_file())
        self.assertTrue((target / 'bin').is_symlink())
        cfg = core.read_json(target / 'config.json', {})
        self.assertTrue(cfg['preserved'])
        self.assertEqual(cfg['steamuser']['general']['user']['fps'], 30)
        self.assertEqual((root / 'config.json').read_text(), '{"preserved": true}')

    def test_private_layout_refuses_an_incomplete_steam_download(self):
        exe = self.home / 'Steam/distribution/wallpaper64.exe'
        exe.parent.mkdir(parents=True); exe.touch()
        with self.assertRaisesRegex(ValueError, 'Steam'):
            proton.prepare_application({'exe': str(exe)}, {}, self.home / 'private')
        self.assertFalse((self.home / 'private').exists())

    def test_cleanup_addresses_only_own_prefix(self):
        bridge = Bridge()
        runner = self.home / 'Proton/proton'
        wineserver = runner.parent / 'files/bin/wineserver'
        wineserver.parent.mkdir(parents=True)
        wineserver.touch()
        bridge.found = {'proton': str(runner)}
        bridge.env = {'WINEPREFIX': str(bridge.prefix / 'pfx')}
        child = Mock()
        child.poll.return_value = None
        bridge.children = [child]
        with patch('ninetales_wallpapers.proton_bridge.subprocess.run') as run:
            bridge.cleanup()
        self.assertEqual(run.call_args.args[0], [str(wineserver), '-k'])
        self.assertEqual(run.call_args.kwargs['env']['WINEPREFIX'], str(bridge.prefix / 'pfx'))
        child.send_signal.assert_called_with(signal.SIGCONT)
        child.terminate.assert_called_once()


if __name__ == '__main__':
    unittest.main()
