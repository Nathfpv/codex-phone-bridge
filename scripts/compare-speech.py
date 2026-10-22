#!/usr/bin/env python3
"""Opt-in synthetic speech comparison, RAM only. Not human/iPhone proof."""
import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import aiohttp
from livekit import rtc
from livekit.agents import inference, APIConnectOptions, stt
from livekit.plugins import groq
from codex_phone.cloud_voice import credentials
from codex_phone.cloud_audio import provider_cap_verified
from codex_phone.storage import config


async def main():
    cfg = config()
    if not provider_cap_verified(cfg):
        raise RuntimeError('Current Build plan verification required')
    c = credentials(cfg['cloud_voice']['project_id'])
    os.environ.update(LIVEKIT_URL=c['url'], LIVEKIT_API_KEY=c['api_key'], LIVEKIT_API_SECRET=c['api_secret'])
    key = (Path.home()/'.groq-key').read_text().strip()
    async with aiohttp.ClientSession() as http:
        voice = inference.TTS(model='fishaudio/s2.1-pro', voice=cfg['cloud_voice']['voice_id'],
                              language='de', sample_rate=16000, http_session=http)
        assembly = inference.STT(model='assemblyai/universal-streaming-multilingual', language='de', http_session=http)
        whisper = groq.STT(model='whisper-large-v3', api_key=key, language='de')
        try:
            for sentence in ['Bitte wähle Option A und behalte Desktop unverändert.',
                             'Die Zahl ist dreiundzwanzig, nicht zweiunddreissig.',
                             'Ja, aber bitte ändere auch die mobile Navigation.']:
                pcm = bytearray(); t = time.monotonic(); first = None
                async with voice.synthesize(sentence, conn_options=APIConnectOptions(max_retry=0, timeout=20)) as stream:
                    async for event in stream:
                        if first is None: first = time.monotonic()-t
                        pcm.extend(event.frame.data)
                frame = rtc.AudioFrame(bytes(pcm), 16000, 1, len(pcm)//2)
                t = time.monotonic()
                result = await whisper.recognize(frame, conn_options=APIConnectOptions(max_retry=0, timeout=20))
                whisper_time = time.monotonic()-t
                transcript = []
                async with assembly.stream(conn_options=APIConnectOptions(max_retry=0, timeout=20)) as stream:
                    async def read():
                        async for event in stream:
                            if event.type == stt.SpeechEventType.FINAL_TRANSCRIPT:
                                transcript.extend(a.text for a in event.alternatives[:1])
                    reader = asyncio.create_task(read())
                    for start in range(0, len(pcm), 640):
                        data = bytes(pcm[start:start+640]).ljust(640, b'\0')
                        stream.push_frame(rtc.AudioFrame(data, 16000, 1, 320))
                        await asyncio.sleep(.02)
                    for _ in range(75):
                        stream.push_frame(rtc.AudioFrame(b'\0'*640,16000,1,320)); await asyncio.sleep(.02)
                    ended = time.monotonic(); stream.end_input()
                    try: await asyncio.wait_for(reader, 10)
                    finally:
                        reader.cancel(); await asyncio.gather(reader, return_exceptions=True)
                print(json.dumps({'expected':sentence,'audio_seconds':round(len(pcm)/32000,3),
                    'fish_first_audio_s':round(first,3), 'whisper':result.alternatives[0].text,
                    'whisper_after_utterance_s':round(whisper_time,3), 'assembly':' '.join(transcript),
                    'assembly_stream_close_s':round(time.monotonic()-ended,3)}, ensure_ascii=False), flush=True)
        finally:
            await voice.aclose(); await assembly.aclose(); await whisper.aclose()


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--use-free-allowance', action='store_true', required=True)
    parser.parse_args()
    logging.disable(logging.CRITICAL)
    asyncio.run(main())
