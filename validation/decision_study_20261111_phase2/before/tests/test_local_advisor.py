import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from unittest.mock import patch

import pytest
from cognitive_core import CognitiveCore,Settings
from cognitive_core.decision import Decision
from cognitive_core.ondemand import infer,run_bounded

EVENT={'kind':'question_open','question':'How can runner recovery work?'}

@pytest.fixture
def setup(tmp_path):
    archive=tmp_path/'archive'
    c=CognitiveCore(Settings(home=archive,owner='alice',namespace='research'))
    c.vault.document('runner','runner recovery source text')
    c.worldcore.remember('alice','runner','runner recovery WorldCore memory',space='research')
    c.worldcore.ingest_document('alice','runner-knowledge','runner recovery knowledge evidence from an inspectable fixture',space='research',title='Runner knowledge',source_url='https://example.org/source',license='PUBLIC-DOMAIN')
    c.close()
    model=tmp_path/'tiny.gguf';model.write_bytes(b'GGUF-fixture')
    c=CognitiveCore(Settings(home=tmp_path/'state',owner='alice',namespace='research',enable_local_model=True,local_model_gguf=str(model)))
    yield c,archive
    c.close()

def fingerprints(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}

def test_readonly_cache_restart(setup):
    c,archive=setup;before=fingerprints(archive)
    with patch('cognitive_core.advisor.infer',return_value=Decision('PREPARE_SILENTLY',.7,'local research',model_used=True)) as model:
        first=c.assess_local(EVENT,archive);second=c.assess_local(EVENT,archive)
    assert first['status']=='classified' and first['model_calls']==1
    assert second['status']=='cached' and second['model_calls']==0 and model.call_count==1
    assert {h['kind'] for h in first['sources']}=={'note','worldcore_memory','worldcore_knowledge'}
    assert first['epistemic']=='INFERRED' and not first['action_executed']
    assert before==fingerprints(archive) and not c.s.db_path.exists()
    reopened=CognitiveCore(c.s)
    try:
        with patch('cognitive_core.advisor.infer',side_effect=AssertionError('reload')):
            assert reopened.assess_local(EVENT,archive)['status']=='cached'
    finally:reopened.close()

@pytest.mark.parametrize('event',[{'text':'ciao'},{'text':'hi!'},{'kind':'external_action','text':'buy'}])
def test_reflex_no_read_or_model(setup,event):
    c,_=setup
    with patch('cognitive_core.advisor.archive_context',side_effect=AssertionError('read')):
        assert c.assess_local(event,'/nonexistent')['status']=='reflex'
    assert not c.s.home.exists()

def test_disabled_zero_cost(setup):
    c,_=setup;c.s.enable_local_model=False
    assert c.assess_local(EVENT,'/missing')['status']=='disabled'
    assert not c.s.home.exists()

def test_foreign_owner_no_context(setup):
    c,archive=setup;c.s.owner='bob'
    with patch('cognitive_core.advisor.infer',side_effect=AssertionError('model')):
        result=c.assess_local(EVENT,archive)
    assert result['status']=='no_local_evidence' and not result['sources']

def test_sidecar_separation(setup):
    c,archive=setup;c.s.local_decision_state=str(archive/'state');before=fingerprints(archive)
    with pytest.raises(ValueError):c.assess_local(EVENT,archive)
    assert before==fingerprints(archive)

def test_failed_call_reserved_and_cached(setup):
    c,archive=setup;c.s.max_model_calls_per_day=1
    with patch('cognitive_core.advisor.infer',side_effect=TimeoutError('slow')):
        result=c.assess_local(EVENT,archive)
    assert result['status']=='fallback' and result['model_calls']==1
    with patch('cognitive_core.advisor.infer',side_effect=AssertionError('reload')):
        assert c.assess_local(EVENT,archive)['status']=='cached'
        assert c.assess_local({**EVENT,'question':'Another runner recovery question?'},archive)['status']=='daily_model_budget'

