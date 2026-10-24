#!/usr/bin/env bash
# Publish the prepared project using the user's authenticated GitHub CLI.
set -Eeuo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
command -v gh >/dev/null || { echo 'Install GitHub CLI (gh), then run gh auth login.' >&2; exit 1; }
gh auth status >/dev/null
owner=$(gh api user --jq .login)
account_id=$(gh api user --jq .id)
[[ $owner =~ ^[A-Za-z0-9-]+$ && $account_id =~ ^[0-9]+$ ]]
repo="$owner/ninetales-wallpapers"
version=$(python3 -c 'from ninetales_wallpapers import __version__; print(__version__)')
python3 -m unittest discover -s tests
python3 scripts/build-release.py
if [[ ! -d .git ]]; then
 git init --initial-branch=main
fi
# Never add local logs, caches, release archives, Steam files or machine plans.
mapfile -t sources < <(python3 - <<'PY'
import importlib.util
from pathlib import Path
p = Path('scripts/build-release.py').resolve()
spec = importlib.util.spec_from_file_location('release_builder', p)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
for path in module.source_files():
    print(path.relative_to(module.ROOT))
PY
)
git add -- "${sources[@]}"
python3 - <<'PYINDEX'
import importlib.util
from pathlib import Path
import subprocess
spec = importlib.util.spec_from_file_location('release_builder', 'scripts/build-release.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
allowed = {str(p.relative_to(module.ROOT)) for p in module.source_files()}
tracked = set(subprocess.check_output(['git', 'ls-files', '-z']).decode().rstrip('\0').split('\0'))
unexpected = tracked - allowed
if unexpected:
    raise SystemExit('Refusing publication with unexpected tracked files: ' + ', '.join(sorted(unexpected)))
PYINDEX
if ! git diff --cached --quiet; then
 git -c user.name="$owner" -c user.email="$account_id+$owner@users.noreply.github.com" \
   commit -m "Release Ninetales Wallpapers $version prerelease"
fi
# A pre-existing repository is never overwritten or deleted.
if ! git remote get-url origin >/dev/null 2>&1; then
 if gh repo view "$repo" --json name >/dev/null 2>&1; then
  git remote add origin "https://github.com/$repo.git"
 else
  gh repo create "$repo" --public --source=. --remote=origin \
    --description 'GTK wallpaper manager for Hyprland and Caelestia, with native playback and an experimental Proton bridge.'
 fi
fi
origin=$(git remote get-url origin)
[[ $origin == "https://github.com/$repo.git" || $origin == "git@github.com:$repo.git" ]] || {
 echo 'Origin points at another repository; review it before publishing.' >&2; exit 1;
}
git push --set-upstream origin HEAD:main
if ! git rev-parse "v$version" >/dev/null 2>&1; then
 git tag "v$version"
fi
# This triggers the release workflow, which uploads the source archives and checksums.
git push origin "v$version"
echo "Repository: https://github.com/$repo"
echo "Release workflow: https://github.com/$repo/actions"
echo "Release (after the workflow completes): https://github.com/$repo/releases/tag/v$version"
