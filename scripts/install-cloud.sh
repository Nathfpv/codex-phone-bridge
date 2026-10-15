#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
command -v uv >/dev/null || { printf '%s\n' 'Install uv first; see docs/CLOUD-VOICE.md.'; exit 1; }
command -v python3.12 >/dev/null || { printf '%s\n' 'An existing Python 3.12 is required.'; exit 1; }
if ! command -v lk >/dev/null; then
  command -v brew >/dev/null
  HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALL_CLEANUP=1 brew install livekit-cli
fi
if ! test -x .local/voice-venv/bin/python; then
  uv venv --python python3.12 .local/voice-venv
fi
uv pip sync --python .local/voice-venv/bin/python requirements-voice.lock
uv pip check --python .local/voice-venv/bin/python
printf '%s\n' 'Cloud SDK installed locally. Next: lk cloud auth; verify free Build plan; codex-phone cloud-config.'