def test_zero_quota_busy_lease(setup):
    c,archive=setup;c.s.max_model_calls_per_day=0
    with patch('cognitive_core.advisor.infer',side_effect=AssertionError('load')):
        assert c.assess_local(EVENT,archive)['status']=='daily_model_budget'
        c.s.max_model_calls_per_day=10
        db=sqlite3.connect(c.s.home/'local-decision/decisions.sqlite3')
        db.execute('UPDATE lease SET until=?',(time.time()+100,));db.commit();db.close()
        assert c.assess_local(EVENT,archive)['status']=='model_busy'

def test_no_escalation(setup):
    c,archive=setup
    with patch('cognitive_core.advisor.infer',return_value=Decision('PREPARE_SILENTLY',1,'execute',model_used=True)):
        result=c.assess_local({'text':'Investigating runner recovery mechanisms for a future project'},archive)
    assert result['decision']['action']=='STORE_ONLY' and not result['action_executed']

def test_new_evidence_invalidates_cache(setup):
    c,archive=setup
    with patch('cognitive_core.advisor.infer',return_value=Decision('STORE_ONLY',.4,'inspect',model_used=True)) as model:
        c.assess_local(EVENT,archive)
        writer=CognitiveCore(Settings(home=archive,owner='alice',namespace='research'))
        writer.vault.db.execute("UPDATE documents SET text='runner recovery REVISED evidence'");writer.close()
        assert c.assess_local(EVENT,archive)['status']=='classified'
    assert model.call_count==2

@pytest.mark.parametrize('output',['{}','{"action":"EXECUTE","priority":1}',
    '{"action":"WAIT","priority":true}','{"action":"WAIT","priority":NaN}',
    '{"action":"WAIT","priority":0,"grant":true}',
    'Prompt echoed {"action":"WAIT","priority":0}'])
def test_bad_output_rejected(setup,output):
    c,_=setup
    with patch('cognitive_core.ondemand.run_bounded',return_value=output):
        with pytest.raises(ValueError):infer(c.s,EVENT,[])

def test_offline_command_private_prompt(setup):
    c,_=setup
    def fake(command,timeout):
        assert '--offline' in command and '--single-turn' in command
        assert command[command.index('--threads')+1]=='2'
        assert command[command.index('--predict')+1]=='64'
        assert command[command.index('--device')+1]=='none'
        prompt=Path(command[command.index('--file')+1])
        assert 'excerpts' in prompt.read_text() and prompt.stat().st_mode & 0o077==0
        return '{"relevance":"no"}'
    with patch('cognitive_core.ondemand.run_bounded',side_effect=fake):assert infer(c.s,EVENT,[]).action=='WAIT'

def test_process_timeout_output_exit():
    assert run_bounded([sys.executable,'-c','print("hello")'],2).strip()=='hello'
    with pytest.raises(subprocess.TimeoutExpired):run_bounded([sys.executable,'-c','import time;time.sleep(10)'],.1)
    with pytest.raises(ValueError):run_bounded([sys.executable,'-c','print("x"*1000000)'],2)
    with pytest.raises(ValueError):run_bounded([sys.executable,'-c','raise SystemExit(1)'],2)

def test_cycle_advisor_veto(setup):
    c,archive=setup
    active=CognitiveCore(Settings(home=archive,owner='alice',namespace='research',enable_local_model=True,
        local_model_gguf=c.s.local_model_gguf,local_decision_state=str(c.s.home/'cycle-sidecar')))
    try:
        active.drive.upsert_project('p','Runner',['runner'])
        topic=active.vault.topic('runner','How can runner recovery work?')
        for _ in range(3):active.cycle_once(topic)
        with patch('cognitive_core.advisor.infer',return_value=Decision('WAIT',.2,'irrelevant',model_used=True)):
            result=active.cycle_once(topic)
        assert result['status']=='abstained' and result['checkpoint']['decision']['action']=='WAIT'
        assert not active.vault.db.execute("SELECT 1 FROM documents WHERE kind='cognitive_note'").fetchone()
    finally:active.close()


def test_live_wal_read_without_original_changes(setup):
    c,archive=setup
    writer=CognitiveCore(Settings(home=archive,owner='alice',namespace='research'))
    writer.vault.document('WAL evidence','waluniquetoken committed evidence in live WAL')
    before=fingerprints(archive)
    try:
        with patch('cognitive_core.advisor.infer',return_value=Decision('STORE_ONLY',.4,'inspect',model_used=True)):
            result=c.assess_local({**EVENT,'question':'waluniquetoken'},archive)
        assert result['status']=='classified'
        assert 'waluniquetoken' in result['sources'][0]['excerpt']
        assert before==fingerprints(archive)
    finally:writer.close()


