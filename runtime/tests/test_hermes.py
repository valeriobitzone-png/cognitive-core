import importlib.util
import json
from pathlib import Path
from worldcore import WorldCore

PATH=Path(__file__).resolve().parents[1]/'adapters'/'hermes'/'worldcore'/'__init__.py'


def test_hermes_hooks_register_and_execute(tmp_path,monkeypatch):
    monkeypatch.setenv('WORLDCORE_DB',str(tmp_path/'h.db'))
    with WorldCore(tmp_path/'h.db') as w:w.remember('local','project.next','use world model')
    spec=importlib.util.spec_from_file_location('worldcore_hermes_adapter', PATH)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    registered={}
    class Context:
        def register_hook(self,name,cb):registered[name]=cb
    module.register(Context())
    assert set(registered)=={'pre_llm_call','post_tool_call'}
    assert 'use world model' in registered['pre_llm_call'](session_id='s',user_message='project next',model='test')['context']
    assert registered['pre_llm_call'](session_id='s',user_message='') is None
    registered['post_tool_call'](tool_name='terminal',args={'secret':'very_sensitive'},result='my password: xxx',status='ok',duration_ms=10)
    with WorldCore(tmp_path/'h.db') as w:
        assert len(w.events('local'))==1
        assert 'very_sensitive' not in w.events('local')[0]['summary']
        assert 'password' not in w.events('local')[0]['summary']


def test_hermes_whatif_has_typed_arguments_and_errors(tmp_path,monkeypatch):
    monkeypatch.setenv('WORLDCORE_DB',str(tmp_path/'native.db'))
    monkeypatch.setenv('WORLDCORE_OWNER','local')
    monkeypatch.setenv('WORLDCORE_SPACE','default')
    spec=importlib.util.spec_from_file_location('worldcore_hermes_typed',PATH)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    tools={}
    class Context:
        def register_hook(self,*args):pass
        def register_tool(self,**kw):tools[kw['name']]=kw
    module.register(Context())
    params=tools['worldcore_whatif']['schema']['parameters']['properties']
    assert params['scenarios']['items']['required']==['id','actions']
    assert params['objectives']['items']['required']==['key','direction']
    assert params['scenarios']['items']['properties']['actions']['items']['properties']['op']['enum']==['set','add','delete']
    invalid={'question':'bad','scenarios':[{'name':'invented','budget_change':20}],'objectives':[]}
    assert json.loads(tools['worldcore_whatif']['handler'](invalid))['error']=='WorldCoreError'
    with WorldCore(tmp_path/'native.db') as w:w.set_state('local','budget',100)
    valid={'question':'typed','scenarios':[{'id':'prepare','actions':[{'op':'add','key':'budget','value':-5}]},{'id':'keep','actions':[]}],
           'objectives':[{'key':'budget','direction':'minimize','scale':1}]}
    result=json.loads(tools['worldcore_whatif']['handler'](valid))
    assert result['scenarios'][0]['projected_state']['budget']==95
    assert result['action_executed'] is False
    with WorldCore(tmp_path/'native.db') as w:assert w.state('local')['budget']==100
