#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
command -v brew >/dev/null
command -v codex >/dev/null
python3 -c 'import sys; assert (3,9)<=sys.version_info[:2]<(3,13), "Python 3.9-3.12 required"'
for formula in baresip whisper.cpp; do
  if ! HOMEBREW_NO_AUTO_UPDATE=1 brew list --versions "$formula" >/dev/null 2>&1; then
    HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALL_CLEANUP=1 brew install "$formula"
  fi
done
./scripts/build-audio.sh
mkdir -p .local
if ! test -f .local/ggml-base.bin; then
  curl --fail --location --retry 2 https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin -o .local/ggml-base.bin.part
  printf '%s  %s\n' 60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe .local/ggml-base.bin.part | shasum -a 256 -c -
  mv .local/ggml-base.bin.part .local/ggml-base.bin
fi
printf '%s  %s\n' 60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe .local/ggml-base.bin | shasum -a 256 -c -
python3 -m unittest discover -s tests -v
./bin/codex-phone doctor
printf '%s\n' 'Installed locally. Configure in your terminal, then perform the real iPhone test.'