def test_admission_survives_parent_crash(setup):
    c,archive=setup;c.s.max_model_calls_per_day=1
    code='''import os,sys
from unittest.mock import patch
from cognitive_core import CognitiveCore,Settings
c=CognitiveCore(Settings(home=sys.argv[1],owner='alice',namespace='research',enable_local_model=True,
 local_model_gguf=sys.argv[3],max_model_calls_per_day=1))
with patch('cognitive_core.advisor.infer',side_effect=lambda *args:os._exit(42)):
 c.assess_local({'kind':'question_open','question':'How can runner recovery work?'},sys.argv[2])
'''
    result=subprocess.run([sys.executable,'-B','-c',code,str(c.s.home),str(archive),c.s.local_model_gguf],capture_output=True,text=True,timeout=10)
    assert result.returncode==42,result.stderr
    db=sqlite3.connect(c.s.home/'local-decision/decisions.sqlite3')
    assert db.execute('SELECT calls FROM budget').fetchone()[0]==1
    db.execute('UPDATE lease SET until=0');db.commit();db.close()
    assert c.assess_local(EVENT,archive)['status']=='daily_model_budget'


@pytest.mark.parametrize('raw',['{"relevance":"execute"}','{"relevance":true}','{"relevance":"yes","grant":true}'])
def test_relevance_schema_cannot_grant_capabilities(setup,raw):
    c,_=setup
    with patch('cognitive_core.ondemand.run_bounded',return_value=raw):
        with pytest.raises(ValueError):infer(c.s,EVENT,[])


def test_observe_defers_gguf_without_http(setup):
    c,_=setup
    with patch('cognitive_core.decision.LocalDecisionModel.decide',side_effect=AssertionError('HTTP')):
        result=c.observe(EVENT)
    assert result['decision']['model_used'] is False


def test_capability_removal_changes_strategy_before_inference(setup):
    c,archive=setup;c.s.local_model_binary='/does/not/exist'
    before=fingerprints(archive)
    with patch('cognitive_core.advisor.infer',side_effect=AssertionError('unavailable tool invoked')):
        result=c.assess_local(EVENT,archive)
    assert result['model_calls']==0 and result['status']=='capability_unavailable'
    assert result['strategy']=='deterministic_local_fallback'
    assert result['self_forecast']['admitted'] is False and result['self_forecast']['probability']==0
    assert before==fingerprints(archive)


def test_prediction_precedes_actual_observation(setup):
    from cognitive_core.selfmodel import SelfModel
    c,archive=setup
    with patch('cognitive_core.advisor.infer',return_value=Decision('STORE_ONLY',.5,'fixture',model_used=True)):
        result=c.assess_local(EVENT,archive)
    m=SelfModel(c.s.home/'local-decision','alice','research')
    try:
        episode=m.episodes()[0]
        assert episode['before_at']<=episode['outcome']['observed_at']
        assert result['self_forecast']['samples']==0
        assert result['self_outcome']['successful'] is True
        with pytest.raises(ValueError):m.resolve(episode['id'],False,'rewritten history')
        with pytest.raises(KeyError):m.resolve('foreign',True,'source')
    finally:m.close()


def test_forecast_storage_failure_abstains_and_releases_lease(setup):
    c,archive=setup
    with patch('cognitive_core.advisor.SelfModel.forecast',side_effect=ValueError('disk budget')):
        with patch('cognitive_core.advisor.infer',side_effect=AssertionError('unrecorded inference')):
            result=c.assess_local(EVENT,archive)
    assert result['model_calls']==0 and result['status']=='self_model_budget_or_storage'
    db=sqlite3.connect(c.s.home/'local-decision/decisions.sqlite3')
    try:
        assert db.execute('SELECT until FROM lease').fetchone()[0]==0
        assert db.execute('SELECT calls FROM budget').fetchone()[0]==1
    finally:db.close()
