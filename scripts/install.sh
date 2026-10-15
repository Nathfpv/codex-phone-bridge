#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
command -v brew >/dev/null
command -v codex >/dev/null
python3 -c 'import sys; assert (3,9)<=sys.version_info[:2]<(3,13), "Python 3.9-3.12 required"'
for formula in baresip cmake; do
  if ! HOMEBREW_NO_AUTO_UPDATE=1 brew list --versions "$formula" >/dev/null 2>&1; then
    HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALL_CLEANUP=1 brew install "$formula"
  fi
done
./scripts/build-audio.sh
./scripts/build-sip-library.sh
python3 scripts/build-srtp-module.py
mkdir -p .local
python3 -m unittest discover -s tests -v
./bin/codex-phone doctor
printf '%s\n' 'SIP installed locally. Complete docs/CLOUD-VOICE.md before a real iPhone test. Local STT is disabled.'
