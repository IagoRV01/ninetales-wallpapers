#!/usr/bin/env bash
set -Eeuo pipefail
export PATH="$HOME/.local/bin:$PATH"
state="$HOME/.local/state/ninetales-wallpapers"
source_dir="$HOME/.local/share/ninetales-wallpapers/linux-wallpaperengine"
mkdir -p "$state" "$(dirname "$source_dir")"
log="$state/instalar-motor-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$log") 2>&1
trap 'printf "\nLa instalación se ha detenido en la línea %s. Registro: %s\n" "$LINENO" "$log"' ERR
(( EUID != 0 )) || { echo 'Ejecuta este script como iago; sudo pedirá la contraseña cuando haga falta.'; exit 1; }
jobs=${NW_BUILD_JOBS:-2}
[[ $jobs =~ ^[1-9][0-9]*$ ]]
packages=(build-essential cmake git pkg-config libxrandr-dev libxinerama-dev
 libxcursor-dev libxi-dev libgl-dev libglew-dev freeglut3-dev libsdl2-dev
 liblz4-dev libavcodec-dev libavformat-dev libavutil-dev libswscale-dev
 libxxf86vm-dev libglm-dev libglfw3-dev libmpv-dev mpv libmpv2 libpulse-dev
 libfftw3-dev libfreetype-dev libwayland-dev wayland-protocols libegl-dev
 libdbus-1-dev libxkbcommon-dev libgmp-dev libswresample-dev libavfilter-dev
 libavdevice-dev libxss-dev libasound2-dev libgbm-dev libnss3-dev
 libatk-bridge2.0-dev libxcomposite-dev libxdamage-dev libjack-jackd2-dev)
echo 'Instalando el reproductor nativo de Almamu/linux-wallpaperengine para Wayland.'
echo 'No se descarga Wallpaper Engine ni sus fondos: Steam debe proporcionar esos archivos.'
sudo -v
sudo apt-get update
apt-get --simulate --no-remove --no-install-recommends install "${packages[@]}"
sudo apt-get --yes --no-remove --no-install-recommends install "${packages[@]}"
if [[ ! -d "$source_dir/.git" ]]; then
 git clone --recurse-submodules https://github.com/Almamu/linux-wallpaperengine.git "$source_dir"
else
 git -C "$source_dir" submodule update --init --recursive
fi
git -C "$source_dir" rev-parse HEAD > "$state/revision-motor.txt"
python3 "$(dirname -- "${BASH_SOURCE[0]}")/patch-renderer.py" --source-only
cmake -S "$source_dir" -B "$source_dir/build" -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF
cmake --build "$source_dir/build" --parallel "$jobs"
test -x "$source_dir/build/output/linux-wallpaperengine"
mkdir -p "$HOME/.local/bin"
python3 - "$HOME/.local/bin/linux-wallpaperengine" "$source_dir/build/output" <<'PY'
from pathlib import Path
import os, shlex, sys
p=Path(sys.argv[1]); binary=Path(sys.argv[2])/'linux-wallpaperengine'
temporary=p.with_name('.linux-wallpaperengine-wrapper')
temporary.write_text('#!/usr/bin/env bash\ncd -- '+shlex.quote(str(binary.parent))+'\nexec '+shlex.quote(str(binary))+' "$@"\n')
temporary.chmod(0o755)
os.replace(temporary,p)
PY
echo 'Motor instalado. En Ninetales Wallpapers, pulsa Actualizar y selecciona un fondo.'
echo "Registro: $log"
