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
import time
import tempfile
from contextlib import ExitStack
from unittest.mock import patch
from pathlib import Path
import aiohttp
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from livekit import rtc
from livekit.agents import inference, APIConnectOptions
from codex_phone.sip import Sip
from codex_phone.cloud_voice import credentials, SipOutput, conversation
from codex_phone.cloud_audio import converse, prepare_voice
from codex_phone.storage import config
from codex_phone.bridge import Bridge


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
    first_audible_at = None
    connected_at = None
    async def drain():
        nonlocal received, first_audible_at
        while True:
            data = await asyncio.get_running_loop().sock_recv(b.rx, 65536)
            if max((abs(x) for x in array.array('h', data)), default=0) > 500:
                if first_audible_at is None:
                    first_audible_at = time.monotonic()
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
    prepared = None
    question = "Soll die mobile Navigation vereinfacht werden und Desktop unverändert bleiben?"
    installed = config()
    cfg = {"cloud_voice": {"project_id": args.project, "voice_id": args.voice,
                            "free_plan_verified": True, "max_call_seconds": 100},
           "dialogue_backend": installed.get('dialogue_backend', 'livekit'),
           "recognition_backend": installed.get('recognition_backend', 'livekit'),
           "provider_plan_evidence": installed.get('provider_plan_evidence', {})}
    cfg['cloud_voice']['synthesis_profile'] = args.synthesis_profile or installed.get('cloud_voice', {}).get('synthesis_profile', 'fish')
    drain_task = None
    mcp = None
    server = None
    bridge = None
    isolation = ExitStack()
    try:
        await b.start()
        if args.mcp:
            directory = isolation.enter_context(tempfile.TemporaryDirectory(prefix='cpb-mcp-sip-'))
            isolation.enter_context(patch.dict(os.environ, CODEX_PHONE_HOME=directory))
            # Only the SIP transport boundary is redirected to an actual local
            # synthetic peer. No personal account or destination is loaded.
            cfg.update(voice_backend='livekit', iphone_uri=f'sip:bridge@127.0.0.1:{b_port}')
            isolation.enter_context(patch('codex_phone.bridge.config', return_value=cfg))
            isolation.enter_context(patch('codex_phone.bridge.Sip', return_value=a))
            bridge = Bridge()
            server = await asyncio.start_unix_server(bridge.client, str(Path(directory)/'control.sock'))
            mcp = await asyncio.create_subprocess_exec(sys.executable, '-B',
                str(Path(__file__).resolve().parents[1]/'bin/codex-phone-mcp'),
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)
            async def invoke():
                request={'jsonrpc':'2.0','id':42,'method':'tools/call',
                         'params':({'name':'phone_call','arguments':{}} if args.open_hangup else
                                   {'name':'phone_decision','arguments':{'kind':'design','question':question}})}
                mcp.stdin.write(json.dumps(request).encode()+b'\n'); await mcp.stdin.drain()
                response=json.loads(await mcp.stdout.readline())
                assert response['id']==42, 'Response reached wrong invocation'
                payload=json.loads(response['result']['content'][0]['text'])
                if args.open_hangup:
                    assert payload.get('completed') is True, 'No completed open call'
                    assert 'decision' not in payload and 'confirmed' not in payload
                    assert payload['metrics'].get('local_dialog_closed') is True, 'No observed SIP hangup'
                    return None, payload['metrics']
                assert payload.get('confirmed') is True, 'No confirmed MCP decision'
                return payload['decision'], payload.get('metrics', {})
            task=asyncio.create_task(invoke())
        else:
            await a.start()
            prepared = await prepare_voice(a, question, cfg)
            await a.dial()
        incoming = await b.event({'CALL_INCOMING', 'CALL_CLOSED'}, 50)
        assert incoming['type'] == 'CALL_INCOMING'
        await b.command('accept')
        connected = await (b if args.mcp else a).event({'CALL_ESTABLISHED', 'CALL_CLOSED'}, 15)
        assert connected['type'] == 'CALL_ESTABLISHED'
        connected_at = time.monotonic()
        if prepared:
            prepared.options["connected_at"] = connected_at
        drain_task = asyncio.create_task(drain())
        if not args.mcp:
            task = asyncio.create_task(converse(a, question, cfg, prepared=prepared))
        if args.open_hangup:
            await asyncio.sleep(5)
            await say('Moment.')
            await asyncio.sleep(2)
            held_audio = received
            await asyncio.sleep(2)
            assert not task.done(), 'Hold unexpectedly ended call'
            assert received == held_audio, 'Assistant spoke during hold'
            await say('Ich möchte das Gespräch beenden.')
            answer, metrics = await asyncio.wait_for(task, 20)
        else:
            await asyncio.sleep(12)
            await say('Bitte vereinfache die mobile Navigation und lass Desktop unverändert.')
            await asyncio.sleep(12)
            for _ in range(3):
                if task.done():
                    break
                await say('Ja, wir schicken ab.')
                await asyncio.sleep(7)
            answer, metrics = await asyncio.wait_for(task, 30)
            answer = answer.lower()
            assert 'mobil' in answer and 'desktop' in answer, 'Decision content mismatch'
        assert received > 32000, 'No actual return RTP audio'
        if bridge:
            row=bridge.store.db.execute('SELECT status FROM questions').fetchone()
            assert row[0]==('COMPLETED' if args.open_hangup else 'ANSWERED'), 'Confirmed decision was not persisted'
            if args.open_hangup:
                assert bridge.store.db.execute('SELECT answer FROM questions').fetchone()[0] is None
            assert len(bridge.store.db.execute('SELECT id FROM calls').fetchall())==1, 'Duplicate call'
        print(json.dumps({'status': 'PASS', 'scope': 'real MCP + controller + local SIP/RTP + cloud' if args.mcp else 'synthetic caller, real local SIP/RTP and cloud',
                          'received_audio_bytes': received, 'metrics': metrics,
                          'first_audible_rtp_seconds': round(first_audible_at-connected_at, 3),
                          'scenario': 'hold then end by request' if args.open_hangup else 'confirmed decision',
                          'iphone': 'NOT_TESTED'}))
    finally:
        for item in (task, drain_task):
            if item and not item.done():
                item.cancel()
        await asyncio.gather(*(t for t in (task, drain_task) if t), return_exceptions=True)
        if prepared:
            await prepared.close()
        if mcp:
            mcp.stdin.close()
            try: await asyncio.wait_for(mcp.wait(), 5)
            except asyncio.TimeoutError: mcp.kill(); await mcp.wait()
        if server:
            server.close(); await server.wait_closed()
        if bridge:
            for pending in list(bridge.call_tasks): pending.cancel()
            await asyncio.gather(*bridge.call_tasks, return_exceptions=True)
            bridge.store.db.close()
        if a.dir.exists():
            await a.close()
        await b.close()
        isolation.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True)
    parser.add_argument('--voice', default='fa4c9eb3dccc4806b382b40d61c6b10a')
    parser.add_argument('--use-free-allowance', required=True, action='store_true')
    parser.add_argument('--open-hangup', action='store_true', help='Test OPEN hold then deterministic end; requires --mcp')
    parser.add_argument('--synthesis-profile', choices=('fish','cartesia-de'))
    parser.add_argument('--mcp', action='store_true', help='Include a real stdio MCP client and controller; calls ONLY a synthetic loopback SIP peer')
    logging.basicConfig(level=logging.WARNING)
    args = parser.parse_args()
    if args.open_hangup and not args.mcp:
        parser.error('--open-hangup requires --mcp')
    asyncio.run(main(args))
