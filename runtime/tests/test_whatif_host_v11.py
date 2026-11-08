import json
import os
import subprocess
import sys
import types
from worldcore import WorldCore
from worldcore.bridge import dispatch
from worldcore.mcp_server import create_server


def test_whatif_bridge_parity(tmp_path):
    with WorldCore(tmp_path/'bridge.db') as w:
        w.set_state('trusted','budget',100)
        base={'owner':'trusted','space':'private','question':'What if the budget goes down?',
              'target':{'budget':{'op':'<=','value':80}},
              'candidate_actions':[{'op':'add','key':'budget','value':-10}],
              'max_depth':2}
        w.set_state('trusted','budget',100,space='private')
        result=dispatch({'op':'whatif_backcast',**base},w)
        assert result['plan']['steps']==2
        assert w.state('trusted',space='private')['budget']==100
        cmp=dispatch({'op':'whatif_compare','owner':'trusted','space':'private',
             'question':'Alternatives','objectives':[],
             'scenarios':[{'id':'A','actions':result['plan']['actions']},{'id':'B','actions':[]}]},w)
        assert dispatch({'op':'whatif_replay','owner':'trusted','space':'private','run_id':cmp['run_id']},w)['status']=='unresolved'
        assert not result['action_executed']


def test_whatif_mcp_tools_are_read_only(monkeypatch,tmp_path):
    class FakeMCP:
        def __init__(self,*args,**kwargs):self.tools={}
        def tool(self):
            def deco(fn):self.tools[fn.__name__]=fn;return fn
            return deco
    fake=types.ModuleType('mcp');server=types.ModuleType('mcp.server');fast=types.ModuleType('mcp.server.fastmcp');fast.FastMCP=FakeMCP
    monkeypatch.setitem(sys.modules,'mcp',fake)
    monkeypatch.setitem(sys.modules,'mcp.server',server)
    monkeypatch.setitem(sys.modules,'mcp.server.fastmcp',fast)
    monkeypatch.setenv('WORLDCORE_DB',str(tmp_path/'mcp.db'))
    monkeypatch.setenv('WORLDCORE_OWNER','trusted')
    mcp=create_server()
    assert {'whatif_compare','whatif_backcast','whatif_replay','whatif_verify'} <= set(mcp.tools)
    with WorldCore(tmp_path/'mcp.db') as w:w.set_state('trusted','cost',90)
    res=mcp.tools['whatif_backcast']('Cost reduction',{'cost':{'op':'<=','value':80}},
             [{'op':'add','key':'cost','value':-10}])
    assert res['status']=='assumed_plan_found'
    with WorldCore(tmp_path/'mcp.db') as w:assert w.state('trusted')['cost']==90


def test_claude_hook_executable_stdio_is_observational(monkeypatch,tmp_path):
    db=str(tmp_path/'claude.db')
    with WorldCore(db) as w:w.remember('claude','task','Test planning',source='operator')
    env=dict(os.environ,WORLDCORE_DB=db,WORLDCORE_OWNER='claude')
    ok=subprocess.run([sys.executable,'-m','worldcore.claude_hook'],env=env,
           input=json.dumps({'hook_event_name':'UserPromptSubmit','prompt':'task'}),
           capture_output=True,text=True,timeout=10)
    assert ok.returncode==0
    out=json.loads(ok.stdout)
    assert 'Test planning' in out['hookSpecificOutput']['additionalContext']
    event=subprocess.run([sys.executable,'-m','worldcore.claude_hook'],env=env,
           input=json.dumps({'hook_event_name':'PostToolUse','tool_name':'Bash',
              'tool_input':{'command':'SECRET_PRIVATE_PAYLOAD'}}),
           capture_output=True,text=True,timeout=10)
    assert event.returncode==0
    with WorldCore(db) as w:
        events=w.events('claude')
        assert len(events)==1
        assert 'Bash' in events[0]['summary']
        assert 'PRIVATE_PAYLOAD' not in str(events)
