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
        self.assertEqual(cmd[:3], [found['proton'], 'run', found['exe']])
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
