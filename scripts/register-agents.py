#!/usr/bin/env python3
"""Register only this MCP entry; preserve unrelated user settings.

Run with the optional voice environment's Python 3.12 (tomllib is stdlib).
No secrets or blanket tool approvals are added; only the three phone tools
are preapproved in Codex, as authorized by the bridge integration request.
"""
import json
from pathlib import Path
import re
import subprocess
import tomllib

root=Path(__file__).resolve().parents[1]
entry=str(root/'bin/codex-phone-mcp')
name='codex-phone'
codex_path=Path.home()/'.codex/config.toml'
copilot_path=Path.home()/'.copilot/mcp-config.json'
originals={p:p.read_bytes() if p.exists() else None for p in (codex_path,copilot_path)}
before_codex=tomllib.loads((originals[codex_path] or b'').decode())
before_copilot=json.loads(originals[copilot_path] or '{}')
for value in (before_codex.get('mcp_servers',{}).get(name),before_copilot.get('mcpServers',{}).get(name)):
    if value and (value.get('command')!=entry or value.get('args',[])):
        raise SystemExit('Conflicting codex-phone entry; no settings changed')
try:
    text=codex_path.read_text() if codex_path.exists() else ''
    if name not in before_codex.get('mcp_servers',{}):
        text+='\n[mcp_servers.codex-phone]\ncommand = '+json.dumps(entry)+'\nargs = []\ntool_timeout_sec = 900\n'
    else:
        pattern=r'(\[mcp_servers\.codex-phone\]\n)(.*?)(?=^\[|\Z)'
        def timeout(match):
            body=re.sub(r'^tool_timeout_sec\s*=.*\n','',match[2],flags=re.M)
            return match[1]+'tool_timeout_sec = 900\n'+body
        text,count=re.subn(pattern,timeout,text,flags=re.M|re.S)
        if count!=1:raise RuntimeError('Cannot safely locate the existing Codex MCP entry')
    header='[mcp_servers.codex-phone]\n'
    for tool in ('phone_call','phone_decision','phone_status'):
        line=f'tools.{tool}.approval_mode = "approve"\n'
        existing_tools=before_codex.get('mcp_servers',{}).get(name,{}).get('tools',{})
        if tool not in existing_tools:text=text.replace(header,header+line,1)
    codex_path.write_text(text)
    if name not in before_copilot.get('mcpServers',{}):
        subprocess.run(['copilot','mcp','add',name,'--timeout','900000','--',entry],
                       check=True,stdout=subprocess.DEVNULL)
    after_codex=tomllib.loads(codex_path.read_text())
    after_copilot=json.loads(copilot_path.read_text())
    for before,after,key in ((before_codex,after_codex,'mcp_servers'),(before_copilot,after_copilot,'mcpServers')):
        before=json.loads(json.dumps(before,default=str));after=json.loads(json.dumps(after,default=str))
        before.get(key,{}).pop(name,None);after.get(key,{}).pop(name,None)
        if not before.get(key):before.pop(key,None)
        if not after.get(key):after.pop(key,None)
        if before!=after:
            def paths(a,b,prefix=''):
                found=[]
                for k in set(a)|set(b):
                    if a.get(k)!=b.get(k):
                        if isinstance(a.get(k),dict) and isinstance(b.get(k),dict):found.extend(paths(a[k],b[k],prefix+k+'.'))
                        else:found.append(prefix+k)
                return found
            changed=paths(before,after)
            raise RuntimeError('Unrelated settings changed at keys: '+','.join(changed))
except BaseException:
    for path,original in originals.items():
        if original is not None:path.write_bytes(original)
        elif path.exists():path.unlink()
    raise
print('Registered codex-phone for Codex and Copilot CLI; unrelated settings preserved.')
print('Restart existing agent sessions to discover the new tools. Only phone_call/phone_decision/phone_status are preapproved in Codex; all security approvals remain separate.')

policy=(root/'docs/AGENT-POLICY.md').read_text()
for path in (Path.home()/'.codex/AGENTS.md',Path.home()/'.copilot/copilot-instructions.md'):
    text=path.read_text() if path.exists() else ''
    if '<!-- codex-phone-bridge:start -->' in text:
        updated,count=re.subn(r'<!-- codex-phone-bridge:start -->.*?<!-- codex-phone-bridge:end -->', lambda _:policy.strip(), text, flags=re.S)
        if count!=1:raise RuntimeError('Ambiguous phone policy markers')
        path.write_text(updated)
    else:
        path.write_text(text+'\n'+policy)
print('Phone decision policy present in both personal instruction files.')
