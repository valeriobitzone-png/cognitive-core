import json
from pathlib import Path
import pytest
from worldcore import WorldCore,WorldCoreError

def test_real_action_requires_operator_approval(tmp_path,monkeypatch):
    monkeypatch.setenv('WORLDCORE_ACTION_ROOT',str(tmp_path/'outbox'))
    with WorldCore(tmp_path/'core.sqlite') as w:
        args={'title':'Prova','body':'Scrivi una nota'}
        req=w.propose_real_action('alice','note.create',args,'Nota autorizzata',space='secret')
        with pytest.raises(WorldCoreError):w.execute_approved_action('alice',req['id'],'note.create',args,space='secret')
        w.approve_action('alice',req['id'],space='secret',approve=True)
        with pytest.raises(WorldCoreError):w.execute_approved_action('bob',req['id'],'note.create',args,space='secret')
        with pytest.raises(WorldCoreError):w.execute_approved_action('alice',req['id'],'note.create',{'title':'Prova','body':'TAMPERED'},space='secret')
        result=w.execute_approved_action('alice',req['id'],'note.create',args,space='secret')
        assert result['status']=='completed'
        assert Path(result['artifact']).is_file()
        assert json.loads(Path(result['artifact']).read_text())['args']==args
        assert w.action_receipt('alice',req['id'],space='secret')['status']=='completed'
        assert w.action_receipt('alice',req['id'],space='default') is None
        with pytest.raises(WorldCoreError):w.execute_approved_action('alice',req['id'],'note.create',args,space='secret')

def test_real_action_disabled_and_never_arbitrary_host(tmp_path):
    with WorldCore(':memory:') as w:
        with pytest.raises(WorldCoreError):w.propose_real_action('alice','shell.exec',{'command':'pwd'},'No')
        req=w.propose_real_action('alice','task.create',{'description':'Visitare il sito','due_at':'2027-01-15T10:00:00Z'},'Agenda')
        w.approve_action('alice',req['id'],approve=True)
        with pytest.raises(WorldCoreError):w.execute_approved_action('alice',req['id'],'task.create',{'description':'Visitare il sito','due_at':'2027-01-15T10:00:00Z'})

def test_semantics_host_verified_conflicts_and_tenant_isolation(tmp_path):
    with WorldCore(tmp_path/'scenes.db') as w:
        claim=lambda value:{'entity':'photo1','attribute':'object','value':value,'confidence':0.9}
        w.record_semantic_observation('a','room',[claim('chair')],modality='image',source='v1',verified_by_host=True)
        w.record_semantic_observation('a','room',[claim('chair')],modality='audio',source='a1',verified_by_host=True)
        scene=w.semantic_scene('a','room')['claims'][0]
        assert scene['status']=='corroborated' and scene['value']=='chair'
        w.record_semantic_observation('a','room',[claim('table')],modality='web',source='w1',verified_by_host=True)
        assert w.semantic_scene('a','room')['claims'][0]['status']=='conflict'
        assert w.semantic_scene('b','room')['claims']==[]
        with pytest.raises(WorldCoreError):w.record_semantic_observation('a','x',[claim('chair')],modality='executable',source='x')
        with pytest.raises(WorldCoreError):w.record_semantic_observation('a','x',[{'entity':'x','attribute':'a','value':'v','confidence':float('nan')}],modality='text',source='x')

def test_unverified_mcp_claims_not_trusted(tmp_path):
    with WorldCore(tmp_path/'scenes.db') as w:
        w.record_semantic_observation('a','browser',[{'entity':'site','attribute':'safety','value':'totally safe','confidence':1}],modality='web',source='unknown_mcp')
        assert w.semantic_scene('a','browser')['claims'][0]['status']=='unsupported'


