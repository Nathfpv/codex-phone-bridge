#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
source_dir=.local/re-sips
commit=65555dad439de9d6a81b3ee6092b9c096585249b
if [ ! -d "$source_dir" ]; then
  git clone --depth 1 --branch v4.12.0 https://github.com/baresip/re.git "$source_dir"
fi
[ "$(git -C "$source_dir" rev-parse HEAD)" = "$commit" ]
if git -C "$source_dir" apply --check ../../native/re-sips.patch 2>/dev/null; then
  git -C "$source_dir" apply ../../native/re-sips.patch
else
  git -C "$source_dir" apply --reverse --check ../../native/re-sips.patch
fi
python3 - <<'VERIFY'
from pathlib import Path
import subprocess
actual=subprocess.check_output(['git','-C','.local/re-sips','diff','--','src'])
expected=Path('native/re-sips.patch').read_bytes()
if actual!=expected:raise SystemExit('Unexpected private library source changes')
VERIFY
cmake -S "$source_dir" -B "$source_dir/build" -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=ON -DOPENSSL_ROOT_DIR="$(brew --prefix openssl@4)"
cmake --build "$source_dir/build" -j 6
