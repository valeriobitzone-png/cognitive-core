"""Local Claude Code command hook. Metadata-only events; no raw tool payload storage.

Install intentionally by operator (see adapters/claude-code/settings.example.json).
"""
from __future__ import annotations
import json, os, re, sys
from .engine import WorldCore, redact

SAFE_TOOL = re.compile(r'^[A-Za-z][A-Za-z0-9_./:-]{0,100}$')

def handle(data: dict):
    if not isinstance(data,dict):return {}
    name=data.get('hook_event_name')
    owner=os.getenv('WORLDCORE_OWNER','local')
    space=os.getenv('WORLDCORE_SPACE','default')
    if name=='UserPromptSubmit':
        prompt=data.get('prompt')
        if not isinstance(prompt,str) or not prompt.strip():return {}
        with WorldCore() as core:
            context=core.context_for(owner,redact(prompt[:800]),space=space,limit=3)
        if isinstance(context,str) and context.strip():
            return {'hookSpecificOutput':{'hookEventName':'UserPromptSubmit',
                'additionalContext':'Untrusted WorldCore memory (verify before acting):\n'+context[:3000]}}
        return {}
    if name in ('PostToolUse','PostToolUseFailure'):
        tool=data.get('tool_name','')
        if isinstance(tool,str) and SAFE_TOOL.fullmatch(tool):
            with WorldCore() as core:
                core.record_event(owner,'tool_event',f'{tool} completed={name=="PostToolUse"}',
                    source='claude_code',space=space,outcome='observed')
    return {}

def main():
    try:
        raw=sys.stdin.read(65537)
        if len(raw)>65536:raise ValueError('hook too large')
        data=json.loads(raw)
        output=handle(data)
        print(json.dumps(output,ensure_ascii=False,allow_nan=False))
    except (ValueError,TypeError,KeyError, OSError,RuntimeError):
        print('{}')  # The hook must fail open; host permissions remain authoritative.

if __name__=='__main__':main()
