"""Provider boundary checks; run with the installed voice environment."""
import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
try:
    from livekit.agents import llm
    VOICE_SDK = True
except ImportError:
    VOICE_SDK = False


@unittest.skipUnless(VOICE_SDK, 'Requires the installed voice environment')
class MaffeoDialogue(unittest.IsolatedAsyncioTestCase):
    async def test_failed_or_silent_readback_never_enables_confirmation(self):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        from livekit.agents.voice.speech_handle import SpeechHandle
        from codex_phone.cloud_voice import read_back_proposal
        from codex_phone.voice_decision import Decision
        for failed, interrupted in [(True, False), (False, True), (False, False)]:
            decision = Decision()
            handle = SpeechHandle(speech_id='test', allow_interruptions=True, input_details=None)
            if interrupted:
                handle.interrupt()
            handle._mark_done(error=RuntimeError('synthetic TTS failure') if failed else None)
            audio = SimpleNamespace(total_samples=0)
            def say(*args, **kwargs):
                # Failed/interrupted playback may have emitted partial audio.
                if failed or interrupted:
                    audio.total_samples += 640
                return handle
            session = SimpleNamespace(output=SimpleNamespace(audio=audio), say=say)
            with self.assertRaisesRegex(RuntimeError, 'Readback audio'):
                await read_back_proposal(session, decision, 'Option A')
            decision.heard('Ja')
            with self.assertRaises(ValueError):
                decision.confirm()

    async def test_dialogue_uses_maffeo_model_and_streams_answer(self):
        from codex_phone.voice_models import dialogue_model
        requests = []
        async def serve(reader, writer):
            header = await reader.readuntil(b'\r\n\r\n')
            length = int(next(x.split(b':', 1)[1] for x in header.split(b'\r\n')
                              if x.lower().startswith(b'content-length:')))
            requests.append(json.loads(await reader.readexactly(length)))
            events = [dict(id='test', object='chat.completion.chunk', model='gpt-oss-120b',
                           choices=[dict(index=0, delta={'content': 'Option A'}, finish_reason=None)]),
                      dict(id='test', object='chat.completion.chunk', model='gpt-oss-120b',
                           choices=[dict(index=0, delta={}, finish_reason='stop')])]
            data = ''.join('data: '+json.dumps(e)+'\n\n' for e in events)+'data: [DONE]\n\n'
            writer.write(('HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nContent-Length: '+str(len(data.encode()))+'\r\n\r\n'+data).encode())
            await writer.drain(); writer.close(); await writer.wait_closed()
        server = await asyncio.start_server(serve, '127.0.0.1', 0)
        port = server.sockets[0].getsockname()[1]
        model = dialogue_model({'dialogue_backend': 'maffeo'},
                               base_url=f'http://127.0.0.1:{port}/v1')
        try:
            context = llm.ChatContext()
            context.add_message(role='user', content='Choose Option A')
            content = ''
            async with model.chat(chat_ctx=context) as stream:
                async for chunk in stream:
                    if chunk.delta and chunk.delta.content:
                        content += chunk.delta.content
            self.assertEqual(content, 'Option A')
            self.assertEqual(requests[0]['model'], 'gpt-oss-120b')
            self.assertEqual(requests[0]['reasoning_effort'], 'low')
        finally:
            await model.aclose(); server.close(); await server.wait_closed()

    async def test_external_dialogue_endpoint_is_refused(self):
        from codex_phone.voice_models import dialogue_model
        with self.assertRaisesRegex(ValueError, 'loopback'):
            dialogue_model({'dialogue_backend': 'maffeo'}, base_url='https://api.openai.com/v1')
