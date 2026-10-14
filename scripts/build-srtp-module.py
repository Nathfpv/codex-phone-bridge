#!/usr/bin/env python3
"""Build only an isolated upstream SRTP module with TX cipher-reset fix."""
import hashlib
from pathlib import Path
import subprocess
import urllib.request
ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'.local/srtp-module'
DEST.mkdir(mode=0o700,parents=True,exist_ok=True)
HASHES={'srtp.c': '08f0281e4e7afc93838a26ceddd3075eb029148edfae21bfa8a6dd9937d9907e', 'sdes.c': 'ddf0dff0e4496b1cb05dcff6b1daa9a217974c7f633cb02541479d61ae6a3ecc', 'sdes.h': '2e9325fff68b764270a796787de00c650ed799eb4ebb1708460347c892b3cc28'}
for name,digest in HASHES.items():
    content=urllib.request.urlopen('https://raw.githubusercontent.com/baresip/baresip/v4.12.0/modules/srtp/'+name).read()
    if hashlib.sha256(content).hexdigest()!=digest:raise RuntimeError('Upstream source checksum mismatch')
    (DEST/name).write_bytes(content)
subprocess.run(['patch','-p1','-i',str(ROOT/'native/srtp-rekey.patch')],cwd=DEST,check=True)
prefix=subprocess.check_output(['brew','--prefix'],text=True).strip()
subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-O2','-bundle','-undefined','dynamic_lookup','-I'+prefix+'/include/re','-I'+prefix+'/include',str(DEST/'srtp.c'),str(DEST/'sdes.c'),'-o',str(ROOT/'.local/modules/srtp.so')],check=True)
print('Private SRTP module built; global Baresip untouched')
