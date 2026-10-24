"""Real SDK session/plugin boundary; model fixture otherwise keeps chatting."""
import asyncio
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
try:
    from livekit.agents import AgentSession, function_tool
    from livekit.plugins import openai
    from codex_phone.decision_agent import DecisionAgent
    from codex_phone.voice_decision import Decision
    from codex_phone.call_control import CallController
    from codex_phone.voice_session import attach_controller
    VOICE_SDK=True
except ImportError:
    VOICE_SDK=False


@unittest.skipUnless(VOICE_SDK,'Requires the installed voice environment')
class ProposalHandoff(unittest.IsolatedAsyncioTestCase):
    async def exercise(self, message, *, existing_proposal=False, control=None):
        requests=[]
        async def serve(reader,writer):
            header=await reader.readuntil(b'\r\n\r\n')
            if not header.startswith(b'POST '):
                writer.write(b'HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n')
                await writer.drain();writer.close();await writer.wait_closed()
                return
            lengths=[line.split(b':',1)[1] for line in header.split(b'\r\n')
                     if line.lower().startswith(b'content-length:')]
            if lengths:
                data=await reader.readexactly(int(lengths[0]))
            else:
                chunks=[]
                while True:
                    size=int((await reader.readline()).strip(),16)
                    if not size:
                        await reader.readline()
                        break
                    chunks.append(await reader.readexactly(size))
                    await reader.readexactly(2)
                data=b''.join(chunks)
            body=json.loads(data);requests.append(body)
            forced=body.get('tool_choice')=={'type':'function','function':{'name':'propose_decision'}}
            delta=({'tool_calls':[{'index':0,'id':'proposal-call','type':'function',
                       'function':{'name':'propose_decision','arguments':'{"answer":"Normales Hochdeutsch und kurze Antworten."}'}}]}
                    if forced else {'content':'Möchtest du noch etwas besprechen?'})
            events=[{'id':'test','object':'chat.completion.chunk','model':'test',
                     'choices':[{'index':0,'delta':delta,'finish_reason':None}]},
                    {'id':'test','object':'chat.completion.chunk','model':'test',
                     'choices':[{'index':0,'delta':{},'finish_reason':'tool_calls' if forced else 'stop'}]}]
            data=''.join('data: '+json.dumps(event)+'\n\n' for event in events)+'data: [DONE]\n\n'
            writer.write(('HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nContent-Length: '+
                          str(len(data.encode()))+'\r\n\r\n'+data).encode())
            await writer.drain();writer.close();await writer.wait_closed()
        server=await asyncio.start_server(serve,'127.0.0.1',0)
        model=openai.LLM(model='test',base_url=f'http://127.0.0.1:{server.sockets[0].getsockname()[1]}/v1',
                         api_key='offline',parallel_tool_calls=False,max_retries=0)
        decision=Decision()
        if existing_proposal:decision.propose('Vorheriger Vorschlag')
        proposed=[]
        @function_tool
        async def propose_decision(answer:str):
            """Prepare a proposal, never a confirmation."""
            proposed.append(decision.propose(answer))
            return {'proposal':answer,'next':'Read back before a new confirmation.'}
        session=AgentSession(llm=model)
        if control is not None:
            attach_controller(session, control)
        try:
            agent=DecisionAgent(decision=decision,instructions='Besprich die Entscheidung.',tools=[propose_decision])
            await session.start(agent=agent,record=False)
            await session.generate_reply(user_input=message)
            return requests,proposed,decision
        finally:
            await session.aclose();await model.aclose();server.close();await server.wait_closed()

    async def test_clear_yes_does_not_force_a_proposal_without_context(self):
        requests, proposed, decision = await self.exercise('Ja, wir schicken ab.')
        self.assertTrue(requests)
        self.assertFalse(proposed)
        self.assertNotEqual(requests[0].get('tool_choice'),
                            {'type':'function','function':{'name':'propose_decision'}})
        self.assertIsNone(decision.read_back_at)

    async def test_new_generated_speech_invalidates_late_readback_callback(self):
        control = CallController()
        control.decision.propose('Old')
        version = control.decision.version
        await self.exercise('A different question', control=control)
        self.assertFalse(control.decision.read_back(version, ended_at=1.))
        control.speech_started(); control.user_turn('new', 'Ja')
        control.tick(); self.assertIsNone(control.outcome)

    async def test_qualified_yes_or_question_does_not_force_a_proposal(self):
        for message in ('Ja, aber Desktop auch ändern.', 'Ja?', 'Nein, bitte noch warten.'):
            with self.subTest(message=message):
                requests, proposed, _ = await self.exercise(message)
                self.assertTrue(requests)
                self.assertFalse(proposed)
                self.assertNotEqual(requests[0].get('tool_choice'),
                    {'type':'function','function':{'name':'propose_decision'}})

    async def test_existing_proposal_is_not_replaced_by_an_affirmation(self):
        requests, proposed, decision = await self.exercise('Ja, wir schicken ab.', existing_proposal=True)
        self.assertTrue(requests)
        self.assertFalse(proposed)
        self.assertEqual(decision.proposal, 'Vorheriger Vorschlag')
        self.assertNotEqual(requests[0].get('tool_choice'),
            {'type':'function','function':{'name':'propose_decision'}})
