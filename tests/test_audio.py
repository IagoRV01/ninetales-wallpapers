import json
import subprocess
import unittest
from unittest.mock import patch

from ninetales_wallpapers import audio


def stream(index, app='browser', muted=False, corked=False, volume=65536, role='music', pid='100'):
    return dict(index=index, client=index, mute=muted, corked=corked,
                properties={'application.id': app, 'application.process.id': pid, 'media.role': role},
                volume={'front-left': {'value': volume}})


class AudioTests(unittest.TestCase):
    def setUp(self):
        self.monitor = audio.WallpaperAudio()
        self.streams = [stream(5, audio.APP_ID), stream(9)]
        self.commands = []
        self.runner = patch.object(audio.subprocess, 'run', side_effect=self.command)
        self.runner.start()
        self.clock = patch.object(audio.time, 'monotonic', return_value=10)
        self.now = self.clock.start()

    def tearDown(self):
        self.clock.stop()
        self.runner.stop()

    def command(self, argv, **kwargs):
        if argv[:3] == ['pactl', '--format=json', 'list']:
            return subprocess.CompletedProcess(argv, 0, json.dumps(self.streams), '')
        self.commands.append(argv)
        index = int(argv[2])
        next(s for s in self.streams if s['index'] == index)['mute'] = argv[3] == '1'
        return subprocess.CompletedProcess(argv, 0, '', '')

    def poll(self, **settings):
        with patch.object(audio, 'descendant', return_value=False):
            self.monitor.poll({'muted': False, 'auto_mute': True, **settings}, {123})

    def test_music_mutes_only_wallpaper_and_pause_restores_without_restarting(self):
        self.poll()
        self.assertEqual(self.commands, [['pactl', 'set-sink-input-mute', '5', '1']])
        self.assertTrue(self.monitor.auto_muted)
        self.streams[1]['corked'] = True
        self.now.return_value = 10.5
        self.poll()
        self.assertEqual(len(self.commands), 1)
        self.now.return_value = 12
        self.poll()
        self.assertEqual(self.commands[-1], ['pactl', 'set-sink-input-mute', '5', '0'])
        self.assertFalse(self.monitor.auto_muted)

    def test_own_audio_does_not_trigger_a_feedback_loop(self):
        self.streams.pop()
        self.poll()
        self.assertFalse(self.monitor.auto_muted)
        self.assertEqual(self.commands, [])

    def test_paused_muted_zero_volume_and_notifications_do_not_duck(self):
        for external in (stream(9, corked=True), stream(9, muted=True), stream(9, volume=0), stream(9, role='event')):
            self.streams[1] = external
            self.poll()
        self.assertEqual(self.commands, [])

    def test_user_mute_is_preserved_and_setting_can_be_disabled(self):
        self.streams[0]['mute'] = True
        self.poll()
        self.streams.pop()
        self.now.return_value = 12
        self.poll()
        self.assertEqual(self.commands, [])
        self.streams[0]['mute'] = False
        self.streams.append(stream(9))
        self.poll()
        self.poll(auto_mute=False)
        self.assertEqual([c[-1] for c in self.commands], ['1', '0'])

    def test_manual_mute_wins_even_after_music_stops(self):
        self.poll()
        self.streams.pop()
        self.now.return_value = 12
        self.poll(muted=True)
        self.assertTrue(self.streams[0]['mute'])
        self.assertEqual(len(self.commands), 1)

    def test_recycled_stream_index_is_not_unmuted(self):
        self.poll()
        self.streams = [stream(5, audio.APP_ID, muted=True, pid='200')]
        self.now.return_value = 12
        self.poll()
        self.assertEqual(len(self.commands), 1)

    def test_audio_server_failure_does_not_crash_supervisor(self):
        with patch.object(audio.subprocess, 'run', side_effect=OSError('Unavailable')):
            self.monitor.poll({'muted': False}, {123})
        self.assertTrue(self.monitor.status()['audio_error'])

    def test_failed_mute_is_reported_and_not_later_unmuted_as_if_successful(self):
        original = self.command
        def fail_write(argv, **kwargs):
            if argv[1] == 'set-sink-input-mute':
                return subprocess.CompletedProcess(argv, 1, '', 'Operation failed')
            return original(argv, **kwargs)
        with patch.object(audio.subprocess, 'run', side_effect=fail_write):
            self.poll()
        self.assertTrue(self.monitor.error)
        self.assertEqual(self.monitor.changed, {})

    def test_proton_environment_is_tagged_without_muting_all_steam(self):
        env = audio.renderer_environment({'PULSE_PROP': 'media.role=music'})
        self.assertIn('application.id=' + audio.APP_ID, env['PULSE_PROP'])
        self.assertIn(audio.APP_ID, env['PIPEWIRE_PROPS'])
        self.assertFalse(audio.owned(stream(9, 'com.valvesoftware.Steam'), set()))


if __name__ == '__main__':
    unittest.main()