def test_real_task_created_updates_personal_state(tmp_path,monkeypatch):
    monkeypatch.setenv('WORLDCORE_ACTION_ROOT',str(tmp_path/'out'))
    with WorldCore(tmp_path/'core.db') as w:
        args={'description':'Preparare la presentazione','due_at':'2027-01-15T10:00:00Z'}
        req=w.propose_real_action('owner','task.create',args,'Attività approvata')
        w.approve_action('owner',req['id'],approve=True)
        result=w.execute_approved_action('owner',req['id'],'task.create',args)
        assert result['status']=='completed'
        items=w.anticipate_needs('owner',now='2027-01-14T10:00:00Z',horizon_hours=48)['items']
        assert any(x['task_id']==req['id'] for x in items)


def test_mcp_approved_action_end_to_end(tmp_path,monkeypatch):
    import sys,types
    from worldcore.mcp_server import create_server
    class FakeMCP:
        def __init__(self,*args,**kw):self.tools={}
        def tool(self):
            def f(method):self.tools[method.__name__]=method;return method
            return f
    for name,mod in [('mcp',types.ModuleType('mcp')),('mcp.server',types.ModuleType('mcp.server')),
                     ('mcp.server.fastmcp',types.ModuleType('mcp.server.fastmcp'))]:
        monkeypatch.setitem(sys.modules,name,mod)
    sys.modules['mcp.server.fastmcp'].FastMCP=FakeMCP
    monkeypatch.setenv('WORLDCORE_DB',str(tmp_path/'mcp.sqlite'))
    monkeypatch.setenv('WORLDCORE_OWNER','alice')
    monkeypatch.setenv('WORLDCORE_SPACE','private')
    monkeypatch.setenv('WORLDCORE_ACTION_ROOT',str(tmp_path/'out'))
    host=create_server()
    assert {'action_propose','action_execute_approved','action_execution_receipt','semantic_observe','semantic_scene'} <= set(host.tools)
    args={'title':'Note from MCP','body':'Data on disk'}
    req=host.tools['action_propose']('note.create',args,'Approved action')
    assert host.tools['action_execute_approved'](req['id'],'note.create',args)['status']=='disabled'
    monkeypatch.setenv('WORLDCORE_MCP_REAL_ACTIONS','1')
    # not yet operator approved
    with pytest.raises(WorldCoreError):host.tools['action_execute_approved'](req['id'],'note.create',args)
    with WorldCore(tmp_path/'mcp.sqlite') as w:w.approve_action('alice',req['id'],space='private',approve=True)
    completed=host.tools['action_execute_approved'](req['id'],'note.create',args)
    assert completed['status']=='completed'
    assert Path(completed['artifact']).exists()
    assert host.tools['action_execution_receipt'](req['id'])['status']=='completed'

def test_macro_artifact_equivalent_to_sklearn():
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'benchmarks'))
    import v08_macro_gdp as bench
    from worldcore.macro_gdp import predict_next_gdp,FEATURE_NAMES
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import Ridge
    x,y,*_=bench.dataset()
    years=bench.dataset()[-1]
    model=make_pipeline(StandardScaler(),Ridge(alpha=.1));model.fit(x[years<=1995],y[years<=1995])
    artifact=Path(__file__).resolve().parents[1]/'training-artifacts/v08_macro_gdp_model.json'
    for row in x[-8:]:
        data={k:float(v) for k,v in zip(FEATURE_NAMES,row)}
        p=predict_next_gdp(data,artifact)['predicted_next_real_gdp']
        assert abs(p-model.predict(row.reshape(1,-1))[0])<1e-6

def test_complete_audit_disposition_has_246_quarantined():
    p=Path(__file__).resolve().parents[1]/'catalog/audit_disposition_246_v08.json'
    obj=json.loads(p.read_text())
    assert obj['repo_count']==246 and obj['approved']==0
    assert len(obj['records'])==246
    assert all(r['gate']=='QUARANTINE' for r in obj['records'])
    assert any(r['repo']=='polakowo/vectorbt' and 'copyleft_or_restricted_license_review' in r['flags'] for r in obj['records'])
