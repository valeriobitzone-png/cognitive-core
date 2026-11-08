"""Assertions run against *implemented* behavior; no fake AI outputs."""
from __future__ import annotations
import concurrent.futures
import multiprocessing
import json
import os
import sqlite3
import subprocess
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from worldcore import WorldCore, WorldCoreError
from worldcore.bridge import dispatch
from worldcore.engine import redact

@pytest.fixture
def db(tmp_path):
    with WorldCore(tmp_path/'world.db') as w:
        yield w


def due(days=1):return (datetime.now(timezone.utc)+timedelta(days=days)).isoformat()


def test_init_db_permissions(tmp_path):
    with WorldCore(tmp_path/'secure'/'db.sqlite') as w:assert w.db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    if os.name=='posix':
        assert ((tmp_path/'secure').stat().st_mode & 0o777)==0o700
        assert ((tmp_path/'secure'/'db.sqlite').stat().st_mode & 0o777)==0o600


def test_no_model_and_dependencies(db):
    assert db.state('alice')=={}
    assert db.forecast_stats('alice')['resolved']==0
    assert db.recall('alice','anything')==[]


def test_memory_version_reconciliation(db):
    a=db.remember('alice','project.arch','version one',source='decision')
    b=db.remember('alice','project.arch','version two',source='decision')
    assert b['version']==2 and b['supersedes']==a['id']
    assert [m['status'] for m in db.history('alice','project.arch')]==['superseded','active']
    assert 'version one' not in db.context_for('alice','project arch')
    assert 'version two' in db.context_for('alice','project arch')
    assert db.remember('alice','project.arch','version two',source='decision')['id']==b['id']


def test_memory_updated_expiry_and_sources(db):
    a=db.remember('u','old','aging',valid_until=due(-1)) if False else None
    with pytest.raises(WorldCoreError):db.remember('u','old','aging',valid_until=due(-1))
    r=db.remember('u','new','fresh',kind='preference',source='user',confidence=.8,tags=['important'],valid_until=due(1))
    assert db.memory_by_id('u',r['id'])['kind']=='preference'
    assert db.recall('u','important')[0]['fact_key']=='new'

@pytest.mark.parametrize('bad', ['', ' ', 'a'*129, 'owner with spaces', 'a\x00'])
def test_owner_key_validation(db,bad):
    with pytest.raises(WorldCoreError): db.remember(bad,'k','v')
    with pytest.raises(WorldCoreError): db.remember('u',bad,'v')

@pytest.mark.parametrize('bad', [float('nan'),float('inf'),-1,1.1,'hi'])
def test_bad_confidence(db,bad):
    with pytest.raises(WorldCoreError):db.remember('u','k','v',confidence=bad)


def test_cross_tenant_and_space_isolation(db):
    ma=db.remember('alice','shared','secret alice',space='work')
    db.remember('bob','shared','secret bob',space='work')
    db.remember('alice','shared','secret private',space='private')
    assert db.recall('bob','secret',space='work')[0]['value']=='secret bob'
    assert db.recall('alice','secret',space='private')[0]['value']=='secret private'
    assert db.memory_by_id('bob',ma['id'],space='work') is None
    assert db.history('bob','shared',space='work')[0]['value']=='secret bob'
    assert db.forget('bob','shared',space='work')==1
    assert db.recall('bob','secret',space='work')==[]
    assert len(db.history('alice','shared',space='work'))==1
    db.set_state('alice','x',2,space='work')
    assert db.state('bob',space='work')=={} and db.state('alice',space='private')=={}


def test_sql_injection_and_control_char(db):
    db.remember('u','a','alice hidden')
    assert db.recall('u',"'; DROP TABLE memories;--")==[]
    assert db.recall('u','alice')[0]['value']=='alice hidden'
    with pytest.raises(WorldCoreError):db.remember('u','b','not\x00allowed')


def test_redaction_in_memories_and_events(db):
    db.remember('a','credential','api_key=verysecretandbad sk-ABCDEFGHIJKLMN')
    assert 'verysecretandbad' not in db.recall('a','credential')[0]['value']
    db.record_event('a','test','password: hello_world')
    assert 'hello_world' not in db.events('a')[0]['summary']
    assert '[REDACTED]' in redact('token: abc123')


def test_limit_and_recall_empty(db):
    for i in range(12):db.remember('a',f'key{i}',f'phone data {i}')
    assert len(db.recall('a','phone',limit=3))==3
    assert len(db.recall('a','',limit=50))==12
    with pytest.raises(WorldCoreError):db.recall('a','x',limit=1000)
    assert not db.context_for('a','nonexistent')


def test_persistence_between_instances(tmp_path):
    path=tmp_path/'p.db'
    with WorldCore(path) as a:
        a.remember('owner','pref','local first')
        a.set_state('owner','counter',6)
    with WorldCore(path) as b:
        assert b.recall('owner','local')[0]['value']=='local first'
        assert b.state('owner')['counter']==6


