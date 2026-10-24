#!/usr/bin/env python3
"""Build source-only archives from an explicit allowlist, without local user data."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ninetales_wallpapers import __version__

TOP = ('README.md', 'LICENSE', 'CHANGELOG.md', 'CONTRIBUTING.md',
       'THIRD_PARTY_NOTICES.md', '.gitignore', 'install.py', 'uninstall.py',
       'install-renderer.sh', 'patch-renderer.py')
DIRECTORIES = ('ninetales_wallpapers', 'player', 'tests', 'docs', 'scripts', '.github')


def source_files():
    files = [ROOT / name for name in TOP]
    for directory in DIRECTORIES:
        files.extend(p for p in (ROOT / directory).rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts and
                     (p.suffix in ('.py', '.qml', '.md', '.sh', '.yml', '.yaml') or
                      (p.parent == ROOT / 'ninetales_wallpapers/locales' and p.name in ('es.json', 'en.json', 'fr.json', 'pt.json'))))
    for path in files:
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            raise ValueError('Refusing to package a linked or external source file: ' + str(path))
        if not path.is_file():
            raise ValueError('Missing source file: ' + str(path))
    return sorted(set(files))


def build():
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    name = 'ninetales-wallpapers-' + __version__
    files = source_files()
    archive = dist / (name + '.tar.gz')
    with tarfile.open(archive, 'w:gz') as tar:
        for path in files:
            info = tar.gettarinfo(str(path), str(Path(name) / path.relative_to(ROOT)))
            info.uid = info.gid = 0
            info.uname = info.gname = ''
            with path.open('rb') as stream:
                tar.addfile(info, stream)
    zipped = dist / (name + '.zip')
    with zipfile.ZipFile(zipped, 'w', compression=zipfile.ZIP_DEFLATED) as out:
        for path in files:
            out.write(path, str(Path(name) / path.relative_to(ROOT)))
    sums = dist / 'SHA256SUMS'
    sums.write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name + '\n'
                            for p in (archive, zipped)))
    print(f'Packaged {len(files)} source files:')
    for path in (archive, zipped, sums):
        print(path)


if __name__ == '__main__':
    build()
