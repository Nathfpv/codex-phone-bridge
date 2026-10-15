#!/usr/bin/env python3
"""Offline SDK/Unix-datagram test, NOT cloud/SIP/iPhone proof."""
import asyncio
import socket
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from livekit import rtc
from codex_phone.cloud_voice import SipInput, SipOutput


async def main():
    with tempfile.TemporaryDirectory(prefix='cpb-io-') as directory:
        path = str(Path(directory) / 'pcm')
        receiver = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        receiver.bind(path)
        receiver.setblocking(False)
        sender = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        sender.setblocking(False)
        output = SipOutput(sender)
        try:
            await output.capture_frame(rtc.AudioFrame(b"\0" * 640, 16000, 1, 320))
        except RuntimeError:
            pass
        else:
            raise AssertionError("Output must reject audio before SIP connection")
        output.connect(path)
        source = SipInput(receiver)
        packet = b'\x01\x02' * 320
        await output.capture_frame(rtc.AudioFrame(packet, 16000, 1, 320))
        incoming = await asyncio.wait_for(source.__anext__(), 1)
        assert bytes(incoming.data) == packet
        output.flush()
        assert not (await output.wait_for_playout()).interrupted
        long_frame = rtc.AudioFrame(packet * 20, 16000, 1, 6400)
        task = asyncio.create_task(output.capture_frame(long_frame))
        await asyncio.sleep(.045)
        output.clear_buffer()
        await asyncio.wait_for(task, .2)
        count = 0
        while True:
            try:
                receiver.recv(65536)
                count += 1
            except BlockingIOError:
                break
        assert count <= 4, count
        assert (await output.wait_for_playout()).interrupted
        sender.close()
        receiver.close()
    print('PASS: SDK PCM roundtrip, paced playout and interruption. Cloud/SIP/iPhone NOT_TESTED.')


asyncio.run(main())