def test_event_scoping(db):
    db.record_event('alice','tool','completed',source='hermes')
    assert len(db.events('alice'))==1
    assert len(db.events('bob'))==0


def test_world_simulation_does_not_mutate(db):
    db.set_state('u','x',10)
    predicted=db.simulate('u',[{'op':'add','key':'x','value':-3},{'op':'set','key':'new','value':{'k':1}},{'op':'delete','key':'new'}])
    assert predicted['predicted']=={'x':7}
    assert db.state('u')=={'x':10}
    assert predicted['executed'] is False
    assert len(predicted['trace'])==3


def test_simulation_precondition_false(db):
    db.set_state('u','x',2)
    res=db.simulate('u',[{'op':'add','key':'x','value':10,'if_equals':3}])
    assert res['predicted']['x']==2 and not res['trace'][0]['applied']

@pytest.mark.parametrize('bad', [[{'op':'run','key':'x'}],[{'op':'add','key':'x','value':1}],[{'op':'set','key':'a','value':float('nan')}],[{'op':'set','key':'###','value':1}],['rm -rf /']])
def test_simulation_invalid(db,bad):
    with pytest.raises(WorldCoreError):db.simulate('u',bad)


def test_state_revision(db):
    assert db.set_state('u','a',False)['revision']==1
    assert db.set_state('u','a',True)['revision']==2


def test_forecast_brier_positive(db):
    f=db.forecast('u','will fail',True,.8,due())
    assert f['status']=='pending'
    with pytest.raises(WorldCoreError):db.resolve_forecast('u',f['id'],True)
    a=db.resolve_forecast('u',f['id'],False,allow_early=True)
    assert round(a['brier'],4)==.64
    assert round(db.forecast_stats('u')['mean_brier'],4)==.64
    with pytest.raises(WorldCoreError):db.resolve_forecast('u',f['id'],False,allow_early=True)


def test_forecast_brier_expected_false(db):
    f=db.forecast('u','will not fail',False,.8,due())
    r=db.resolve_forecast('u',f['id'],False,allow_early=True)
    assert round(r['brier'],4)==.04


def test_forecast_cross_tenant(db):
    f=db.forecast('alice','x',True,.6,due())
    assert db.get_forecast('bob',f['id']) is None
    with pytest.raises(WorldCoreError):db.resolve_forecast('bob',f['id'],True,allow_early=True)

@pytest.mark.parametrize('bad', [-1,2,float('nan'),'0.5'])
def test_bad_probability(db,bad):
    with pytest.raises(WorldCoreError):db.forecast('u','claim',True,bad,due())


def test_forecast_due_and_timezone_validation(db):
    with pytest.raises(WorldCoreError):db.forecast('u','claim',True,.6,'2027-01-01T00:00:00')
    with pytest.raises(WorldCoreError):db.forecast('u','claim',True,.6,due(-1))


def test_observational_statistics(db):
    for x in [True,True,True,False,False]:db.observe_binary('u','tests_broken',x)
    result=db.estimate_binary('u','tests_broken')
    assert result['samples']==5 and result['successes']==3
    assert round(result['probability'],5)==round(4/7,5)
    assert result['warning'].startswith('association only')
    assert db.estimate_binary('bob','tests_broken')['probability'] is None


def test_proactive_threshold_and_cooldown(db):
    db.set_state('u','regressions',4)
    db.add_rule('u','regressions','>=',3,'Review regressions',cooldown_seconds=86400)
    first=db.tick('u')
    assert len(first)==1 and first[0]['executed'] is False
    assert not db.tick('u')
    assert len(db.alerts('u'))==1
    assert db.alerts('bob')==[]


def test_proactive_does_not_alarm_if_missing(db):
    db.add_rule('u','absent','>',0,'Should not fire')
    assert db.tick('u')==[]


def test_proactive_strict_numeric(db):
    db.add_rule('u','enabled','==',1,'Alert')
    db.set_state('u','enabled',True)
    assert db.tick('u')==[]


def test_proactive_cooldown_zero(db):
    db.add_rule('u','risk','>',0,'Risk',cooldown_seconds=0)
    db.set_state('u','risk',1)
    assert len(db.tick('u'))==1
    assert len(db.tick('u'))==1


def test_proactive_no_external_action(db):
    db.add_rule('u','x','>=',2,'Danger')
    db.set_state('u','x',5)
    assert db.tick('u')[0]['executed'] is False


