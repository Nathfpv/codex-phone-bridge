"""Offline real AgentSession turn engine with deterministic VAD/STT boundaries.

This proves SDK interruption wiring, not acoustic recognition or iPhone delivery.
"""
import asyncio
from pathlib import Path
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
try:
    from livekit import rtc
    from livekit.agents import Agent, AgentSession, stt, vad
    from livekit.agents.voice import io
    from codex_phone.cloud_voice import SipOutput
    VOICE_SDK = True
except ImportError:
    VOICE_SDK = False

if VOICE_SDK:
    class ControlledVAD(vad.VAD):
        def __init__(self):
            super().__init__(capabilities=vad.VADCapabilities(update_interval=.02))
            self.streams = []

        def stream(self):
            stream = ControlledVADStream(self)
            self.streams.append(stream)
            return stream

        def emit_speech(self, kind):
            event = vad.VADEvent(type=kind, samples_index=16000,
                timestamp=time.time(), speech_duration=.8, silence_duration=0,
                speaking=kind != vad.VADEventType.END_OF_SPEECH,
                raw_accumulated_speech=.8, frames=[rtc.AudioFrame(b'\1\2'*320,16000,1,320)])
            for stream in self.streams:
                stream.emit(event)

    class ControlledVADStream(vad.VADStream):
        def emit(self, event):
            self._event_ch.send_nowait(event)

        async def _main_task(self):
            async for _ in self._input_ch:
                pass

    class BatchSTT(stt.STT):
        def __init__(self, text):
            super().__init__(capabilities=stt.STTCapabilities(streaming=False, interim_results=False))
            self.text = text

        async def _recognize_impl(self, buffer, *, language, conn_options):
            return stt.SpeechEvent(type=stt.SpeechEventType.FINAL_TRANSCRIPT,
                alternatives=[stt.SpeechData(language='de', text=self.text)])

    class WaitingInput(io.AudioInput):
        def __init__(self):
            super().__init__(label='offline-synthetic-input')
            self.wait = asyncio.Event()

        async def __anext__(self):
            await asyncio.sleep(.02)
            return rtc.AudioFrame(b'\0'*640,16000,1,320)


