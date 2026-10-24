#!/usr/bin/env bash
# Install the distribution's GitHub CLI in the user account, then authenticate.
set -Eeuo pipefail
export PATH="$HOME/.local/bin:$PATH"
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if ! command -v gh >/dev/null; then
 command -v apt-get >/dev/null
 command -v dpkg-deb >/dev/null
 download_dir=$(mktemp -d)
 trap 'rm -rf -- "$download_dir"' EXIT
 (
  cd -- "$download_dir"
  apt-get download gh
 )
 mapfile -t packages < <(find "$download_dir" -maxdepth 1 -type f -name 'gh_*.deb')
 (( ${#packages[@]} == 1 ))
 gh_root="$HOME/.local/share/ninetales-wallpapers/github-cli"
 mkdir -p "$gh_root" "$HOME/.local/bin"
 dpkg-deb --extract "${packages[0]}" "$gh_root"
 test -x "$gh_root/usr/bin/gh"
 if [[ -e "$HOME/.local/bin/gh" || -L "$HOME/.local/bin/gh" ]]; then
  echo 'A local gh launcher already exists; review it before continuing.' >&2
  exit 1
 fi
 ln -s "$gh_root/usr/bin/gh" "$HOME/.local/bin/gh"
 rm -rf -- "$download_dir"
 trap - EXIT
fi
gh --version
if ! gh auth status --hostname github.com >/dev/null 2>&1; then
 gh auth login --hostname github.com --git-protocol https --web --scopes repo,workflow
fi
gh auth setup-git --hostname github.com
if [[ ${1:-} == --publish ]]; then
 exec bash "$project_dir/scripts/publish.sh"
fi
echo 'GitHub authentication is ready. Run bash scripts/publish.sh to publish.'
