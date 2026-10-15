"""MCP protocol/routing fixtures, never a real phone/cloud acceptance test."""
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, AsyncMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from codex_phone.mcp_server import tool
from codex_phone.bridge import Bridge
from codex_phone.storage import Store

class Decisions(unittest.IsolatedAsyncioTestCase):
    async def test_failure_never_becomes_decision(self):
        with patch('codex_phone.mcp_server.daemon',AsyncMock(return_value={'status':'FAILED','reason':'limit'})):
            value=await tool('phone_decision',{'kind':'design','question':'Which layout?'})
        self.assertFalse(value['confirmed'])
        self.assertNotIn('decision',value)

    async def test_only_explicit_confirmed_result_returned(self):
        with patch('codex_phone.mcp_server.daemon',AsyncMock(return_value={'confirmed':True,'decision':'A'})):
            self.assertEqual((await tool('phone_decision',{'kind':'product','question':'A or B?'}))['decision'],'A')
        with self.assertRaises(ValueError):
            await tool('phone_decision',{'kind':'approval','question':'Allow shell?'})
        with self.assertRaises(ValueError):
            await tool('phone_decision',{'kind':'design','question':'A?','thread_id':'other'})

    async def test_external_identities_are_separate_and_not_model_supplied(self):
        with tempfile.TemporaryDirectory() as directory:
            bridge=Bridge.__new__(Bridge);bridge.store=Store(Path(directory)/'state.sqlite3')
            rows=[]
            async def call(row,external=False):
                self.assertTrue(external);rows.append(row)
                return {'confirmed':True,'decision':row['question']}
            bridge.call=call
            results=await asyncio.gather(*(bridge.command({'op':'phone-decision','kind':'design',
                         'question':text,'thread_id':'forged'}) for text in ('A','B')))
            self.assertEqual([r['decision'] for r in results],['A','B'])
            self.assertNotEqual(rows[0]['session_id'],rows[1]['session_id'])
            self.assertTrue(all(row['session_id'].startswith('mcp:') for row in rows))
            bridge.store.db.close()

    async def test_disconnect_cancels_only_its_operation(self):
        bridge=Bridge.__new__(Bridge);bridge.call_tasks=set()
        started=asyncio.Event();cancelled=asyncio.Event()
        async def command(message):
            started.set()
            try:await asyncio.Future()
            finally:cancelled.set()
        bridge.command=command
        with tempfile.TemporaryDirectory() as directory:
            server=await asyncio.start_unix_server(bridge.client,str(Path(directory)/'sock'))
            reader,writer=await asyncio.open_unix_connection(str(Path(directory)/'sock'))
            writer.write(b'{"op":"phone-decision"}\n');await writer.drain()
            await asyncio.wait_for(started.wait(),1)
            writer.close();await writer.wait_closed()
            await asyncio.wait_for(cancelled.wait(),1)
            server.close();await server.wait_closed()

    async def test_confirmed_external_call_returns_to_invoker_without_codex_rpc(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            bridge=Bridge.__new__(Bridge);bridge.store=Store(Path(directory)/'state.sqlite3')
            bridge.lock=asyncio.Lock();bridge.questions={};bridge.log=lambda *a,**k:None
            bridge.deliver=AsyncMock()
            sip=SimpleNamespace(start=AsyncMock(),dial=AsyncMock(),close=AsyncMock(),
                event=AsyncMock(return_value={'type':'CALL_ESTABLISHED','direction':'outgoing',
                                             'peeruri':'sip:device@example.invalid'}))
            prepared=SimpleNamespace(options={},close=AsyncMock())
            with patch('codex_phone.bridge.config',return_value={'voice_backend':'livekit',
                        'iphone_uri':'sip:device@example.invalid'}), \
                 patch('codex_phone.bridge.Sip',return_value=sip), \
                 patch('codex_phone.bridge.prepare_voice',AsyncMock(return_value=prepared)), \
                 patch('codex_phone.bridge.converse',AsyncMock(return_value=('Option A',{}))):
                answer=await bridge.command({'op':'phone-decision','kind':'design','question':'A or B?'})
            self.assertEqual(answer['decision'],'Option A');self.assertTrue(answer['confirmed'])
            bridge.deliver.assert_not_awaited()
            self.assertEqual(bridge.store.db.execute('SELECT status FROM questions').fetchone()[0],'ANSWERED')
            sip.close.assert_awaited_once();prepared.close.assert_awaited_once()
            bridge.store.db.close()

    @unittest.skipIf(sys.version_info < (3,11), "Registration helpers require the Python 3.12 voice environment")
    async def test_unregister_preserves_other_servers_and_instructions(self):
        import runpy
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            home=Path(directory);(home/'.codex').mkdir();(home/'.copilot').mkdir()
            entry=str(root/'bin/codex-phone-mcp')
            codex=home/'.codex/config.toml'
            codex.write_text('[mcp_servers.other]\ncommand="keep"\n\n[mcp_servers.codex-phone]\ncommand='+json.dumps(entry)+'\n')
            copilot=home/'.copilot/mcp-config.json'
            copilot.write_text(json.dumps({'mcpServers':{'other':{'command':'keep'},'codex-phone':{'command':entry}}}))
            policy='keep instructions\n'+(root/'docs/AGENT-POLICY.md').read_text()
            for p in (home/'.codex/AGENTS.md',home/'.copilot/copilot-instructions.md'):p.write_text(policy)
            with patch('pathlib.Path.home',return_value=home):
                runpy.run_path(str(root/'scripts/unregister-agents.py'))
            self.assertIn('command="keep"',codex.read_text());self.assertNotIn('codex-phone',codex.read_text())
            self.assertEqual(set(json.loads(copilot.read_text())['mcpServers']),{'other'})
            self.assertEqual((home/'.codex/AGENTS.md').read_text().strip(),'keep instructions')

    async def test_real_stdio_discovery_has_no_phone_side_effect(self):
        root=Path(__file__).resolve().parents[1]
        process=await asyncio.create_subprocess_exec(sys.executable,str(root/'bin/codex-phone-mcp'),
                          stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE)
        try:
            for identity,method in ((1,'initialize'),(2,'tools/list')):
                process.stdin.write((json.dumps({'jsonrpc':'2.0','id':identity,'method':method,
                                      'params':{'protocolVersion':'2025-06-18'}})+'\n').encode())
                await process.stdin.drain()
                response=json.loads(await asyncio.wait_for(process.stdout.readline(),2))
                self.assertEqual(response['id'],identity)
            self.assertEqual({item['name'] for item in response['result']['tools']},
                             {'phone_decision','phone_status'})
        finally:
            process.stdin.close();await asyncio.wait_for(process.wait(),2)
