#!/usr/bin/env python3
"""Publish a source prerelease and point the previous release at its replacement."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def gh(*args):
    return subprocess.check_output(['gh', *args], text=True, cwd=ROOT)


def publish(repo, tag):
    # Read existing metadata first; network/authentication failures must stop
    # publication instead of being mistaken for an empty release history.
    releases = json.loads(gh('release', 'list', '--repo', repo, '--limit', '100',
                             '--json', 'tagName,isDraft,publishedAt'))
    previous = sorted((r for r in releases if r['tagName'] != tag and not r['isDraft']),
                      key=lambda r: r.get('publishedAt') or '', reverse=True)
    existing = next((r for r in releases if r['tagName'] == tag), None)
    notes = ROOT / 'docs/release-notes.md'
    version = tag.removeprefix('v')
    assets = [ROOT / 'dist' / ('ninetales-wallpapers-' + version + suffix) for suffix in ('.tar.gz', '.zip')]
    assets.append(ROOT / 'dist/SHA256SUMS')
    if any(not p.is_file() for p in assets):
        raise ValueError('Build the versioned source archives before publishing.')
    if existing:
        gh('release', 'edit', tag, '--repo', repo, '--draft=false', '--prerelease',
           '--title', 'Ninetales Wallpapers ' + tag, '--notes-file', str(notes))
        gh('release', 'upload', tag, '--repo', repo, '--clobber', *map(str, assets))
    else:
        gh('release', 'create', tag, '--repo', repo, '--verify-tag', '--prerelease',
           '--title', 'Ninetales Wallpapers ' + tag, '--notes-file', str(notes), *map(str, assets))
    url = 'https://github.com/' + repo + '/releases/tag/' + tag
    if previous:
        old = previous[0]['tagName']
        body = json.loads(gh('release', 'view', old, '--repo', repo, '--json', 'body'))['body'] or ''
        start = '<!-- ninetales-superseded:start -->'
        end = '<!-- ninetales-superseded:end -->'
        if start in body and end in body:
            begin = body.index(start)
            finish = body.index(end, begin) + len(end)
            body = (body[:begin] + body[finish:]).strip()
        notice = f'{start}\n> Replaced by [{tag}]({url}). Use the newer prerelease for automatic audio muting and the personal SDDM login screen.\n{end}\n\n'
        with tempfile.TemporaryDirectory(prefix='nw-release-notes-') as temporary:
            file = Path(temporary) / 'previous.md'
            file.write_text(notice + body)
            gh('release', 'edit', old, '--repo', repo, '--notes-file', str(file))
    print(url)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('tag')
    parser.add_argument('--repo', default='IagoRV01/ninetales-wallpapers')
    args = parser.parse_args()
    publish(args.repo, args.tag)
