import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from codex_phone.storage import Store
from codex_phone.sip import Sip,validate_uri,netstring
from types import SimpleNamespace
from codex_phone.bridge import Bridge

class Persistence(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'state.sqlite3')
    def tearDown(self):self.store.db.close();self.tmp.cleanup()
    def test_duplicate_request_and_restart(self):
        q=self.store.add('thread-a','turn-a','rpc-1','Question',time.time()+60)
        again=self.store.add('thread-a','turn-a','rpc-1','Question',time.time()+60)
        self.assertEqual(q['id'],again['id'])
        self.store.set_question(q['id'],'WAITING');cid=self.store.new_call(q['id']);self.store.recover()
        self.assertEqual(self.store.pending()[0]['status'],'ORPHANED')
        self.assertEqual(self.store.db.execute('SELECT status FROM calls WHERE id=?',(cid,)).fetchone()[0],'FAILED')
    def test_parallel_thread_isolation(self):
        a=self.store.add('thread-a','turn','request','A',time.time()+60)
        b=self.store.add('thread-b','turn','request','B',time.time()+60)
        self.store.set_question(a['id'],'ANSWERED','choice A')
        self.assertEqual(self.store.pending()[0]['id'],b['id']);self.store.recover()
        self.assertEqual(self.store.db.execute('SELECT status FROM questions WHERE id=?',(a['id'],)).fetchone()[0],'ANSWERED')
    def test_only_personal_provider_uri(self):
        self.assertEqual(validate_uri('sip:sample-user@sip.linphone.org'),'sip:sample-user@sip.linphone.org')
        for uri in ('tel:+41000000000','sip:someone@evil.example','sip:abc@sip.linphone.org;transport=udp','sip:abc@sip.linphone.org\n/quit','sip:$(id)@sip.linphone.org'):
            with self.assertRaises(ValueError):validate_uri(uri)

class Routing(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();os.environ['CODEX_PHONE_HOME']=self.tmp.name
        self.b=Bridge();self.sent=[]
        class Client:
            async def send(inner,obj):self.sent.append(obj)
        self.b.codex=Client()
    async def asyncTearDown(self):self.b.store.db.close();os.environ.pop('CODEX_PHONE_HOME');self.tmp.cleanup()
    def question(self):
        q=self.b.store.add('thread','turn','rpc','Question',time.time()+60)
        self.b.questions[q['id']]={'rpc_id':'rpc','thread':'thread','turn':'turn','live':True,'delivered':False}
        self.b.turns['thread']={'id':'turn','status':'inProgress'}
        return q
    async def test_exact_turn_and_single_delivery(self):
        q=self.question();await self.b.deliver(q['id'],'Keep desktop')
        self.assertEqual(self.sent[0]['id'],'rpc')
        with self.assertRaises(RuntimeError):await self.b.deliver(q['id'],'Duplicate')
        await self.b.event({'method':'turn/completed','params':{'threadId':'thread','turn':{'id':'turn','status':'completed'}}})
        self.assertEqual(self.b.store.db.execute('SELECT status FROM questions').fetchone()[0],'ANSWERED')
    async def test_wrong_turn_refused(self):
        q=self.question();self.b.turns['thread']['id']='different-turn'
        with self.assertRaises(RuntimeError):await self.b.deliver(q['id'],'Answer')
        self.assertEqual(self.sent,[])
    async def test_resolved_request_refused(self):
        q=self.question();await self.b.event({'method':'serverRequest/resolved','params':{'threadId':'thread','requestId':'rpc'}})
        with self.assertRaises(RuntimeError):await self.b.deliver(q['id'],'Late')
    async def test_approval_never_enters_phone_queue(self):
        await self.b.request({'method':'item/permissions/requestApproval','id':4,'params':{'threadId':'thread','turnId':'turn','permissions':{'network':{'enabled':True}}}})
        self.assertEqual(self.b.store.pending(),[]);self.assertIn('4',self.b.approvals);self.assertEqual(self.sent,[])
    async def test_concurrent_retries_are_bounded(self):
        q=self.question()
        results=await asyncio.gather(*(self.b.call(q) for _ in range(4)))
        count=self.b.store.db.execute('SELECT COUNT(*) FROM calls WHERE question_id=?',(q['id'],)).fetchone()[0]
        self.assertEqual(count,2)
        self.assertEqual(sum(r.get('reason')=='retry_limit' for r in results),2)
        self.assertEqual(self.b.store.pending()[0]['id'],q['id'])
    async def test_malformed_netstring(self):
        for data in (b'x:abc,',b'2:{};',b'2000000:'):
            r=asyncio.StreamReader();r.feed_data(data);r.feed_eof()
            with self.assertRaises((ValueError,asyncio.IncompleteReadError)):await netstring(r)
    async def test_valid_fragmented_netstring(self):
        r=asyncio.StreamReader()
        for b in (b'7:',b'{"a":',b'1},'):r.feed_data(b)
        self.assertEqual(await netstring(r),{'a':1})

class Registration(unittest.IsolatedAsyncioTestCase):
    async def check(self, data):
        # Contract fixture only: this does not register a real provider account.
        sip=Sip.__new__(Sip)
        sip.proc=SimpleNamespace(returncode=None)
        sip.disconnected=asyncio.Event()
        async def command(name):return {'data':data}
        sip.command=command
        return await sip.wait_registered(timeout=.01)
    async def test_live_status_with_ansi(self):
        result=await self.check('0 - sip:owner@provider.invalid   \x1b[32mOK \x1b[;m server.invalid:5061 Expires 600s')
        self.assertEqual(result['status'],'REGISTERED')
    async def test_username_ok_is_not_registration(self):
        with self.assertRaises(RuntimeError):await self.check('0 - sip:OK_user@provider.invalid   zzz server.invalid')
    async def test_multiword_provider_status(self):
        result=await self.check('0 - sip:owner@provider.invalid OK Flexisip/2.6 (sofia-sip-nta/2.0) Expires 600s')
        self.assertEqual(result['status'],'REGISTERED')
    async def test_rejection_redacts_raw_account(self):
        with self.assertRaises(RuntimeError) as ctx:await self.check('0 - sip:private@provider.invalid ERR server.invalid')
        self.assertNotIn('private',str(ctx.exception));self.assertNotIn('provider.invalid',str(ctx.exception))
    async def test_expired_registration_is_not_success(self):
        with self.assertRaises(RuntimeError):await self.check('0 - sip:owner@provider.invalid OK server.invalid Expires 0s')
if __name__=='__main__':unittest.main()
