import configparser
import hashlib
import importlib.util
import io
import json
import contextlib
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from ninetales_wallpapers import core, login
from test_wallpapers import Environment


class LoginTests(Environment):
    def setUp(self):
        super().setUp()
        try:
            import gi
            gi.require_version('GdkPixbuf', '2.0')
            from gi.repository import GdkPixbuf
        except ImportError:
            self.skipTest('Optional GdkPixbuf dependency unavailable')
        self.avatar = self.home / 'photo.png'
        self.background = self.home / 'wallpaper.png'
        image = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 32, 32)
        image.fill(0x7060AAFF)
        for path in (self.avatar, self.background):
            image.savev(str(path), 'png', [], [])

    def test_self_contained_image_and_avatar_with_complete_integrity_manifest(self):
        before = core.load_config()
        bundle = login.prepare(str(self.background), str(self.avatar))
        theme = bundle / 'theme'
        conf = configparser.ConfigParser(); conf.read(theme / 'theme.conf')
        self.assertEqual(conf['General']['AnimationKind'], 'image')
        self.assertEqual((theme / conf['General']['Background']).read_bytes(), self.background.read_bytes())
        self.assertTrue((theme / conf['General']['Avatar']).is_file())
        manifest = json.loads((bundle / 'manifest.json').read_text())
        for name, expected in manifest['files'].items():
            self.assertEqual(hashlib.sha256((theme / name).read_bytes()).hexdigest(), expected)
        self.assertFalse(manifest['video'])
        self.assertEqual(core.load_config(), before)
        self.assertNotIn(str(self.home), (theme / 'theme.conf').read_text())

    def test_scene_exports_its_preview_without_executing_renderer(self):
        project = self.project(preview='preview.png')
        (project / 'preview.png').write_bytes(self.background.read_bytes())
        with patch.object(login.subprocess, 'run') as run:
            bundle = login.prepare(str(project), str(self.avatar))
        run.assert_not_called()
        conf = configparser.ConfigParser();conf.read(bundle / 'theme/theme.conf')
        self.assertEqual(conf['General']['AnimationKind'], 'image')

    def test_video_exports_media_and_a_silent_poster_fallback(self):
        video = self.home / 'clip.mp4';video.write_bytes(b'video-fixture')
        def poster(argv, **kwargs):
            Path(argv[-1]).write_bytes(self.background.read_bytes())
            return __import__('subprocess').CompletedProcess(argv, 0)
        with patch.object(login.shutil, 'which', return_value='/usr/bin/ffmpeg'), patch.object(login.subprocess, 'run', side_effect=poster):
            bundle = login.prepare(str(video), str(self.avatar))
        conf = configparser.ConfigParser();conf.read(bundle / 'theme/theme.conf')
        self.assertEqual(conf['General']['AnimationKind'], 'video')
        self.assertEqual((bundle / 'theme' / conf['General']['Animation']).read_bytes(), b'video-fixture')
        self.assertTrue(json.loads((bundle / 'manifest.json').read_text())['video'])

    def test_missing_avatar_or_selection_is_reported_before_installing(self):
        with self.assertRaises(ValueError):
            login.prepare()
        with self.assertRaises(ValueError):
            login.prepare(str(self.background), str(self.home / 'missing.png'))

    def test_scene_without_preview_leaves_no_partial_bundle(self):
        with self.assertRaises(ValueError):
            login.prepare(str(self.project()), str(self.avatar))
        self.assertEqual(list((self.home / '.local/share/ninetales-wallpapers/login-bundles').iterdir()), [])

    def test_installer_backs_up_existing_theme_and_never_restarts_sddm(self):
        bundle = login.prepare(str(self.background), str(self.avatar))
        spec = importlib.util.spec_from_file_location('login_installer_fixture', bundle / 'install.py')
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        system = self.home / 'fake-system'
        def mapped(value):
            value = str(value)
            return system / value.lstrip('/') if value.startswith(('/etc/', '/usr/', '/var/')) else Path(value)
        manager = mapped('/etc/X11/default-display-manager')
        manager.parent.mkdir(parents=True)
        manager.write_text('/usr/bin/sddm\n')
        target = mapped('/usr/share/sddm/themes/ninetales-glass')
        target.mkdir(parents=True)
        (target / 'previous').write_text('keep the old theme')
        snippet = mapped('/etc/sddm.conf.d/99-ninetales-theme.conf')
        snippet.parent.mkdir(parents=True)
        snippet.write_text('[Theme]\nCurrent=previous\n')
        backup_root = mapped('/var/backups')
        backup_root.mkdir(parents=True)
        original_mkdtemp = tempfile.mkdtemp
        def mkdtemp(*args, **kwargs):
            if str(kwargs.get('dir', '')).startswith('/var/'):
                kwargs['dir'] = mapped(kwargs['dir'])
            return original_mkdtemp(*args, **kwargs)
        with patch.object(installer, 'Path', mapped), patch.object(installer.os, 'geteuid', return_value=0), \
             patch.object(installer.tempfile, 'mkdtemp', side_effect=mkdtemp), \
             patch.object(installer.subprocess, 'run') as run, contextlib.redirect_stdout(io.StringIO()):
            installer.main()
        self.assertTrue((target / 'Main.qml').is_file())
        self.assertEqual(snippet.read_text(), '[Theme]\nCurrent=ninetales-glass\n')
        backup = next(backup_root.iterdir())
        self.assertEqual((backup / 'theme/previous').read_text(), 'keep the old theme')
        self.assertIn('Current=previous', (backup / 'theme.conf').read_text())
        self.assertTrue((backup / 'rollback.sh').is_file())
        self.assertEqual(len(run.call_args_list), 1)
        self.assertEqual(run.call_args.args[0][:3], ['apt-get', '--no-remove', 'install'])
        self.assertEqual((target / 'assets/avatar.png').stat().st_mode & 0o777, 0o644)


if __name__ == '__main__':
    unittest.main()
