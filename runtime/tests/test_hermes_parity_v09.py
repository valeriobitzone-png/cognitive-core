"""Hermes contract tests mirror the OpenClaw checks, using a simulated host.
NOT a real Hermes deployment, and mock LLM is not a production LLM.
"""
import importlib.util,os,sqlite3
from pathlib import Path
from types import SimpleNamespace
from worldcore import WorldCore

PATH=Path(__file__).resolve().parents[1]/'adapters'/'hermes'/'worldcore'/'__init__.py'

def harness():
    spec=importlib.util.spec_from_file_location('worldcore_hermes_v09',PATH)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    hooks={}
    class Host:
        def register_hook(self,name,fn):hooks[name]=fn
    module.register(Host())
    return module,hooks

def test_hermes_plugin_hook_registration():
    _,hooks=harness()
    assert {'pre_llm_call','post_tool_call'}==set(hooks)

def test_hermes_context_works_with_full_documented_signature(tmp_path,monkeypatch):
    monkeypatch.setenv('WORLDCORE_DB',str(tmp_path/'hermes.db'))
    with WorldCore(tmp_path/'hermes.db') as core:
        core.remember('local','project.motto','prediction before action')
    _,hooks=harness()
    result=hooks['pre_llm_call'](session_id='sess',task_id='task',turn_id='turn',user_message='project motto',
      conversation_history=[],is_first_turn=True,model='host-model',platform='cli',sender_id='demo')
    assert result and 'prediction before action' in result['context']

def test_hermes_tool_metadata_privacy(tmp_path,monkeypatch):
    monkeypatch.setenv('WORLDCORE_DB',str(tmp_path/'hermes.db'))
    _,hooks=harness()
    hooks['post_tool_call'](tool_name='terminal',args={'secret':'SECRET_VALUE'},result='API: SECRET_VALUE',
                           error_message='PRIVATE_TOKEN',status='ok',duration_ms=12,task_id='test')
    with WorldCore(tmp_path/'hermes.db') as core:
        e=core.events('local');assert len(e)==1
        assert all(x not in e[0]['summary'] for x in ['SECRET_VALUE','PRIVATE_TOKEN'])

def test_hermes_missing_db_fails_open(monkeypatch,tmp_path):
    monkeypatch.setenv('WORLDCORE_DB',str(tmp_path/'invalid'/'db'))
    _,hooks=harness()
    assert hooks['pre_llm_call'](user_message='') is None
    assert hooks['post_tool_call'](tool_name='',args={},result='') is None

def test_hermes_host_llm_opt_in_mock(tmp_path,monkeypatch):
    module,_=harness()
    called=[]
    class LLM:
        def complete(self,**kw):
            called.append(kw)
            return SimpleNamespace(text='Suggestion: verify the result.',model='stub-model',provider='stub')
    ctx=SimpleNamespace(llm=LLM())
    assert module.llm_contract_probe(ctx)['status']=='disabled'
    monkeypatch.setenv('WORLDCORE_ENABLE_LLM_PROBE','1')
    result=module.llm_contract_probe(ctx,'What can improve memory quality?')
    assert result['status']=='completed' and result['provider']=='stub'
    assert called[0]['purpose']=='worldcore.contract_probe' and called[0]['max_tokens']==100
    assert module.llm_contract_probe(SimpleNamespace(), 'a')['status']=='unavailable'

def test_hermes_opt_in_registers_probe_command(monkeypatch):
    monkeypatch.setenv('WORLDCORE_ENABLE_LLM_PROBE','1')
    spec=importlib.util.spec_from_file_location('worldcore_hermes_cmd_v09',PATH)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    commands={};hooks={}
    class Host:
        llm=SimpleNamespace(complete=lambda **k:SimpleNamespace(text='Safe to verify first',model='stub',provider='stub'))
        def register_hook(self,name,cb):hooks[name]=cb
        def register_command(self,**kwargs):commands[kwargs['name']]=kwargs['handler']
    module.register(Host())
    assert 'worldcore-probe' in commands
    assert 'Safe to verify first' in commands['worldcore-probe']('short question')
