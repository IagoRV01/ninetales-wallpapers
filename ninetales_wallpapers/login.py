"""Export media and a personal avatar into a self-contained SDDM theme bundle."""
from __future__ import annotations

import configparser
import hashlib
import json
import math
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import tempfile

from . import core


def prepare(path=None, avatar=None):
    config = core.load_config()
    path = path or config.get('login_wallpaper') or (config.get('selection') or {}).get('path')
    if not path:
        raise ValueError('Selecciona primero un fondo para el inicio de sesión.')
    wall = core.wallpaper_from_path(Path(path))
    avatar = Path(avatar or config.get('login_avatar') or core.HOME / '.face').expanduser().resolve()
    if not avatar.is_file():
        raise ValueError('Elige una foto de perfil para el inicio de sesión.')
    import gi
    gi.require_version('GdkPixbuf', '2.0')
    from gi.repository import GdkPixbuf, GLib
    # Validate/decode locally; export a standard PNG instead of an arbitrary file.
    photo = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(avatar), 512, 512, True)
    destination = core.HOME / '.local/share/ninetales-wallpapers/login-bundles'
    destination.mkdir(parents=True, exist_ok=True)
    bundle = Path(tempfile.mkdtemp(prefix='ninetales-', dir=destination))
    try:
        theme = bundle / 'theme'
        shutil.copytree(core.PROJECT / 'integrations/sddm/theme', theme)
        assets = theme / 'assets'
        assets.mkdir()
        side = min(photo.get_width(), photo.get_height())
        photo = photo.new_subpixbuf((photo.get_width() - side) // 2, (photo.get_height() - side) // 2, side, side)
        photo = photo.scale_simple(256, 256, GdkPixbuf.InterpType.BILINEAR).add_alpha(False, 0, 0, 0)
        pixels = bytearray(photo.get_pixels())
        stride = photo.get_rowstride()
        for y in range(256):
            for x in range(256):
                coverage = max(0, min(1, 128 - math.hypot(x - 127.5, y - 127.5)))
                offset = y * stride + x * 4 + 3
                pixels[offset] = round(pixels[offset] * coverage)
        # A transparent PNG works with hardware and software Qt rendering alike.
        photo = GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(bytes(pixels)), GdkPixbuf.Colorspace.RGB, True, 8, 256, 256, stride)
        photo.savev(str(assets / 'avatar.png'), 'png', [], [])
        kind = wall.kind
        source = Path(wall.media if kind in ('image', 'gif', 'video') else wall.preview)
        if not source.is_file():
            raise ValueError('Este fondo no incluye una imagen de vista previa para el inicio de sesión.')
        if source.stat().st_size > 512 * 1024 * 1024:
            raise ValueError('El fondo de inicio de sesión no puede superar 512 MiB.')
        suffix = source.suffix.lower()
        background = 'assets/background' + suffix
        animation = ''
        if kind == 'video':
            if not shutil.which('ffmpeg'):
                raise ValueError('Se necesita ffmpeg para preparar la vista previa del vídeo.')
            animation = 'assets/background' + suffix
            shutil.copyfile(source, theme / animation)
            background = 'assets/poster.jpg'
            result = subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                                     '-i', str(source), '-frames:v', '1', '-vf', 'scale=1920:-2',
                                     '-threads', '1', '-update', '1', str(theme / background)],
                                    capture_output=True, timeout=45)
            if result.returncode:
                raise ValueError('No se pudo generar una vista previa del vídeo.')
        else:
            shutil.copyfile(source, theme / background)
            if kind == 'gif':
                animation = background
        account = pwd.getpwuid(os.getuid())
        settings = configparser.ConfigParser(interpolation=None)
        settings.optionxform = str
        settings['General'] = dict(Background=background, Animation=animation,
                                  AnimationKind=kind if kind in ('gif', 'video') else 'image',
                                  Avatar='assets/avatar.png', CustomUser=account.pw_name,
                                  DisplayName=account.pw_gecos.split(',')[0] or account.pw_name)
        with (theme / 'theme.conf').open('w') as output:
            settings.write(output)
        shutil.copyfile(core.PROJECT / 'integrations/sddm/install.py', bundle / 'install.py')
        (bundle / 'install.sh').write_text('#!/bin/sh\nset -eu\ncd -- "$(dirname -- "$0")"\nexec /usr/bin/python3 ./install.py\n')
        files = {str(file.relative_to(theme)): hashlib.sha256(file.read_bytes()).hexdigest()
                 for file in theme.rglob('*') if file.is_file()}
        (bundle / 'manifest.json').write_text(json.dumps({'files': files, 'video': kind == 'video'}, indent=2) + '\n')
        return bundle
    except Exception:
        shutil.rmtree(bundle)
        raise
