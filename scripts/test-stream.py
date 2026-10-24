#!/usr/bin/env python3
"""Optional integration check: real FFmpeg tee/FIFOs -> two Qt video decoders.

Requires installed Quickshell, compatible Qt Multimedia and ffmpeg; no display,
Steam, Wallpaper Engine or proprietary fixtures are used.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ninetales_wallpapers import core, proton


def main():
    with tempfile.TemporaryDirectory(prefix='nw-stream-check-') as temporary:
        temp = Path(temporary)
        runtime = temp / 'runtime'
        runtime.mkdir(mode=0o700)
        fifos = [temp / f'output-{i}.ts' for i in range(2)]
        for fifo in fifos:
            os.mkfifo(fifo, 0o600)
        shutil.copy2(ROOT / 'player/MediaWallpaper.qml', temp / 'MediaWallpaper.qml')
        items = '\n'.join('MediaWallpaper { anchors.fill:parent; kind:"video"; mediaUri:"' +
                          fifo.as_uri() + '"; onReady: root.frame(); onFailed: message => root.failed(message) }'
                          for fifo in fifos)
        (temp / 'shell.qml').write_text('''import QtQuick
import Quickshell
import "."
ShellRoot {
 id: root
 property int received: 0
 function frame() { received++; if (received === 2) { console.log("NW_STREAM_TEST_OK"); Qt.quit(); } }
 function failed(message) { console.error("NW_STREAM_TEST_ERROR:" + message); Qt.quit(); }
 Item { width:96; height:64
''' + items + '''
 }
 Timer { interval:20000; running:true; onTriggered:Qt.quit() }
}
''')
        env = core.qt_environment()
        env.pop('WAYLAND_DISPLAY', None)
        env.update(QT_QPA_PLATFORM='offscreen', QSG_RHI_BACKEND='software', XDG_RUNTIME_DIR=str(runtime))
        capture = proton.capture_command(':unused', '0x123', 96, 64, 15, fifos)
        # Keep the actual bridge's encoder/tee plan and substitute synthetic input.
        capture = capture[:capture.index('-f')] + ['-re', '-f', 'lavfi', '-i', 'testsrc2=size=96x64:rate=15'] + capture[capture.index('-an'):]
        producer = subprocess.Popen(capture, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            player = subprocess.run([core.quickshell_path(), '--no-color', '-p', str(temp / 'shell.qml')],
                                    env=env, capture_output=True, text=True, timeout=25)
            output = player.stdout + player.stderr
            if 'NW_STREAM_TEST_OK' not in output:
                print(output, file=sys.stderr)
                return 1
            print('PASS: both output streams produced a decoded Qt video frame.')
        finally:
            if producer.poll() is None:
                producer.kill()
            producer.wait(timeout=3)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
