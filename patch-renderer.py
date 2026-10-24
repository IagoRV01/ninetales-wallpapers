#!/usr/bin/env python3
"""Corregir el tamaño de capas con máscaras pequeñas y recompilar sin sudo."""
from pathlib import Path
import json
import os
import shlex
import shutil
import subprocess
import sys
import time

root = Path.home() / '.local/share/ninetales-wallpapers/linux-wallpaperengine'
build = root / 'build'
source = root / 'src/WallpaperEngine/Render/Objects/CImage.cpp'
state = Path.home() / '.local/state/ninetales-wallpapers'
state.mkdir(parents=True, exist_ok=True)
original = source.read_text()
old = '''glm::vec2 CImage::getSize () const {
    if (this->m_texture == nullptr) {
	return this->getImage ().size;
    }

    return { this->m_texture->getRealWidth (), this->m_texture->getRealHeight () };
}'''
new = '''glm::vec2 CImage::getSize () const {
    // A material's first texture may be a small flow mask, not its geometry.
    const auto& image = this->getImage ();
    const glm::vec2 textureSize = this->m_texture == nullptr
        ? glm::vec2 (0.0f)
        : glm::vec2 (this->m_texture->getRealWidth (), this->m_texture->getRealHeight ());
    return resolveDeclaredImageSize (image.size, image.model->width, image.model->height,
                                     textureSize, image.model->autosize);
}'''
if old in original:
    shutil.copy2(source, state / ('CImage.cpp.before-' + str(time.time_ns())))
    source.write_text(original.replace('#include "CImage.h"', '#include "CImage.h"\n#include "DeclaredImageSize.h"').replace(old, new))
elif 'resolveDeclaredImageSize' not in original:
    raise SystemExit('El motor cambió: revisar CImage::getSize antes de aplicar el parche.')
header = source.with_name('DeclaredImageSize.h')
header.write_text('''#pragma once
#include <optional>
#include <glm/vec2.hpp>
namespace WallpaperEngine::Render::Objects {
inline glm::vec2 resolveDeclaredImageSize(const glm::vec2& explicitSize,
    std::optional<int> modelWidth, std::optional<int> modelHeight,
    const glm::vec2& textureSize, bool autosize) {
    if (explicitSize.x > 0 && explicitSize.y > 0) return explicitSize;
    const bool declared = modelWidth && modelHeight && *modelWidth > 0 && *modelHeight > 0;
    if (declared && !autosize) return {float(*modelWidth), float(*modelHeight)};
    if (textureSize.x > 0 && textureSize.y > 0) return textureSize;
    if (declared) return {float(*modelWidth), float(*modelHeight)};
    return explicitSize;
}
}
''')
# Verificar la resolución de geometría sin necesitar GPU ni la sesión gráfica.
test = state / 'test-image-size.cpp'
test.write_text('''#include <cassert>
#include "DeclaredImageSize.h"
using namespace WallpaperEngine::Render::Objects;
int main() {
    assert(resolveDeclaredImageSize({0,0},1920,1080,{480,270},false) == glm::vec2(1920,1080));
    assert(resolveDeclaredImageSize({800,600},1920,1080,{480,270},false) == glm::vec2(800,600));
    assert(resolveDeclaredImageSize({0,0},{},{},{480,270},false) == glm::vec2(480,270));
    assert(resolveDeclaredImageSize({0,0},1920,1080,{480,270},true) == glm::vec2(480,270));
    assert(resolveDeclaredImageSize({0,0},1920,1080,{0,0},true) == glm::vec2(1920,1080));
    assert(resolveDeclaredImageSize({0,0},0,0,{640,360},false) == glm::vec2(640,360));
}
''')
binary = state / 'test-image-size'
subprocess.run(['g++', '-std=c++20', '-I', str(source.parent), str(test), '-o', str(binary)], check=True)
subprocess.run([str(binary)], check=True)
print('Resolución de geometría: 6 casos correctos.', flush=True)
if '--source-only' in sys.argv[1:]:
    print('Parche de tamaño aplicado al código fuente.', flush=True)
    raise SystemExit(0)
entries = json.loads((build / 'compile_commands.json').read_text())
entry = next(e for e in entries if Path(e['file']).resolve() == source.resolve())
args = entry.get('arguments') or shlex.split(entry['command'])
subprocess.run(args, cwd=entry['directory'], check=True)
link = shlex.split((build / 'CMakeFiles/linux-wallpaperengine-lib.dir/link.txt').read_text())
output = build / 'output/liblinux-wallpaperengine-lib.so'
staged = output.with_name('.liblinux-wallpaperengine-lib.fixed.so')
link[link.index('-o') + 1] = str(staged)
subprocess.run(link, cwd=build, check=True)
# Sustituir el inodo, sin truncar la biblioteca que está usando el fondo actual.
backup = state / 'liblinux-wallpaperengine-lib.before-size-fix.so'
if not backup.exists():
    shutil.copy2(output, backup)
os.replace(staged, output)
(state / 'renderer-size-fix.json').write_text(json.dumps({'installed': True, 'source': str(source), 'backup': str(backup)}))
print('Motor corregido. Se cargará al volver a aplicar el fondo.', flush=True)
