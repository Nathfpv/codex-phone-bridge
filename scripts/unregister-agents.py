#!/usr/bin/env python3
"""Remove only this project's MCP entries and marked personal policy blocks."""
import json
from pathlib import Path
import re
import tomllib
root=Path(__file__).resolve().parents[1]
entry=str(root/'bin/codex-phone-mcp')
path=Path.home()/'.codex/config.toml'
if path.exists():
    text=path.read_text();value=tomllib.loads(text).get('mcp_servers',{}).get('codex-phone')
    if value:
        if value.get('command')!=entry:raise SystemExit('Conflicting Codex entry; left unchanged')
        text=re.sub(r'^\[mcp_servers\.codex-phone(?:\.[^\]]+)?\]\n.*?(?=^\[|\Z)','',text,flags=re.M|re.S)
        tomllib.loads(text)
        path.write_text(text)
path=Path.home()/'.copilot/mcp-config.json'
if path.exists():
    value=json.loads(path.read_text());server=value.get('mcpServers',{}).get('codex-phone')
    if server:
        if server.get('command')!=entry:raise SystemExit('Conflicting Copilot entry; left unchanged')
        del value['mcpServers']['codex-phone']
        path.write_text(json.dumps(value,indent=2)+'\n')
for path in (Path.home()/'.codex/AGENTS.md',Path.home()/'.copilot/copilot-instructions.md'):
    if path.exists():
        text=re.sub(r'\n?<!-- codex-phone-bridge:start -->.*?<!-- codex-phone-bridge:end -->\n?',
                    '',path.read_text(),flags=re.S)
        path.write_text(text)
print('Removed this project’s MCP entries and marked policy blocks; restart agent sessions.')
