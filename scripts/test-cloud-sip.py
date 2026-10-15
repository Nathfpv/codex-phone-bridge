#!/usr/bin/env python3
"""Real local SIP/RTP + real cloud speech. Synthetic caller, NOT iPhone proof.

Explicit opt-in because this consumes the project's free inference allowance.
No microphone, local transcription or private project context is used.
"""
import argparse
import array
import asyncio
import json
import logging
import os
import socket
import sys
from pathlib import Path
import aiohttp
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from livekit import rtc
from livekit.agents import inference, APIConnectOptions
from codex_phone.sip import Sip
from codex_phone.cloud_voice import credentials, SipOutput, conversation
from codex_phone.cloud_audio import converse


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


async def main(args):
    cred = credentials(args.project)
    os.environ.update(LIVEKIT_URL=cred['url'], LIVEKIT_API_KEY=cred['api_key'],
                      LIVEKIT_API_SECRET=cred['api_secret'])
    a_port, b_port = port(), port()
    a = Sip(local_port=a_port, peer=f'sip:bridge@127.0.0.1:{b_port}')
    b = Sip(local_port=b_port, peer=f'sip:bridge@127.0.0.1:{a_port}')
    received = 0
    async def drain():
        nonlocal received
        while True:
            data = await asyncio.get_running_loop().sock_recv(b.rx, 65536)
            if max((abs(x) for x in array.array('h', data)), default=0) > 500:
                received += len(data)
    async def say(text):
        async with aiohttp.ClientSession() as http:
            tts = inference.TTS(model='fishaudio/s2.1-pro', voice=args.voice,
                                language='de', sample_rate=16000, http_session=http)
            output = SipOutput(b.tx, b.tx_path)
            try:
                async with tts.synthesize(text, conn_options=APIConnectOptions(max_retry=0, timeout=20)) as stream:
                    async for event in stream:
                        await output.capture_frame(event.frame)
                output.flush()
            finally:
                await tts.aclose()
    task = None
    drain_task = None
    try:
        await a.start()
        await b.start()
        await a.dial()
        incoming = await b.event({'CALL_INCOMING', 'CALL_CLOSED'}, 10)
        assert incoming['type'] == 'CALL_INCOMING'
        await b.command('accept')
        connected = await a.event({'CALL_ESTABLISHED', 'CALL_CLOSED'}, 15)
        assert connected['type'] == 'CALL_ESTABLISHED'
        await asyncio.sleep(.4)
        drain_task = asyncio.create_task(drain())
        # Duplicate FDs: the worker owns its handles, the SIP owner owns originals.
        task = asyncio.create_task(converse(a,
            'Soll die mobile Navigation vereinfacht werden und Desktop unverändert bleiben?',
            {'cloud_voice': {'project_id': args.project, 'voice_id': args.voice,
                             'free_plan_verified': True, 'max_call_seconds': 70}}))
        await asyncio.sleep(12)
        await say('Bitte vereinfache die mobile Navigation und lass Desktop unverändert.')
        await asyncio.sleep(12)
        for _ in range(3):
            if task.done():
                break
            await say('Ja, genau.')
            await asyncio.sleep(7)
        answer, metrics = await asyncio.wait_for(task, 30)
        answer = answer.lower()
        assert 'mobil' in answer and 'desktop' in answer, 'Decision content mismatch'
        assert received > 32000, 'No actual return RTP audio'
        print(json.dumps({'status': 'PASS', 'scope': 'synthetic caller, real local SIP/RTP and cloud',
                          'received_audio_bytes': received, 'metrics': metrics,
                          'iphone': 'NOT_TESTED'}))
    finally:
        for item in (task, drain_task):
            if item and not item.done():
                item.cancel()
        await asyncio.gather(*(t for t in (task, drain_task) if t), return_exceptions=True)
        await a.close()
        await b.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True)
    parser.add_argument('--voice', default='fa4c9eb3dccc4806b382b40d61c6b10a')
    parser.add_argument('--use-free-allowance', required=True, action='store_true')
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main(parser.parse_args()))
