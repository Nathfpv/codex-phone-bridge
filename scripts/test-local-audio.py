#!/usr/bin/env python3
"""Real loopback SIP/RTP; explicitly NOT an iPhone/CallKit test."""
import asyncio
import json
import socket
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from codex_phone.sip import Sip
from codex_phone.audio import Audio

def port():
    s=socket.socket();s.bind(('127.0.0.1',0));p=s.getsockname()[1];s.close();return p
async def main():
    p1,p2=port(),port();uri=f'sip:bridge@127.0.0.1:{p2}'
    a=Sip(local_port=p1,peer=uri);b=Sip(local_port=p2,peer=f'sip:bridge@127.0.0.1:{p1}')
    try:
        await a.start();await b.start();await a.dial()
        e=await b.event({'CALL_INCOMING','CALL_CLOSED'},10);print('incoming',e['type'])
        if e['type']!='CALL_INCOMING':raise RuntimeError('Not incoming')
        print(await b.command('accept'))
        e=await a.event({'CALL_ESTABLISHED','CALL_CLOSED'},15);print('outgoing',e['type'])
        if e['type']!='CALL_ESTABLISHED':raise RuntimeError('Not established')
        aa,ab=Audio(a),Audio(b);await asyncio.sleep(.3)
        for sender,receiver,text in [(aa,ab,'Die mobile Navigation wird vereinfacht. Desktop bleibt unverändert.'),(ab,aa,'This is the return audio path. Keep the desktop unchanged.')]:
            pcm=await sender.synthesize(text,voice='Daniel' if text.startswith('This') else None)
            task=asyncio.create_task(receiver.listen(timeout=20))
            await asyncio.sleep(.05);await sender.play(pcm);received=await task
            transcript=await receiver.transcribe(received)
            print(json.dumps({'sent':text,'received_transcript':transcript,'received_pcm_bytes':len(received),'metrics':receiver.metrics},ensure_ascii=False))
            if not ('desktop' in transcript.lower() and ('unverändert' in transcript.lower() or 'unchanged' in transcript.lower())):raise RuntimeError('Transcript mismatch')
        print('PASS: real local SIP/RTP audio in both directions, TTS and Whisper. iPhone NOT_TESTED.')
    finally:await a.close();await b.close()
asyncio.run(main())
