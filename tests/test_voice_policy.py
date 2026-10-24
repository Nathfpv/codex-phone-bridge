"""Actual SDK user-turn hook and production turn options, without providers."""
import asyncio
import unittest
from codex_phone.call_control import CallController
try:
    from codex_phone.decision_agent import DecisionAgent, short_speech
    from codex_phone.voice_session import build_session
    from test_turn_playout import ControlledVAD, BatchSTT, WaitingInput
    from livekit.agents import vad
    VOICE_SDK = True
except ImportError:
    VOICE_SDK = False


@unittest.skipUnless(VOICE_SDK, 'Requires installed voice environment')
class VoicePolicy(unittest.IsolatedAsyncioTestCase):
    async def test_hold_turn_reaches_controller_and_remains_in_actual_chat_context(self):
        detector = ControlledVAD()
        stt = BatchSTT('Moment')
        ctl = CallController(conversation=True)
        called = asyncio.Event()
        async def on_turn(msg):
            action = ctl.user_turn(msg.id, msg.text_content)
            called.set()
            return action
        agent = DecisionAgent(on_turn=on_turn, instructions='Deutsch.')
        session = build_session(vad=detector, stt=stt)
        session.input.audio = WaitingInput()
        try:
            await session.start(agent=agent, record=False)
            async with asyncio.timeout(2):
                while not detector.streams:
                    await asyncio.sleep(.01)
            detector.emit_speech(vad.VADEventType.START_OF_SPEECH)
            detector.emit_speech(vad.VADEventType.INFERENCE_DONE)
            await asyncio.sleep(.35)
            detector.emit_speech(vad.VADEventType.END_OF_SPEECH)
            await asyncio.wait_for(called.wait(), 3)
            await asyncio.sleep(.05)
            self.assertTrue(ctl.holding)
            self.assertTrue(any(getattr(m, 'text_content', '') == 'Moment'
                                for m in agent.chat_ctx.items))
            stt.text = 'Jetzt mein neues Anliegen'
            called.clear()
            detector.emit_speech(vad.VADEventType.START_OF_SPEECH)
            detector.emit_speech(vad.VADEventType.INFERENCE_DONE)
            await asyncio.sleep(.35)
            detector.emit_speech(vad.VADEventType.END_OF_SPEECH)
            await asyncio.wait_for(called.wait(), 3)
            self.assertFalse(ctl.holding)
            self.assertTrue(any(getattr(m, 'text_content', '') == 'Moment'
                                for m in agent.chat_ctx.items))
        finally:
            await session.aclose()

    async def test_spoken_reply_stops_after_two_sentences(self):
        async def source():
            for part in ('Erster Satz. Zwe', 'iter Satz. Dritter Satz. Noch mehr.'):
                yield part
        output = ''.join([part async for part in short_speech(source())])
        self.assertEqual(output.strip(), 'Erster Satz. Zweiter Satz.')
