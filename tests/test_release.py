import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).resolve().parent.parent / 'scripts/github-release.py'
        spec = importlib.util.spec_from_file_location('github_release_fixture', source)
        self.publisher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.publisher)
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / 'dist').mkdir()
        (self.root / 'docs').mkdir()
        (self.root / 'docs/release-notes.md').write_text('Current release notes')
        for name in ('ninetales-wallpapers-0.6.0a1.tar.gz', 'ninetales-wallpapers-0.6.0a1.zip', 'SHA256SUMS'):
            (self.root / 'dist' / name).write_text('fixture')
        # An old archive must not be attached to the new release.
        (self.root / 'dist/ninetales-wallpapers-0.5.0a1.zip').write_text('old fixture')
        self.releases = [{'tagName': 'v0.5.3a1', 'isDraft': False, 'publishedAt': '2026-10-24T00:00:00Z'}]
        self.body = 'Original notes with useful history.'
        self.commands = []
        self.previous_notes = ''

    def tearDown(self):
        self.temporary.cleanup()

    def gh(self, *args):
        self.commands.append(args)
        if args[:2] == ('release', 'list'):
            return json.dumps(self.releases)
        if args[:2] == ('release', 'view'):
            return json.dumps({'body': self.body})
        if args[:3] == ('release', 'edit', 'v0.5.3a1'):
            self.previous_notes = Path(args[args.index('--notes-file') + 1]).read_text()
        return ''

    def publish(self):
        with patch.object(self.publisher, 'ROOT', self.root), patch.object(self.publisher, 'gh', side_effect=self.gh), contextlib.redirect_stdout(io.StringIO()):
            self.publisher.publish('IagoRV01/ninetales-wallpapers', 'v0.6.0a1')

    def test_new_release_uses_only_current_archives_then_updates_previous_notes(self):
        self.publish()
        create = next(c for c in self.commands if c[:2] == ('release', 'create'))
        self.assertIn('--verify-tag', create)
        self.assertIn('--prerelease', create)
        self.assertNotIn(str(self.root / 'dist/ninetales-wallpapers-0.5.0a1.zip'), create)
        self.assertIn('/releases/tag/v0.6.0a1', self.previous_notes)
        self.assertIn(self.body, self.previous_notes)
        self.assertFalse(any('delete' in command for command in self.commands))

    def test_existing_release_is_updated_and_assets_replaced_without_creating_duplicate(self):
        self.releases.append({'tagName': 'v0.6.0a1', 'isDraft': True, 'publishedAt': None})
        self.publish()
        self.assertFalse(any(c[:2] == ('release', 'create') for c in self.commands))
        upload = next(c for c in self.commands if c[:2] == ('release', 'upload'))
        self.assertIn('--clobber', upload)

    def test_previous_notice_is_replaced_once_while_history_is_preserved(self):
        self.body = '<!-- ninetales-superseded:start -->old notice<!-- ninetales-superseded:end -->\n\nHistory'
        self.publish()
        self.assertEqual(self.previous_notes.count('ninetales-superseded:start'), 1)
        self.assertNotIn('old notice', self.previous_notes)
        self.assertIn('History', self.previous_notes)

    def test_network_or_auth_failure_stops_before_any_release_mutation(self):
        with patch.object(self.publisher, 'ROOT', self.root), patch.object(self.publisher, 'gh', side_effect=subprocess.CalledProcessError(1, ['gh'])) as call:
            with self.assertRaises(subprocess.CalledProcessError):
                self.publisher.publish('IagoRV01/ninetales-wallpapers', 'v0.6.0a1')
        self.assertEqual(call.call_count, 1)


if __name__ == '__main__':
    unittest.main()
