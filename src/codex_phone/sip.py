import asyncio
import json
import os
import re
import shutil
import socket
import tempfile
import uuid
from pathlib import Path
from .storage import ROOT

URI = re.compile(r'^sip:([A-Za-z0-9_.-]{3,80})@sip\.linphone\.org$')

def validate_uri(value):
    if not isinstance(value,str) or not URI.fullmatch(value):
        raise ValueError('Only a personal sip:user@sip.linphone.org address is allowed')
    return value

async def netstring(reader):
    size = bytearray()
    while True:
        ch = await reader.readexactly(1)
        if ch == b':': break
        if not ch.isdigit() or len(size)>7: raise ValueError('Invalid netstring')
        size.extend(ch)
    n=int(size)
    if n>1048576: raise ValueError('Oversized netstring')
    data = await reader.readexactly(n)
    if await reader.readexactly(1) != b',': raise ValueError('Invalid netstring terminator')
    return json.loads(data)

class Sip:
    def __init__(self, cfg=None, *, local_port=None, peer=None):
        self.cfg=cfg; self.local_port=local_port; self.peer=peer
        self.dir=Path(tempfile.mkdtemp(prefix='cpb-')); self.dir.chmod(0o700)
        self.disconnected=asyncio.Event();self.events=asyncio.Queue(); self.waiters={}; self.tasks=[]; self.proc=None
        self.tx_path=str(self.dir/'tx'); self.rx_path=str(self.dir/'rx')
        self.rx=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM); self.rx.bind(self.rx_path)
        os.chmod(self.rx_path,0o600); self.rx.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,262144); self.rx.setblocking(False)
        self.tx=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM); self.tx.setsockopt(socket.SOL_SOCKET,socket.SO_SNDBUF,262144); self.tx.setblocking(False)
    async def start(self):
        self.control_path=str(self.dir/'control.sock')
        prefix=Path(shutil.which('baresip')).resolve().parents[1]
        modules=prefix/'lib/baresip/modules'
        custom=ROOT/'.local/modules/phoneaudio.so'
        if not custom.exists(): raise RuntimeError('Build phoneaudio first')
        private_modules=self.dir/'modules';private_modules.mkdir(mode=0o700)
        for file in modules.glob('*.so'):(private_modules/file.name).symlink_to(file)
        patched_srtp=ROOT/'.local/modules/srtp.so'
        if patched_srtp.exists():
            (private_modules/'srtp.so').unlink(missing_ok=True)
            (private_modules/'srtp.so').symlink_to(patched_srtp)
        (private_modules/'phoneaudio.so').symlink_to(custom)
        (private_modules/'phonecontrol.so').symlink_to(ROOT/'.local/modules/phonecontrol.so')
        base=f'''poll_method kqueue
net_interface {'en0' if self.cfg else '127.0.0.1'}
sip_listen 127.0.0.1:{self.local_port or 0}
call_max_calls 1
call_local_timeout 45
call_max_duration 180
sip_verify_server yes
sip_cafile /etc/ssl/cert.pem
audio_player phoneaudio,{self.rx_path}
audio_source phoneaudio,{self.tx_path}
audio_alert phoneaudio,{self.rx_path}
ausrc_srate 16000
auplay_srate 16000
ausrc_channels 1
auplay_channels 1
audio_buffer 20-160
audio_level no
audio_txmode poll
audio_source_format s16
audio_player_format s16
module_path {private_modules}
module g711.so
module auconv.so
module auresamp.so
module phoneaudio.so
module menu.so
module_app account.so
module_app phonecontrol.so
phonecontrol_socket {self.control_path}
redial_attempts 0
video_source none
video_display none
'''
        if self.cfg:
            validate_uri(self.cfg['mac_uri']); validate_uri(self.cfg['iphone_uri'])
            pw=self.cfg['password']
            if any(c in pw for c in '\r\n"\\;'):
                raise ValueError('Password contains unsupported Baresip account characters')
            base += 'sip_transports tls\nmodule stun.so\nmodule ice.so\nmodule srtp.so\n'
            # IPv4 interface binding for outbound provider; media path uses ICE.
            base=base.replace(f'sip_listen 127.0.0.1:0','sip_listen 0.0.0.0:0')
            user=URI.fullmatch(self.cfg['mac_uri']).group(1)
            account=f'"Codex Phone Bridge" <{self.cfg["mac_uri"]}>;auth_user={user};auth_pass="{pw}";outbound="sip:sip.linphone.org;transport=tls";regint=600;medianat=ice;stunserver=stun:stun.cloudflare.com:3478;mediaenc=srtp-mand;answermode=manual\n'
        else:
            account=f'<sip:bridge@127.0.0.1:{self.local_port}>;regint=0;answermode=manual\n'
        for name,content in [('config',base),('accounts',account)]:
            p=self.dir/name; p.write_text(content);p.chmod(0o600)
        env=os.environ.copy()
        private_re=ROOT/'.local/re-sips/build'
        if (private_re/'libre.45.dylib').exists():
            env['DYLD_LIBRARY_PATH']=str(private_re)
        self.proc=await asyncio.create_subprocess_exec('baresip','-4','-f',str(self.dir),stdin=asyncio.subprocess.DEVNULL,
                        stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT,env=env)
        self.diagnostics=[];self.local_diagnostics=[]
        async def drain():
            while True:
                line=await self.proc.stdout.readline()
                if not line: break
                # Raw SIP output never persisted; expose only dependency errors.
                s=line.decode(errors='replace')
                if not self.cfg:self.local_diagnostics.append(s)
                if 'module' in s and ('failed' in s or 'error' in s): self.diagnostics.append(s.strip())
        self.tasks.append(asyncio.create_task(drain()))
        for _ in range(60):
            if self.proc.returncode is not None: raise RuntimeError('Baresip exited; '+str(self.diagnostics))
            try:
                self.reader,self.writer=await asyncio.open_unix_connection(self.control_path);break
            except OSError: await asyncio.sleep(.1)
        else: raise RuntimeError('Baresip control unavailable')
        self.tasks.append(asyncio.create_task(self.read_events()))
        for _ in range(50):
            result=await self.command('reginfo')
            if 'User Agents (1)' in result.get('data',''):break
            await asyncio.sleep(.1)
        else:raise RuntimeError('Baresip account not loaded')
    async def read_events(self):
        try:
            while True:
                msg=await netstring(self.reader)
                if msg.get('response'):
                    f=self.waiters.pop(msg.get('token'),None)
                    if f and not f.done(): f.set_result(msg)
                elif msg.get('event'):
                    if msg.get('type')=='CALL_CLOSED':self.disconnected.set()
                    if self.cfg and msg.get('type')=='CALL_INCOMING':
                        # No unauthenticated incoming decision path in v1.
                        self.tasks.append(asyncio.create_task(self.hangup()))
                    else:await self.events.put(msg)
        except (OSError,asyncio.IncompleteReadError,ValueError):
            self.disconnected.set();await self.events.put({'type':'CONTROL_LOST'})
    async def command(self, name, params=''):
        token=str(uuid.uuid4()); f=asyncio.get_running_loop().create_future();self.waiters[token]=f
        b=json.dumps({'command':name,'params':params,'token':token}).encode()
        self.writer.write(str(len(b)).encode()+b':'+b+b',');await self.writer.drain()
        try:
            msg=await asyncio.wait_for(f,5)
            if not msg['ok']: raise RuntimeError('SIP command failed: '+name)
            return msg
        finally: self.waiters.pop(token,None)
    async def event(self, types, timeout=45):
        async def loop():
            while True:
                e=await self.events.get()
                if e['type'] in types: return e
        return await asyncio.wait_for(loop(),timeout)
    async def dial(self, uri=None):
        if self.cfg:
            await self.wait_registered()
        uri=uri or (self.cfg['iphone_uri'] if self.cfg else self.peer)
        if self.cfg:
            validate_uri(uri)
            if uri!=self.cfg['iphone_uri']:raise ValueError('Destination must match the configured owner')
        elif uri!=self.peer: raise ValueError('Local test peer mismatch')
        self.disconnected.clear();return await self.command('dial',uri)
    async def wait_registered(self, timeout=20):
        """Check provider registration without dialing or disclosing identities."""
        deadline=asyncio.get_running_loop().time()+timeout
        while asyncio.get_running_loop().time()<deadline:
            info=await self.command('reginfo')
            data=info.get('data','')
            plain=re.sub(r'\x1b\[[0-9;]*m','',data)
            # Match the actual status field with a live expiry, not a username
            # containing "OK" or an expired previous registration.
            if re.search(r'(?:^|\s)OK\s+[^\r\n]+?\s+Expires [1-9][0-9]*s\b',plain):
                return {'status':'REGISTERED'}
            if re.search(r'(?:^|\s)(?:FB-)?ERR(?:\s|$)',plain):
                raise RuntimeError('SIP registration rejected; check account or provider status')
            if self.proc.returncode is not None or self.disconnected.is_set():
                raise RuntimeError('SIP control disconnected during registration')
            await asyncio.sleep(.2)
        raise RuntimeError('SIP registration not confirmed before timeout')
    async def hangup(self):
        if hasattr(self,'writer'):
            try: await self.command('hangup')
            except (OSError,RuntimeError,asyncio.TimeoutError): pass
    async def close(self):
        await self.hangup()
        if hasattr(self,'writer'):
            self.writer.close()
            try:await self.writer.wait_closed()
            except OSError:pass
        if self.proc and self.proc.returncode is None:
            self.proc.terminate()
            try: await asyncio.wait_for(self.proc.wait(),4)
            except asyncio.TimeoutError: self.proc.kill();await self.proc.wait()
        for t in self.tasks: t.cancel()
        await asyncio.gather(*self.tasks,return_exceptions=True)
        self.rx.close();self.tx.close();shutil.rmtree(self.dir)
