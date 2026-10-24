"""Real loopback SIP dialogs, never the configured personal destination."""
import asyncio
from pathlib import Path
import shutil
import socket
import unittest
from codex_phone.sip import Sip
from codex_phone.storage import ROOT


def port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


@unittest.skipUnless(shutil.which('baresip') and (ROOT/'.local/modules/phoneaudio.so').exists(),
                     'Requires installed local SIP modules')
class LocalHangup(unittest.IsolatedAsyncioTestCase):
    async def test_hangup_is_observed_by_both_local_peers(self):
        pa, pb = port(), port()
        while pb == pa:
            pb = port()
        a = Sip(local_port=pa, peer='sip:bridge@127.0.0.1:'+str(pb))
        b = Sip(local_port=pb, peer='sip:bridge@127.0.0.1:'+str(pa))
        try:
            await a.start(); await b.start()
            await a.dial()
            self.assertEqual((await b.event({'CALL_INCOMING'}, 5))['type'], 'CALL_INCOMING')
            await b.command('accept')
            await a.event({'CALL_ESTABLISHED'}, 5)
            await b.event({'CALL_ESTABLISHED'}, 5)
            self.assertTrue(await a.hangup_and_wait())
            await asyncio.wait_for(b.call_closed.wait(), 3)
            self.assertTrue(a.call_closed.is_set())
            self.assertTrue(b.call_closed.is_set())
        finally:
            await a.close(); await b.close()
