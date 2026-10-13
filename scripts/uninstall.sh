#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if test -S .local/runtime/control.sock || test -n "${CODEX_PHONE_HOME:-}"; then
  ./bin/codex-phone stop || { printf '%s\n' 'Stop failed; refusing to remove running artifacts.'; exit 1; }
fi
# Exact generated files only. No dependencies, credentials, queue or repository deletion.
rm -f .local/modules/phoneaudio.so .local/modules/phonecontrol.so .local/ggml-base.bin .local/ggml-base.bin.part
printf '%s\n' 'Generated modules/model removed. Private runtime and unanswered questions preserved.'
./bin/codex-phone doctor
