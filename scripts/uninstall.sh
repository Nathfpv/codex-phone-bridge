#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if test -S .local/runtime/control.sock || test -n "${CODEX_PHONE_HOME:-}"; then
  ./bin/codex-phone stop || { printf '%s\n' 'Stop failed; refusing to remove running artifacts.'; exit 1; }
fi
# Exact generated files only. No dependencies, credentials, queue or repository deletion.
rm -f .local/modules/phoneaudio.so .local/modules/phonecontrol.so .local/modules/srtp.so .local/ggml-base.bin .local/ggml-base.bin.part
# Retain downloaded source for inspection; remove only generated private library.
rm -f .local/re-sips/build/libre.dylib .local/re-sips/build/libre.45.dylib .local/re-sips/build/libre.45.12.0.dylib
printf '%s\n' 'Generated modules/model removed. Private runtime and unanswered questions preserved.'
./bin/codex-phone doctor
