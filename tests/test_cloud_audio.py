"""Real subprocess protocol tests; no provider or phone is contacted."""
import asyncio
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from codex_phone.cloud_audio import converse


class WorkerProtocol(unittest.IsolatedAsyncioTestCase):
    async def test_confirmed_receipt_is_acknowledged_before_graceful_close(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / '.local/voice-venv/bin/python'
            executable.parent.mkdir(parents=True)
            executable.symlink_to(sys.executable)
            marker = root / 'source-ready'
            marker.touch()
            rx, tx = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
            sip = SimpleNamespace(rx=rx, tx=tx, tx_path=str(marker), disconnected=asyncio.Event())
            actual_spawn = asyncio.create_subprocess_exec
            processes = []

            async def spawn(*args, **kwargs):
                program = ("import sys,json; o=json.loads(sys.stdin.readline()); "
                           "base={'v':2,'call_id':o['call_id']}; "
                           "print(json.dumps(dict(base,type='ready')),flush=True); sys.stdin.readline(); "
                           "print(json.dumps(dict(base,type='outcome',kind='confirmed',answer='Option A',metrics={})),flush=True); "
                           "print(json.dumps(dict(base,type='outcome',kind='confirmed',answer='Option A',metrics={})),flush=True); "
                           "ack=json.loads(sys.stdin.readline()); assert ack['type']=='outcome_ack'; "
                           "print(json.dumps(dict(base,type='ready_to_close')),flush=True)")
                process = await actual_spawn(sys.executable, '-c', program, **kwargs)
                processes.append(process)
                return process

            receipts = []
            async def save(answer):
                receipts.append(answer)
            try:
                with patch('codex_phone.cloud_audio.ROOT', root), \
                     patch.dict(os.environ, CODEX_PHONE_HOME=str(root / 'runtime')), \
                     patch('codex_phone.cloud_audio.asyncio.create_subprocess_exec', spawn):
                    result = await asyncio.wait_for(converse(sip, 'Choose an option', {
                        'cloud_voice': {'project_id': 'test', 'voice_id': 'test',
                                        'free_plan_verified': True}}, on_outcome=save), 3)
                self.assertEqual(result[0], 'Option A')
                self.assertEqual(receipts, ['Option A'])
                self.assertTrue(result[1]['farewell_completed'])
                self.assertIsNotNone(processes[0].returncode)
            finally:
                rx.close()
                tx.close()
