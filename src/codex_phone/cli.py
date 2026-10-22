import argparse
import asyncio
import getpass
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from .storage import ROOT,home,config,private_json
from .sip import validate_uri

async def request(msg):
    try:r,w=await asyncio.open_unix_connection(str(home()/'control.sock'))
    except OSError:raise RuntimeError('Bridge is stopped. Run codex-phone start')
    w.write(json.dumps(msg).encode()+b'\n');await w.drain()
    try:
        line=await asyncio.wait_for(r.readline(),650)
        if not line:raise RuntimeError('Bridge stopped before replying')
        data=json.loads(line)
        if 'error' in data:raise RuntimeError(data['error'])
        return data['result']
    finally:w.close();await w.wait_closed()

def configure():
    if not sys.stdin.isatty():raise RuntimeError('Run config in a local interactive terminal; never send passwords in chat')
    print('Personal Linphone SIP-to-SIP only. Credentials stay in a mode-0600 local store. No PSTN.')
    mac=validate_uri(input('Mac SIP URI (sip:user@sip.linphone.org): ').strip())
    iphone=validate_uri(input('Your iPhone SIP URI: ').strip())
    if mac==iphone:raise ValueError('Use separate personal accounts for this test')
    password=getpass.getpass('Mac SIP password (hidden): ')
    if not password or any(c in password for c in '\r\n"\\;'):raise ValueError('Unsupported account password characters')
    model=ROOT/'.local/ggml-base.bin'
    existing=config() if (home()/'config.json').exists() else {}
    existing.update(mac_uri=mac,iphone_uri=iphone,password=password,model=str(model))
    existing.setdefault('quiet_hours',[])
    private_json(home()/'config.json',existing)
    print('Saved locally; no secret printed. Next: codex-phone start; codex-phone test-call')

def doctor():
    report={'platform':sys.platform,'executables':{k:bool(shutil.which(k)) for k in ('codex','baresip','cc')},
       'audio_module':all((ROOT/'.local/modules'/name).exists() for name in ('phoneaudio.so','phonecontrol.so')),
       'cloud_sdk':(ROOT/'.local/voice-venv/bin/python').exists(),'local_transcription':'disabled for calls',
       'control_socket':(home()/'control.sock').exists(),'callkit':'MANUAL_CHECK: see docs/CLOUD-ACCEPTANCE.md'}
    try:
        c=config();validate_uri(c['mac_uri']);validate_uri(c['iphone_uri']);report['config']='present (not registration proof)'
        from .readiness import call_readiness
        try: state=asyncio.run(request({'op':'status'}))['call_state']
        except RuntimeError: state='STOPPED'
        report['preflight']=call_readiness(c, state)
        report['voice_backend']=c.get('voice_backend','unconfigured')
        report['free_plan_verified']=bool(c.get('cloud_voice',{}).get('free_plan_verified'))
    except Exception:report['config']='BLOCKED_BY_USER'
    print(json.dumps(report,indent=2))

def main():
    os.umask(0o077)
    p=argparse.ArgumentParser(prog='codex-phone');s=p.add_subparsers(dest='cmd',required=True)
    for name in ('start','stop','status','doctor','register','test-call','logs','config','serve'):s.add_parser(name)
    a=s.add_parser('cloud-config');a.add_argument('--project-id',required=True);a.add_argument('--voice-id',required=True)
    a.add_argument('--free-plan-verified',action='store_true',required=True)
    l=s.add_parser('launch');l.add_argument('--cwd',required=True);l.add_argument('prompt')
    a=s.add_parser('resume');a.add_argument('thread');a.add_argument('--prompt')
    a=s.add_parser('answer');a.add_argument('id');a.add_argument('answer')
    a=s.add_parser('retry');a.add_argument('id')
    a=s.add_parser('approval');a.add_argument('id');a.add_argument('--decision',choices=['accept','decline','cancel'],required=True)
    a=s.add_parser('inspect-approval');a.add_argument('id')
    args=p.parse_args()
    try:
        if args.cmd=='config':configure();return
        if args.cmd=='cloud-config':
            import re
            if not re.fullmatch(r'p_[a-z0-9]+',args.project_id) or not re.fullmatch(r'[a-f0-9]{32}',args.voice_id):
                raise ValueError('Invalid project or Fish voice ID')
            c=config();c['voice_backend']='livekit'
            c['cloud_voice']={'project_id':args.project_id,'voice_id':args.voice_id,
                              'free_plan_verified':True,'max_call_seconds':300}
            private_json(home()/'config.json',c)
            print('Cloud voice configured. Credentials remain in the private LiveKit CLI store.');return
        if args.cmd=='doctor':doctor();return
        if args.cmd=='register':
            from .sip import Sip
            async def register():
                sip=Sip(config())
                try:
                    await sip.start()
                    return await sip.wait_registered()
                finally:await sip.close()
            print(json.dumps(asyncio.run(register()),indent=2));return
        if args.cmd=='logs':
            path=home()/'events.jsonl';print(path.read_text()[-20000:] if path.exists() else 'No events');return
        if args.cmd=='serve':
            from .bridge import Bridge
            async def serve(): await Bridge().run()
            asyncio.run(serve());return
        if args.cmd=='start':
            try:print(json.dumps(asyncio.run(request({'op':'status'})),indent=2));return
            except RuntimeError:pass
            f=open(home()/'daemon.log','ab')
            subprocess.Popen([sys.executable,str(ROOT/'bin/codex-phone'),'serve'],stdin=subprocess.DEVNULL,stdout=f,stderr=f,start_new_session=True)
            f.close()
            for _ in range(60):
                time.sleep(.1)
                try:print(json.dumps(asyncio.run(request({'op':'status'})),indent=2));return
                except RuntimeError:pass
            raise RuntimeError('Daemon failed; inspect private daemon.log')
        msg={'op':args.cmd}
        if args.cmd=='resume':
            msg['thread']=args.thread
            if args.prompt:msg['prompt']=args.prompt
        if args.cmd=='launch':
            cwd=Path(args.cwd).expanduser().resolve()
            if not cwd.is_dir():raise ValueError('Task directory missing')
            msg.update(cwd=str(cwd),prompt=args.prompt)
        if args.cmd in ('answer','retry','approval','inspect-approval'):msg['id']=args.id
        if args.cmd=='answer':msg['answer']=args.answer
        if args.cmd=='approval':
            details=asyncio.run(request({'op':'inspect-approval','id':args.id}))
            print(json.dumps(details,indent=2))
            if not sys.stdin.isatty() or input('Type the exact request ID to submit this local decision: ').strip()!=args.id:raise RuntimeError('Local confirmation missing')
            msg['decision']=args.decision
        result=asyncio.run(request(msg));print(json.dumps(result,indent=2))
        if isinstance(result,dict) and result.get('status')=='FAILED':sys.exit(1)
        if args.cmd=='stop':
            for _ in range(60):
                if not (home()/'control.sock').exists():return
                time.sleep(.1)
            raise RuntimeError('Shutdown has not completed')
    except (RuntimeError,ValueError,KeyError) as exc:print(str(exc),file=sys.stderr);sys.exit(1)