def test_action_default_deny_exact_args_one_time(db):
    req=db.request_action('u','send_email',{'to':'foo@example.com'},'Ask to send')
    rid=req['id']
    assert db.consume_approval('u',rid,'send_email',{'to':'foo@example.com'}) is False
    db.approve_action('u',rid,approve=True)
    assert not db.consume_approval('u',rid,'send_email',{'to':'other@example.com'})
    assert not db.consume_approval('u',rid,'delete_file',{'to':'foo@example.com'})
    assert not db.consume_approval('bob',rid,'send_email',{'to':'foo@example.com'})
    assert db.consume_approval('u',rid,'send_email',{'to':'foo@example.com'})
    assert not db.consume_approval('u',rid,'send_email',{'to':'foo@example.com'})


def test_action_explicit_denial(db):
    req=db.request_action('u','action',{},'try')
    assert db.approve_action('u',req['id'])['status']=='denied'
    with pytest.raises(WorldCoreError):db.approve_action('u',req['id'],approve=True)


def test_action_expiry(db):
    req=db.request_action('u','action',{},'try')
    db.db.execute("UPDATE approvals SET expires_at=? WHERE id=?", (due(-1),req['id']))
    with pytest.raises(WorldCoreError):db.approve_action('u',req['id'],approve=True)
    assert not db.consume_approval('u',req['id'],'action',{})


def test_memory_delete_tenant_safe(db):
    db.remember('a','k','value')
    db.remember('b','k','value')
    assert db.forget('a','k')==1
    assert len(db.recall('b','value'))==1


def test_bridge_allowed_operations(db):
    dispatch({'op':'remember','owner':'u','key':'x','value':'world model'},db)
    assert dispatch({'op':'recall','owner':'u','query':'world'},db)['memories'][0]['value']=='world model'
    assert 'world model' in dispatch({'op':'context','owner':'u','query':'model'},db)['context']
    assert dispatch({'op':'simulate','owner':'u','actions':[]},db)['executed'] is False
    assert dispatch({'op':'forecast_stats','owner':'u'},db)['resolved']==0
    with pytest.raises(WorldCoreError):dispatch({'op':'approve','owner':'u'},db)
    with pytest.raises(WorldCoreError):dispatch({'op':'consume_approval','owner':'u'},db)


def test_bridge_subprocess(tmp_path):
    env={**os.environ,'WORLDCORE_DB':str(tmp_path/'bridge.db')}
    cmd=[sys.executable,'-m','worldcore.bridge']
    p=subprocess.run(cmd,input=json.dumps({'op':'remember','owner':'a','key':'color','value':'purple'}),text=True,capture_output=True,env=env)
    assert p.returncode==0 and json.loads(p.stdout)['ok']
    p=subprocess.run(cmd,input=json.dumps({'op':'context','owner':'a','query':'color'}),text=True,capture_output=True,env=env)
    assert 'purple' in json.loads(p.stdout)['result']['context']
    p=subprocess.run(cmd,input=json.dumps({'op':'approve','owner':'a'}),text=True,capture_output=True,env=env)
    assert p.returncode!=0 and not json.loads(p.stdout)['ok']


def test_operator_cli(tmp_path):
    path=str(tmp_path/'cli.db')
    cmd=[sys.executable,'-m','worldcore','--db',path,'--owner','u']
    p=subprocess.run(cmd+['remember','k','a fact'],capture_output=True,text=True)
    assert p.returncode==0 and json.loads(p.stdout)['version']==1
    p=subprocess.run(cmd+['history','k'],capture_output=True,text=True)
    assert len(json.loads(p.stdout))==1
    p=subprocess.run(cmd+['doctor'],capture_output=True,text=True)
    assert json.loads(p.stdout)['integrity']=='ok'


def _write_in_other_process(args):
    path,i=args
    with WorldCore(path) as w:
        w.remember('u','counter',f'v{i}')
    return i


def test_concurrent_process_memory_versions(tmp_path):
    path=str(tmp_path/'multi.db')
    with concurrent.futures.ProcessPoolExecutor(max_workers=4, mp_context=multiprocessing.get_context('spawn')) as ex:
        got=list(ex.map(_write_in_other_process,[(path,i) for i in range(15)]))
    assert len(got)==15
    with WorldCore(path) as w:
        hist=w.history('u','counter')
        assert len(hist)==15
        assert [x['version'] for x in hist]==list(range(1,16))
        assert len([x for x in hist if x['status']=='active'])==1
        assert w.db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'


def test_threaded_increment_revision(db):
    def f(i):return db.set_state('u','counter',i)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        rows=list(ex.map(f,range(40)))
    assert sorted(x['revision'] for x in rows)==list(range(1,41))


def test_scope_randomized_isolation(db):
    for owner in ('a','b','c'):
        for space in ('private','shared'):
            for n in range(12):db.remember(owner,f'k{n}',f'{owner} {space} thing {n}',space=space)
    for owner in ('a','b','c'):
        for space in ('private','shared'):
            hits=db.recall(owner,'thing',space=space,limit=50)
            assert len(hits)==12
            assert all(h['owner']==owner and h['space']==space for h in hits)
