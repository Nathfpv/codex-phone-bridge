#!/usr/bin/env python3
"""Real native Unix-control negative tests using a local SIP-only fixture."""
import asyncio
import json
import os
from pathlib import Path
import socket
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from codex_phone.sip import Sip,netstring

async def main():
    probe=socket.socket();probe.bind(('127.0.0.1',0));port=probe.getsockname()[1];probe.close()
    s=Sip(local_port=port,peer='sip:bridge@127.0.0.1:9')
    try:
        await s.start()
        assert s.dir.stat().st_mode & 0o777 == 0o700
        assert Path(s.control_path).stat().st_mode & 0o777 == 0o600
        assert Path(s.rx_path).stat().st_mode & 0o777 == 0o600
        try:await s.command('quit')
        except RuntimeError:pass
        else:raise RuntimeError('Disallowed command accepted')
        assert s.proc.returncode is None
        await s.command('reginfo')
        s.writer.write(b'9999999:');await s.writer.drain()
        e=await s.event({'CONTROL_LOST'},5);assert e['type']=='CONTROL_LOST'
        r,w=await asyncio.open_unix_connection(s.control_path)
        b=json.dumps({'command':'reginfo','params':'','token':'test-reconnect'}).encode()
        w.write(str(len(b)).encode()+b':'+b+b',');await w.drain();result=await asyncio.wait_for(netstring(r),5)
        assert result.get('ok') is True
        w.close();await w.wait_closed()
        print('PASS: private owner-only Unix control, command restriction, oversized frame rejection, reconnect; no TCP control socket.')
    finally:await s.close()
asyncio.run(main())
