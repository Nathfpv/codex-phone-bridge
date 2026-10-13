#!/usr/bin/env python3
"""Real Codex inference plus local text answer; explicitly not a phone E2E test."""
import asyncio
import json
import os
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from codex_phone.storage import ROOT
from codex_phone.bridge import Bridge
from codex_phone.codex import Codex

async def main():
    scratch=ROOT/'.local/codex-proof';scratch.mkdir(parents=True,exist_ok=True)
    os.environ['CODEX_PHONE_HOME']=str(scratch/'runtime')
    work=scratch/str(int(time.time()));work.mkdir()
    b=Bridge();b.codex=Codex(b.request,b.event)
    try:
        await b.codex.start()
        result=await b.command({'op':'launch','cwd':str(work),'prompt':
            'Create decision.txt for a navigation change. You MUST first use phone_decision with kind design to ask whether mobile navigation should be simplified while desktop remains unchanged. Wait for the answer, then write decision.txt with the confirmed decision. Do not choose before the response.'})
        print(json.dumps({'launched':result}))
        deadline=time.monotonic()+90;q=None
        while time.monotonic()<deadline:
            q=next((q for q in b.store.pending() if q['session_id']==result['thread_id']),None)
            if q:break
            if b.turns.get(result['thread_id'],{}).get('status') in ('completed','failed'):raise RuntimeError('Task ended before required question')
            await asyncio.sleep(.2)
        if not q:raise RuntimeError('No real dynamic decision received')
        assert q['turn_id']==result['turn_id']
        # Wait for the automatic call attempt to fail on deliberately absent test config.
        await asyncio.gather(*b.call_tasks)
        print(json.dumps({'real_question':q['id'],'thread':q['session_id'],'turn':q['turn_id'],'call':'BLOCKED_BY_USER: no accounts in isolated test runtime'}))
        await b.deliver(q['id'],'Vereinfache die mobile Navigation, aber lass Desktop unverändert. Local text integration test, not a phone transcript.')
        while time.monotonic()<deadline:
            state=b.turns.get(result['thread_id'],{})
            if state.get('status')=='completed':break
            if state.get('status') in ('failed','interrupted'):raise RuntimeError('Codex turn failed')
            await asyncio.sleep(.2)
        else:raise RuntimeError('Codex continuation timed out')
        text=(work/'decision.txt').read_text()
        if not ('desktop' in text.lower() and ('mobile' in text.lower() or 'mobil' in text.lower())):raise RuntimeError('Task output mismatched decision')
        row=b.store.db.execute('SELECT status FROM questions WHERE id=?',(q['id'],)).fetchone()
        if row[0]!='ANSWERED':raise RuntimeError('Delivered answer was incorrectly orphaned')
        print('PASS: real Codex dynamic request, exact original thread/turn, local text response, same task file creation. Phone NOT_TESTED.')
    finally:
        for task in b.call_tasks:task.cancel()
        await asyncio.gather(*b.call_tasks,return_exceptions=True)
        await b.codex.close();b.store.db.close()
asyncio.run(main())
