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
        data=json.loads(await asyncio.wait_for(r.readline(),300))
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
    private_json(home()/'config.json',{'mac_uri':mac,'iphone_uri':iphone,'password':password,'model':str(model),'quiet_hours':[]})
    print('Saved locally; no secret printed. Next: codex-phone start; codex-phone test-call')

def doctor():
    report={'platform':sys.platform,'executables':{k:bool(shutil.which(k)) for k in ('codex','baresip','whisper-cli','say','cc')},
       'audio_module':all((ROOT/'.local/modules'/name).exists() for name in ('phoneaudio.so','phonecontrol.so')),'model':(ROOT/'.local/ggml-base.bin').exists(),
       'control_socket':(home()/'control.sock').exists(),'callkit':'BLOCKED_BY_USER: requires real locked iPhone test'}
    try:c=config();validate_uri(c['mac_uri']);validate_uri(c['iphone_uri']);report['config']='present (not registration proof)'
    except Exception:report['config']='BLOCKED_BY_USER'
    print(json.dumps(report,indent=2))

def main():
    os.umask(0o077)
    p=argparse.ArgumentParser(prog='codex-phone');s=p.add_subparsers(dest='cmd',required=True)
    for name in ('start','stop','status','doctor','test-call','logs','config','serve'):s.add_parser(name)
    l=s.add_parser('launch');l.add_argument('--cwd',required=True);l.add_argument('prompt')
    a=s.add_parser('resume');a.add_argument('thread')
    a=s.add_parser('answer');a.add_argument('id');a.add_argument('answer')
    a=s.add_parser('retry');a.add_argument('id')
    a=s.add_parser('approval');a.add_argument('id');a.add_argument('--decision',choices=['accept','decline','cancel'],required=True)
    a=s.add_parser('inspect-approval');a.add_argument('id')
    args=p.parse_args()
    try:
        if args.cmd=='config':configure();return
        if args.cmd=='doctor':doctor();return
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
        if args.cmd=='resume':msg['thread']=args.thread
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
