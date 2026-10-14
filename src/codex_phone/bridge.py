import asyncio
import json
import re
import time
from .audio import Audio
from .sip import Sip
from .storage import Store,config,home
from .codex import Codex

class Bridge:
    def __init__(self):
        self.store=Store();self.lock=asyncio.Lock();self.questions={};self.approvals={};self.turns={};self.stopping=asyncio.Event();self.call_tasks=set();self.codex=None
    def log(self,event,**fields):
        # No prompts, transcripts, SIP identities, protocol payloads or credentials.
        with (home()/'events.jsonl').open('a') as f:f.write(json.dumps({'time':time.time(),'event':event,**fields})+'\n')
    async def event(self,obj):
        m=obj['method'];p=obj.get('params',{})
        if m in ('turn/started','turn/completed'):
            t=p.get('turn',{});tid=p.get('threadId');self.turns[tid]={'id':t.get('id'),'status':t.get('status')};self.log(m,thread=tid,status=t.get('status'))
            if m=='turn/completed':
                for qid,entry in list(self.questions.items()):
                    if entry['thread']==tid and not entry['delivered']:entry['live']=False;self.store.set_question(qid,'ORPHANED')
        if m=='serverRequest/resolved':
            for qid,entry in list(self.questions.items()):
                if str(p.get('requestId'))==str(entry['rpc_id']) and p.get('threadId')==entry['thread']:
                    entry['live']=False
                    if not entry.get('delivered'):self.store.set_question(qid,'ORPHANED')
        if m=='bridge/disconnected':
            for qid,entry in self.questions.items():
                if not entry['delivered']:entry['live']=False;self.store.set_question(qid,'ORPHANED')
    async def request(self,obj):
        p=obj.get('params',{});method=obj['method']
        if method=='item/tool/call' and p.get('tool')=='phone_decision':
            a=p.get('arguments',{})
            if isinstance(a,str):
                try:a=json.loads(a)
                except ValueError:a={}
            if a.get('kind') not in ('product','design') or not isinstance(a.get('question'),str) or not 1<=len(a['question'])<=2000:
                await self.codex.send({'id':obj['id'],'error':{'code':-32602,'message':'Invalid decision'}});return
            q=self.store.add(p['threadId'],p['turnId'],obj['id'],a['question'],time.time()+900)
            if q['id'] in self.questions:return
            self.questions[q['id']]={'rpc_id':obj['id'],'thread':p['threadId'],'turn':p['turnId'],'live':True,'delivered':False}
            self.store.set_question(q['id'],'WAITING');self.log('question_queued',question=q['id'])
            task=asyncio.create_task(self.call(q));self.call_tasks.add(task);task.add_done_callback(self.call_tasks.discard)
            return
        # All built-in user-input and approval requests stay on the local terminal.
        self.approvals[str(obj['id'])]=obj;self.log('local_action_required',method=method,request=str(obj['id']))
    async def deliver(self,qid,answer,source='local_text'):
        if not isinstance(answer,str) or not 1<=len(answer)<=2000:raise ValueError('Invalid answer')
        e=self.questions.get(qid)
        row=self.store.db.execute('SELECT * FROM questions WHERE id=?',(qid,)).fetchone()
        if not row or not e or not e['live'] or e['delivered'] or row['deadline']<time.time():raise RuntimeError('Question is no longer attached to a live Codex request')
        turn=self.turns.get(e['thread'])
        if turn and (turn['id']!=e['turn'] or turn['status'] in ('completed','failed','interrupted')):raise RuntimeError('Turn mismatch or ended')
        e['delivered']=True
        try:
            await self.codex.send({'id':e['rpc_id'],'result':{'contentItems':[{'type':'inputText','text':json.dumps({'decision':answer,'source':source})}],'success':True}})
        except BaseException:e['delivered']=False;raise
        e['live']=False;self.store.set_question(qid,'ANSWERED',answer);self.log('answer_delivered',question=qid,thread=e['thread'],turn=e['turn'])
    async def call(self,q,manual=False):
        async with self.lock:
            if time.time()>q['deadline']:return {'status':'FAILED','reason':'deadline'}
            if not manual:
                count=self.store.db.execute('SELECT COUNT(*) FROM calls WHERE question_id=?',(q['id'],)).fetchone()[0]
                if count>=2:return {'status':'FAILED','reason':'retry_limit'}
            sip=None;cid=self.store.new_call(q['id']);state='DIALING';self.log('call_started',call=cid)
            def transition(s):
                nonlocal state
                state=s;self.store.call_state(cid,s);self.log('call_state',call=cid,status=s)
            try:
                cfg=config()
                hour=time.localtime().tm_hour
                quiet=cfg.get('quiet_hours',[])
                if hour in quiet:raise RuntimeError('Quiet hours; question remains pending')
                if not manual and not self.questions.get(q['id'],{}).get('live'):raise RuntimeError('Question no longer live')
                sip=Sip(cfg);await sip.start()
                await sip.dial()
                ring_deadline=time.monotonic()+45
                while True:
                    remaining=ring_deadline-time.monotonic()
                    if remaining<=0:raise RuntimeError('Ring timeout')
                    ev=await sip.event({'CALL_RINGING','CALL_ESTABLISHED','CALL_CLOSED','CONTROL_LOST'},remaining)
                    if ev['type']=='CALL_RINGING':transition('RINGING');continue
                    if ev['type']!='CALL_ESTABLISHED':raise RuntimeError('Call not connected')
                    if ev.get('direction')!='outgoing' or ev.get('peeruri','').split(';')[0]!=cfg['iphone_uri']:raise RuntimeError('Call identity mismatch')
                    break
                transition('CONNECTED');audio=Audio(sip,cfg.get('model'))
                transition('SPEAKING');await audio.speak('Codex. Diese Antwort wird lokal transkribiert. '+q['question'])
                answer=None
                for attempt in range(2):
                    try:
                        transition('LISTENING');pcm=await audio.listen()
                        transition('PROCESSING');text=await audio.transcribe(pcm)
                        transition('CONFIRMING');await audio.speak('Ich habe verstanden: '+text+'. Sage genau: Antwort bestätigen. Oder sage: Wiederholen.')
                        reply=await audio.transcribe(await audio.listen(timeout=15))
                        normalized=re.sub(r'[^a-zäöüß ]','',reply.lower()).strip()
                        if normalized in ('antwort bestätigen','antwort bestaetigen','confirm answer'):
                            answer=text;break
                        await audio.speak('Bitte wiederhole deine Antwort.')
                    except RuntimeError:
                        if attempt==1:raise
                        await audio.speak('Die Antwort war unklar. Bitte wiederhole sie.')
                if not answer:raise RuntimeError('No confirmed answer')
                if sip.disconnected.is_set():raise RuntimeError('Call disconnected before confirmation delivery')
                if manual:self.store.set_question(q['id'],'TEST_COMPLETED')
                else:await self.deliver(q['id'],answer,source='confirmed_sip_speech')
                await audio.speak('Danke. Die Antwort ist zugeordnet. Auf Wiederhören.')
                transition('ENDING');return {'status':'ENDING','metrics':audio.metrics,'call_id':cid}
            except asyncio.CancelledError:
                self.store.call_state(cid,'FAILED','cancelled');raise
            except Exception as exc:
                # Do not store exception payloads which may carry private config.
                self.store.call_state(cid,'FAILED',type(exc).__name__);
                if manual:self.store.set_question(q['id'],'TEST_FAILED')
                self.log('call_failed',call=cid,error=type(exc).__name__)
                return {'status':'FAILED','reason':str(exc) if isinstance(exc,(RuntimeError,ValueError)) else type(exc).__name__,'call_id':cid}
            finally:
                if sip:await sip.close()
    async def command(self,msg):
        op=msg.get('op')
        if op=='status':
            calls=[dict(row) for row in self.store.db.execute('SELECT id,question_id,status,started,ended,error FROM calls ORDER BY started DESC LIMIT 10')]
            active=next((c['status'] for c in calls if c['ended'] is None),'IDLE')
            return {'call_state':active,'calls':calls,'questions':[{'id':q['id'],'status':q['status'],'session_id':q['session_id'],'turn_id':q['turn_id']} for q in self.store.pending()], 'turns':self.turns,'approvals':[{'id':k,'method':v['method']} for k,v in self.approvals.items()]}
        if op=='launch':
            result=await self.codex.launch(msg['cwd'],msg['prompt'])
            self.store.db.execute('INSERT INTO sessions VALUES (?,?)',(result['thread_id'],msg['cwd']));self.store.db.commit()
            return result
        if op=='resume':
            prompt=msg.get('prompt','Resume the same task. Earlier unresolved phone decisions are not authorized. Ask them again with phone_decision before acting.')
            if not isinstance(prompt,str) or not 1<=len(prompt)<=10000:raise ValueError('Invalid continuation prompt')
            row=self.store.db.execute('SELECT cwd FROM sessions WHERE id=?',(msg['thread'],)).fetchone()
            if not row:raise RuntimeError('Only controller-owned threads may resume')
            if self.turns.get(msg['thread'],{}).get('status')=='inProgress':raise RuntimeError('Turn already running')
            await self.codex.rpc('thread/resume',{'threadId':msg['thread'],'cwd':row['cwd'],'sandbox':'workspace-write','approvalPolicy':'on-request'})
            result=await self.codex.rpc('turn/start',{'threadId':msg['thread'],'input':[{'type':'text','text':prompt}]})
            return {'thread_id':msg['thread'],'turn_id':result['turn']['id']}
        if op=='answer':await self.deliver(msg['id'],msg['answer']);return {'status':'ANSWERED'}
        if op=='retry':
            q=next((x for x in self.store.pending() if x['id']==msg['id']),None)
            if not q or not self.questions.get(q['id'],{}).get('live'):raise RuntimeError('No live pending question')
            count=self.store.db.execute('SELECT COUNT(*) FROM calls WHERE question_id=?',(q['id'],)).fetchone()[0]
            if count>=2:raise RuntimeError('Two-call retry limit reached')
            return await self.call(q)
        if op=='test-call':
            q=self.store.add('manual-test','manual-test',str(time.time()),'Manueller Test. Sage einen kurzen Satz und bestätige danach die Antwort.',time.time()+180)
            return await self.call(q,manual=True)
        if op=='inspect-approval':
            obj=self.approvals.get(msg['id'])
            if not obj:raise RuntimeError('Unknown request')
            return obj
        if op=='approval':
            obj=self.approvals.get(msg['id'])
            if not obj:raise RuntimeError('Unknown local request')
            if obj['method'] not in ('item/commandExecution/requestApproval','item/fileChange/requestApproval'):raise RuntimeError('This request needs a native Codex client; voice cannot approve it')
            decision=msg['decision']
            if decision not in ('accept','decline','cancel'):raise ValueError('Invalid decision')
            await self.codex.send({'id':obj['id'],'result':{'decision':decision}});del self.approvals[msg['id']];return {'status':'RESOLVED'}
        if op=='stop':self.stopping.set();return {'status':'STOPPING'}
        raise ValueError('Unknown command')
    async def client(self,reader,writer):
        try:
            line=await asyncio.wait_for(reader.readline(),5)
            if len(line)>65536:raise ValueError('Command too large')
            current=asyncio.current_task();self.call_tasks.add(current)
            try:result=await self.command(json.loads(line))
            finally:self.call_tasks.discard(current)
            writer.write(json.dumps({'result':result}).encode()+b'\n')
        except Exception as exc:writer.write(json.dumps({'error':str(exc)}).encode()+b'\n')
        finally:
            await writer.drain();writer.close();await writer.wait_closed()
    async def deadlines(self):
        while not self.stopping.is_set():
            await asyncio.sleep(1)
            for q in self.store.pending():
                e=self.questions.get(q['id'])
                if e and e['live'] and q['deadline']<time.time():
                    e['live']=False;self.store.set_question(q['id'],'ORPHANED')
                    try:await self.codex.rpc('turn/interrupt',{'threadId':e['thread'],'turnId':e['turn']})
                    except RuntimeError:pass
                    self.log('decision_deadline',question=q['id'])
    async def run(self):
        import fcntl
        guard=(home()/'daemon.lock').open('a')
        try:
            fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            guard.close();raise RuntimeError('Already running')
        try:
            self.store.recover()
            await self.serve()
        finally:
            if self.codex and hasattr(self.codex,'proc') and self.codex.proc.returncode is None:await self.codex.close()
            guard.close()
    async def serve(self):
        import signal
        sock=home()/'control.sock'
        if sock.exists():
            try:
                r,w=await asyncio.open_unix_connection(str(sock));w.close();await w.wait_closed()
            except OSError:sock.unlink()
            else:raise RuntimeError('Already running')
        self.codex=Codex(self.request,self.event);await self.codex.start()
        server=await asyncio.start_unix_server(self.client,str(sock),limit=65536);sock.chmod(0o600)
        (home()/'daemon.pid').write_text(str(__import__('os').getpid()))
        loop=asyncio.get_running_loop()
        for sig in (signal.SIGTERM,signal.SIGINT):loop.add_signal_handler(sig,self.stopping.set)
        self.log('started');watchdog=asyncio.create_task(self.deadlines())
        try:await self.stopping.wait()
        finally:
            watchdog.cancel();await asyncio.gather(watchdog,return_exceptions=True)
            server.close();await server.wait_closed()
            for task in self.call_tasks:task.cancel()
            await asyncio.gather(*self.call_tasks,return_exceptions=True)
            await self.codex.close();self.store.recover();sock.unlink(missing_ok=True)
            (home()/'daemon.pid').unlink(missing_ok=True);self.log('stopped')