@unittest.skipUnless(VOICE_SDK, 'Requires the installed voice environment')
class TurnPlayout(unittest.IsolatedAsyncioTestCase):
    async def exercise(self, transcript):
        import socket
        import tempfile
        with tempfile.TemporaryDirectory(prefix='cpb-turn-') as directory:
            receiver = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            self.addCleanup(receiver.close)
            receiver.bind(str(Path(directory) / 'pcm'))
            receiver.setblocking(False)
            sender = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            self.addCleanup(sender.close)
            sender.setblocking(False)
            output_events = []
            output = SipOutput(sender, str(Path(directory) / 'pcm'),
                               diagnostic=lambda *args: output_events.append(args[0]))
            detector = ControlledVAD()
            session = AgentSession(vad=detector, stt=BatchSTT(transcript), aec_warmup_duration=None,
                turn_detection='vad', min_endpointing_delay=.05,
                min_interruption_duration=.1, min_interruption_words=0,
                false_interruption_timeout=.1, resume_false_interruption=True)
            session.input.audio = WaitingInput()
            session.output.audio = output
            false_events = []
            session.on('agent_false_interruption', lambda event: false_events.append(event))
            received = []
            async def drain():
                while True:
                    received.append(await asyncio.get_running_loop().sock_recv(receiver,65536))
            drain_task = asyncio.create_task(drain())
            try:
                await session.start(agent=Agent(instructions='Deutsch.'), record=False)
                async def audio():
                    for i in range(1, 101):
                        yield rtc.AudioFrame(bytes([i,0])*320,16000,1,320)
                handle = session.say('Eine lange Testantwort.',audio=audio())
                async def wait_for(predicate, timeout=2):
                    async with asyncio.timeout(timeout):
                        while not predicate():
                            await asyncio.sleep(.005)
                await wait_for(lambda: len(received)>=3)
                detector.emit_speech(vad.VADEventType.START_OF_SPEECH)
                detector.emit_speech(vad.VADEventType.INFERENCE_DONE)
                await wait_for(lambda:'output_paused' in output_events)
                paused_count = len(received)
                await asyncio.sleep(.07)
                self.assertLessEqual(len(received), paused_count+1)
                detector.emit_speech(vad.VADEventType.END_OF_SPEECH)
                if transcript:
                    await wait_for(lambda:handle.interrupted)
                    self.assertTrue(handle.interrupted)
                    self.assertLess(len(received),100)
                else:
                    await wait_for(lambda:bool(false_events))
                    self.assertTrue(false_events[-1].resumed)
                    await asyncio.wait_for(handle.wait_for_playout(),3)
                    self.assertFalse(handle.interrupted)
                    await wait_for(lambda:len(received)==100)
                    self.assertEqual(received,[bytes([i,0])*320 for i in range(1,101)])
            finally:
                await session.aclose()
                drain_task.cancel()
                await asyncio.gather(drain_task,return_exceptions=True)

    async def test_noise_without_transcript_resumes_exact_remaining_speech(self):
        await self.exercise('')

    async def test_recognized_user_speech_cancels_paused_assistant(self):
        await self.exercise('Stopp, ich möchte etwas korrigieren.')

    async def test_real_readback_rejects_transport_failed_tail_after_audible_prefix(self):
        import errno
        import socket
        import tempfile
        from types import SimpleNamespace
        from codex_phone.cloud_voice import read_back_proposal
        from codex_phone.voice_decision import Decision
        with tempfile.TemporaryDirectory(prefix='cpb-readback-') as directory:
            receiver = socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM)
            self.addCleanup(receiver.close)
            receiver.bind(str(Path(directory)/'pcm'))
            receiver.setblocking(False)
            sender = socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM)
            self.addCleanup(sender.close)
            sender.setblocking(False)
            output = SipOutput(sender,str(Path(directory)/'pcm'))
            session = AgentSession(aec_warmup_duration=None)
            session.output.audio = output
            handles = []
            async def audio():
                yield rtc.AudioFrame(b'\1\2'*320,16000,1,320)
                yield rtc.AudioFrame(b'\3\4'*100,16000,1,100)
                output.pause()
            def say(text, **kwargs):
                handle = session.say(text,audio=audio(),**kwargs)
                handles.append(handle)
                return handle
            proxy = SimpleNamespace(output=session.output,say=say)
            decision = Decision()
            await session.start(agent=Agent(instructions='Deutsch.'),record=False)
            task = asyncio.create_task(read_back_proposal(proxy,decision,'Option A'))
            try:
                await asyncio.wait_for(asyncio.get_running_loop().sock_recv(receiver,640),1)
                async with asyncio.timeout(1):
                    while output.pending_flush is None:
                        await asyncio.sleep(.005)
                self.assertGreater(output.total_samples,0)
                sender.setsockopt(socket.SOL_SOCKET,socket.SO_SNDBUF,2048)
                receiver.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,2048)
                while True:
                    try:
                        sender.send(b'\0'*640)
                    except OSError as exc:
                        self.assertIn(exc.errno,(errno.EAGAIN,errno.EWOULDBLOCK,errno.ENOBUFS))
                        break
                output.resume()
                with self.assertRaisesRegex(RuntimeError,'Readback audio'):
                    await asyncio.wait_for(task,1)
                # SDK handle can finish successfully despite the sink's failed tail.
                self.assertFalse(handles[0].interrupted)
                self.assertIsNone(handles[0].exception())
                decision.heard('Ja')
                with self.assertRaises(ValueError):
                    decision.confirm()
            finally:
                task.cancel()
                await asyncio.gather(task,return_exceptions=True)
                await session.aclose()
