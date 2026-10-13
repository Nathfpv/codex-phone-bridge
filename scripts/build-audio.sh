#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p .local/modules
BREW_PREFIX=$(brew --prefix)
BARESIP_PREFIX=$(brew --prefix baresip)
cc -std=c11 -Wall -Wextra -Werror -O2 -bundle -undefined dynamic_lookup \
 -I"$BREW_PREFIX/include/re" -I"$BARESIP_PREFIX/include" native/phoneaudio.c -o .local/modules/phoneaudio.so

cc -std=c11 -Wall -Wextra -Werror -O2 -bundle -undefined dynamic_lookup \
 -I"$BREW_PREFIX/include/re" -I"$BARESIP_PREFIX/include" native/phonecontrol.c -o .local/modules/phonecontrol.so
