import os
from pathlib import Path
import tempfile
import unittest

from ninetales_wallpapers import desktop


class DesktopEnvironmentTests(unittest.TestCase):
    def test_stale_display_replaced_only_with_a_verified_session_server(self):
        original = {'DISPLAY': ':1', 'WAYLAND_DISPLAY': 'wayland-1', 'XAUTHORITY': '/stale',
                    'QT_PLUGIN_PATH': '/private/qt/plugins'}
        servers = [{'display': ':2', 'authority': '/current-auth'}]
        env = desktop.desktop_environment(original, servers, lambda e: e['DISPLAY'] == ':2' and e.get('XAUTHORITY') == '/current-auth')
        self.assertEqual(env['DISPLAY'], ':2')
        self.assertEqual(env['XAUTHORITY'], '/current-auth')
        self.assertNotIn('QT_PLUGIN_PATH', env)
        self.assertEqual(original['DISPLAY'], ':1')

    def test_missing_display_uses_verified_server(self):
        env = desktop.desktop_environment({'WAYLAND_DISPLAY': 'wayland-0'},
                    [{'display': ':9', 'authority': None}], lambda e: e['DISPLAY'] == ':9')
        self.assertEqual(env['DISPLAY'], ':9')

    def test_server_without_auth_flag_can_drop_a_stale_authority(self):
        env = desktop.desktop_environment({'DISPLAY': ':1', 'WAYLAND_DISPLAY': 'wayland-1', 'XAUTHORITY': '/stale'},
                    [{'display': ':2', 'authority': None}], lambda e: e['DISPLAY'] == ':2' and 'XAUTHORITY' not in e)
        self.assertEqual(env['DISPLAY'], ':2')
        self.assertNotIn('XAUTHORITY', env)

    def test_restricted_probe_never_changes_authentication_or_guesses_a_display(self):
        original = {'DISPLAY': ':1', 'WAYLAND_DISPLAY': 'wayland-1', 'XAUTHORITY': '/original'}
        env = desktop.desktop_environment(original, [{'display': ':0', 'authority': '/other'}], lambda _: False)
        self.assertEqual(env, original)

    def test_xorg_session_is_preserved(self):
        original = {'DISPLAY': ':4', 'XAUTHORITY': '/xorg/auth'}
        self.assertEqual(desktop.desktop_environment(original, [], lambda _: False), original)

    def test_parent_compositor_identifies_server_even_without_exported_wayland_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            session = root / 'runtime/hypr/current'
            session.mkdir(parents=True)
            (session / 'hyprland.lock').write_text('1234\nwayland-1\n')
            proc_root = root / 'proc'
            process = proc_root / '5678'
            process.mkdir(parents=True)
            (process / 'comm').write_text('Xwayland')
            (process / 'cmdline').write_bytes(b'Xwayland\0:5\0-rootless')
            (process / 'environ').write_bytes(b'')
            (process / 'status').write_text('PPid:\t1234\n')
            found = desktop.xwayland_servers({'XDG_RUNTIME_DIR': str(root / 'runtime'),
                                              'HYPRLAND_INSTANCE_SIGNATURE': 'current'}, proc_root)
            self.assertEqual([s['display'] for s in found], [':5'])

    def test_other_users_servers_are_never_selected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            process = root / '123'
            process.mkdir()
            (process / 'comm').write_text('Xwayland')
            (process / 'cmdline').write_bytes(b'Xwayland\0:3')
            (process / 'environ').write_bytes(b'WAYLAND_DISPLAY=wayland-1')
            (process / 'status').write_text('PPid:\t0\n')
            self.assertEqual(desktop.xwayland_servers({'WAYLAND_DISPLAY': 'wayland-1'}, root, os.getuid() + 1), [])

    def test_xwayland_discovery_ignores_other_sessions_and_xvfb(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for pid, comm, argv, wayland in [('1', 'Xwayland', ['Xwayland', ':3', '-auth', '/auth'], 'wayland-1'),
                                           ('2', 'Xwayland', ['Xwayland', ':7'], 'wayland-7'),
                                           ('3', 'Xvfb', ['Xvfb', ':99'], 'wayland-1')]:
                proc = root / pid
                proc.mkdir()
                (proc / 'comm').write_text(comm)
                (proc / 'cmdline').write_bytes(b'\0'.join(a.encode() for a in argv))
                (proc / 'environ').write_bytes(b'WAYLAND_DISPLAY=' + wayland.encode())
                (proc / 'status').write_text('PPid:\t0\n')
            found = desktop.xwayland_servers({'WAYLAND_DISPLAY': 'wayland-1'}, root)
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0]['display'], ':3')
            self.assertEqual(found[0]['authority'], '/auth')


if __name__ == '__main__':
    unittest.main()
