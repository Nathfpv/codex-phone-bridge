import asyncio
import audioop
import os
import time
import wave
from pathlib import Path
from .storage import ROOT

class Audio:
    def __init__(self, sip, model=None):
        self.sip=sip;self.model=Path(model or ROOT/'.local/ggml-base.bin');self.metrics={}
    async def run(self,*args):
        p=await asyncio.create_subprocess_exec(*args,stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
        try:
            rc=await asyncio.wait_for(p.wait(),90)
            if rc: raise RuntimeError('Audio subprocess failed: '+args[0])
        except BaseException:
            if p.returncode is None: p.kill();await p.wait()
            raise
    async def synthesize(self,text,voice=None):
        if not text.strip() or len(text)>4000: raise ValueError('Invalid speech length')
        before=time.monotonic(); path=self.sip.dir/'tts.wav'; msg=self.sip.dir/'tts.txt'
        msg.write_text(text);msg.chmod(0o600)
        try:
            await self.run('/usr/bin/say',*(['-v',voice] if voice else []),'-o',str(path),'--file-format=WAVE','--data-format=LEI16@16000','--channels=1','-f',str(msg))
            with wave.open(str(path),'rb') as w:
                if (w.getframerate(),w.getnchannels(),w.getsampwidth())!=(16000,1,2):raise RuntimeError('Unexpected PCM format')
                pcm=w.readframes(w.getnframes())
            self.metrics['tts_seconds']=round(time.monotonic()-before,3)
            return pcm
        finally: path.unlink(missing_ok=True);msg.unlink(missing_ok=True)
    async def play(self,pcm):
        loop=asyncio.get_running_loop();begin=loop.time();self.sip.tx.connect(self.sip.tx_path)
        for i in range(0,len(pcm),640):
            frame=pcm[i:i+640].ljust(640,b'\0')
            deadline=loop.time()+1
            while True:
                try:self.sip.tx.send(frame);break
                except (BlockingIOError,OSError) as exc:
                    if getattr(exc,'errno',None) not in (35,55) or loop.time()>deadline:raise
                    await asyncio.sleep(.005)
            await asyncio.sleep(max(0,begin+(i//640+1)*.02-loop.time()))
    async def speak(self,text): await self.play(await self.synthesize(text))
    def flush(self):
        while True:
            try: self.sip.rx.recv(65536)
            except BlockingIOError: break
    async def listen(self, timeout=30, silence=1.3):
        self.flush();loop=asyncio.get_running_loop();started=loop.time();last_voice=None;frames=[]
        while loop.time()-started<timeout:
            try: frame=await asyncio.wait_for(loop.sock_recv(self.sip.rx,65536),.3)
            except asyncio.TimeoutError:
                if last_voice and loop.time()-last_voice>=silence:break
                continue
            if len(frame)%2:continue
            loud=audioop.rms(frame,2)>300
            if loud:last_voice=loop.time()
            if last_voice:frames.append(frame)
            if last_voice and loop.time()-last_voice>=silence: break
        if not last_voice: raise RuntimeError('No speech received')
        pcm=b''.join(frames)
        if len(pcm)<16000:raise RuntimeError('Speech too short')
        return pcm
    async def transcribe(self,pcm):
        if not self.model.exists():raise RuntimeError('Whisper model missing')
        before=time.monotonic();p=self.sip.dir/'listen.wav';out=self.sip.dir/'transcript'
        with wave.open(str(p),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(pcm)
        p.chmod(0o600)
        try:
            await self.run('whisper-cli','-m',str(self.model),'-f',str(p),'-l','auto','-nt','-otxt','-of',str(out))
            text=out.with_suffix('.txt').read_text().strip()
            self.metrics['stt_seconds']=round(time.monotonic()-before,3)
            if len(text)<3 or '[' in text or '(' in text or len(text)>2000:raise RuntimeError('Unclear transcript')
            return text
        finally:
            p.unlink(missing_ok=True);out.with_suffix('.txt').unlink(missing_ok=True)
