"""Local newline-delimited JSON-RPC MCP adapter; no provider SDK or credentials.

Each tools/call owns one private daemon connection. Cancellation/EOF closes that
connection, cancelling its call. Stdout contains protocol messages only.
"""
import asyncio
import json
import sys
from .storage import ROOT, home, config
from .readiness import call_readiness

INSTRUCTIONS = ('When the user asks to be called, use phone_call immediately after phone_status, without asking for a reason. The topic may be given during the call. Use phone_decision when a product/design choice genuinely blocks the current task. '
                'For phone_decision, ask one concrete question with enough context and options. Act on that decision '
                'only after confirmed=true. Open calls return completed, never a confirmed decision. Never use voice for shell, file, network, sandbox or '
                'account authorization. On failure keep the decision unresolved; do not guess or '
                'retry automatically. phone_status checks availability without calling.')
TOOLS = [
    {'name':'phone_call','description':'Call the owner now for an open conversation when explicitly requested. No reason, topic or decision is required. Uses the configured personal destination; voice cannot authorize security-sensitive actions.',
     'inputSchema':{'type':'object','properties':{},'additionalProperties':False}},
    {'name':'phone_decision','description':INSTRUCTIONS,
     'inputSchema':{'type':'object','properties':{
         'kind':{'type':'string','enum':['product','design']},
         'question':{'type':'string','minLength':1,'maxLength':2000}},
         'required':['kind','question'],'additionalProperties':False}},
    {'name':'phone_status','description':'Check budget and preflight readiness without calling; provider balance and iPhone delivery may remain unknown.',
     'inputSchema':{'type':'object','properties':{},'additionalProperties':False},
     'annotations':{'readOnlyHint':True}},
]

async def daemon(message):
    socket = str(home()/'control.sock')
    try:
        reader, writer = await asyncio.open_unix_connection(socket)
    except (FileNotFoundError, ConnectionRefusedError):
        # Recover only before sending: never replay a potentially delivered call.
        proc = await asyncio.create_subprocess_exec(
            sys.executable, str(ROOT/'bin/codex-phone'), 'start',
            stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL)
        try:
            code = await asyncio.wait_for(proc.wait(), 10)
        except asyncio.TimeoutError:
            proc.kill(); await proc.wait()
            raise RuntimeError('Bridge startup timed out; no call sent')
        except asyncio.CancelledError:
            if proc.returncode is None:
                proc.kill()
            await proc.wait()
            raise
        if code:
            raise RuntimeError('Bridge startup failed; inspect private daemon.log')
        reader, writer = await asyncio.open_unix_connection(socket)
    try:
        writer.write(json.dumps(message).encode()+b'\n')
        await writer.drain()
        line=await asyncio.wait_for(reader.readline(),650)
        if not line:raise RuntimeError('Bridge stopped before returning a confirmed decision')
        response=json.loads(line)
        if 'error' in response:raise RuntimeError(response['error'])
        return response['result']
    finally:
        writer.close()
        await writer.wait_closed()

async def tool(name, arguments):
    if not isinstance(arguments,dict):raise ValueError('Invalid tool arguments')
    if name=='phone_call' and not arguments:
        result=await daemon({'op':'phone-call'})
        return {key:value for key,value in result.items() if key in ('completed','status','reason','call_id','metrics')}
    if name=='phone_decision':
        if set(arguments)!={'kind','question'}:raise ValueError('Invalid decision fields')
        if arguments['kind'] not in ('product','design') or not isinstance(arguments['question'],str) or not 1<=len(arguments['question'])<=2000:
            raise ValueError('Only bounded product/design questions are accepted')
        result=await daemon(dict(op='phone-decision',**arguments))
        if result.get('confirmed') is not True:
            return {'confirmed':False,'status':result.get('status','FAILED'),
                    'reason':result.get('reason','No confirmed answer'),
                    'instruction':'Decision remains unresolved. Do not guess or retry automatically.'}
        return {'confirmed':True,'decision':result['decision'],'source':'confirmed_cloud_sip_speech'}
    if name=='phone_status' and not arguments:
        result=await daemon({'op':'status'})
        return {'bridge':result['call_state'], **call_readiness(config(), result['call_state'])}
    raise ValueError('Unknown tool or invalid arguments')

async def serve():
    tasks={}
    def send(message):
        print(json.dumps(message),flush=True)
    async def dispatch(request):
        identity=request.get('id')
        try:
            method=request['method'];params=request.get('params',{})
            if method=='initialize':
                version=params.get('protocolVersion','2024-11-05')
                if version not in ('2024-11-05','2025-03-26','2025-06-18','2025-11-25'):version='2024-11-05'
                result={'protocolVersion':version,'capabilities':{'tools':{}},
                        'serverInfo':{'name':'codex-phone-bridge','version':'0.3.0'},'instructions':INSTRUCTIONS}
            elif method=='ping':result={}
            elif method=='tools/list':result={'tools':TOOLS}
            elif method=='tools/call':
                try:
                    value=await tool(params.get('name'),params.get('arguments',{}))
                    result={'content':[{'type':'text','text':json.dumps(value)}],
                            'isError':value.get('confirmed') is False}
                except (RuntimeError,ValueError,OSError,asyncio.TimeoutError) as exc:
                    result={'content':[{'type':'text','text':json.dumps({'confirmed':False,
                            'reason':str(exc) if isinstance(exc,(ValueError,RuntimeError)) else type(exc).__name__})}], 'isError':True}
            else:
                send({'jsonrpc':'2.0','id':identity,'error':{'code':-32601,'message':'Method not found'}});return
            send({'jsonrpc':'2.0','id':identity,'result':result})
        except asyncio.CancelledError:
            send({'jsonrpc':'2.0','id':identity,'error':{'code':-32800,'message':'Request cancelled'}})
        except Exception:
            send({'jsonrpc':'2.0','id':identity,'error':{'code':-32602,'message':'Invalid request'}})
    try:
        while True:
            line=await asyncio.to_thread(sys.stdin.buffer.readline,65537)
            if not line:break
            try:
                if len(line)>65536:raise ValueError()
                request=json.loads(line)
                if not isinstance(request,dict) or request.get('jsonrpc')!='2.0':raise ValueError()
                if request.get('method')=='notifications/cancelled':
                    task=tasks.get(request.get('params',{}).get('requestId'))
                    if task:task.cancel()
                    continue
                if 'id' not in request:continue
                identity=request['id']
                if identity in tasks:
                    send({'jsonrpc':'2.0','id':identity,'error':{'code':-32600,'message':'Duplicate request id'}});continue
                task=asyncio.create_task(dispatch(request));tasks[identity]=task
                task.add_done_callback(lambda _, key=identity:tasks.pop(key,None))
            except (ValueError,TypeError):
                send({'jsonrpc':'2.0','id':None,'error':{'code':-32700,'message':'Invalid JSON-RPC input'}})
    finally:
        pending=list(tasks.values())
        for task in pending:task.cancel()
        await asyncio.gather(*pending,return_exceptions=True)

def main():
    asyncio.run(serve())
