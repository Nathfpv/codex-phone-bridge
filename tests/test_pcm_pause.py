"""Offline playback contract at the real SDK/Unix-datagram boundary."""
import asyncio
import errno
from pathlib import Path
import socket
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
try:
    from livekit import rtc
    from codex_phone.cloud_voice import SipOutput
    VOICE_SDK = True
except ImportError:
    VOICE_SDK = False


@unittest.skipUnless(VOICE_SDK, 'Requires the installed voice environment')
class PcmPause(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='cpb-pause-')
        self.addCleanup(self.directory.cleanup)
        self.receiver = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.receiver.bind(str(Path(self.directory.name) / 'pcm'))
        self.receiver.setblocking(False)
        self.addCleanup(self.receiver.close)
        self.sender = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.sender.setblocking(False)
        self.addCleanup(self.sender.close)
        self.output = SipOutput(self.sender, str(Path(self.directory.name) / 'pcm'))
        self.tasks = []

    async def asyncTearDown(self):
        self.output.clear_buffer()
        self.output.resume()
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    def capture(self, data):
        task = asyncio.create_task(self.output.capture_frame(
            rtc.AudioFrame(data, 16000, 1, len(data) // 2)))
        self.tasks.append(task)
        return task

    async def packet(self):
        return await asyncio.wait_for(
            asyncio.get_running_loop().sock_recv(self.receiver, 65536), .5)

    async def assert_silent(self):
        await asyncio.sleep(.065)
        with self.assertRaises(BlockingIOError):
            self.receiver.recv(65536)

    async def test_long_frame_pause_preserves_pcm_and_resume_pacing(self):
        packets = [bytes([i, 0]) * 320 for i in range(1, 9)]
        task = self.capture(b''.join(packets))
        self.assertEqual(await self.packet(), packets[0])
        self.output.pause()
        await self.assert_silent()
        self.assertFalse(task.done(), 'Pause must retain unfinished output')
        self.output.resume()
        received, times = [], []
        for _ in packets[1:]:
            received.append(await self.packet())
            times.append(asyncio.get_running_loop().time())
        await asyncio.wait_for(task, .5)
        self.output.flush()
        self.assertEqual(received, packets[1:])
        self.assertGreaterEqual(times[-1] - times[0], .09,
                                'Resume must not burst accumulated PCM')
        self.assertFalse((await self.output.wait_for_playout()).interrupted)
        self.assertTrue(self.output.can_pause)

    async def test_paused_partial_tail_flush_waits_for_resume(self):
        tail = b'\x12\x34' * 120
        await self.capture(tail)
        self.output.pause()
        self.output.flush()
        waiter = asyncio.create_task(self.output.wait_for_playout())
        self.tasks.append(waiter)
        await self.assert_silent()
        self.assertFalse(waiter.done(), 'Unplayed partial audio cannot count as finished')
        self.output.resume()
        self.assertEqual(await self.packet(), tail.ljust(640, b'\0'))
        event = await asyncio.wait_for(waiter, .5)
        self.assertFalse(event.interrupted)
        self.assertAlmostEqual(event.playback_position, 120 / 16000)

    async def test_clear_while_paused_wakes_producer_and_discards_old_pcm(self):
        old = b'\x01\x02' * 320
        task = self.capture(old * 8)
        self.assertEqual(await self.packet(), old)
        self.output.pause()
        await self.assert_silent()
        self.output.clear_buffer()
        await asyncio.wait_for(task, .3)
        self.assertTrue((await self.output.wait_for_playout()).interrupted)
        self.output.resume()
        fresh = b'\x07\x08' * 320
        await self.capture(fresh)
        self.output.flush()
        self.assertEqual(await self.packet(), fresh)
        await self.assert_silent()
        self.assertFalse((await self.output.wait_for_playout()).interrupted)

    async def test_clear_paused_partial_flush_does_not_leak_completion_to_new_segment(self):
        await self.capture(b'\x01\x02' * 100)
        self.output.pause()
        self.output.flush()
        self.output.flush()
        old_waiter = asyncio.create_task(self.output.wait_for_playout())
        self.tasks.append(old_waiter)
        await asyncio.sleep(.01)
        self.output.clear_buffer()
        self.assertTrue((await asyncio.wait_for(old_waiter, .3)).interrupted)
        self.output.resume()
        fresh = b'\x09\x0a' * 320
        await self.capture(fresh)
        self.output.flush()
        self.assertEqual(await self.packet(), fresh)
        await self.assert_silent()
        self.assertFalse((await self.output.wait_for_playout()).interrupted)

    async def test_deferred_flush_backpressure_resolves_as_interrupted(self):
        await self.capture(b'\x11\x22' * 100)
        # Saturate the real datagram receiver; no mocked transport exception.
        self.sender.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 2048)
        self.receiver.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2048)
        while True:
            try:
                self.sender.send(b'\0' * 640)
            except OSError as exc:
                self.assertIn(exc.errno, (errno.EAGAIN, errno.EWOULDBLOCK, errno.ENOBUFS))
                break
        self.output.pause()
        self.output.flush()
        self.output.resume()
        event = await asyncio.wait_for(self.output.wait_for_playout(), .3)
        self.assertTrue(event.interrupted, 'Failed deferred playback must never report success')
