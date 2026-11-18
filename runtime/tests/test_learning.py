"""Real assertions against the learning kernel; no external models or services."""
from __future__ import annotations
import concurrent.futures
import json
import multiprocessing
import os
import subprocess
import sys
import pytest
from worldcore import WorldCore, WorldCoreError
from worldcore.bridge import dispatch


@pytest.fixture
def w(tmp_path):
    with WorldCore(tmp_path/'learn.db') as core:
        yield core


def example(sample_id='a', outcome=True, x=.6):
    return {'id':sample_id,'features':{'x':x,'y':.2},'outcome':outcome}


def test_logistic_learns_and_persists(tmp_path):
    path=tmp_path/'persist.db'
    with WorldCore(path) as w:
        w.create_model('alice','risk',['x','y'],provenance='synthetic')
        assert w.predict_model('alice','risk',{'x':0,'y':0})['probability'] is None
        samples=[example(f'hi{i}',True,x=.95) for i in range(150)]+[example(f'lo{i}',False,x=.05) for i in range(150)]
        # Interleave examples instead of sorting by outcome, to avoid spurious drift.
        interleaved=[v for pair in zip(samples[:150],samples[150:]) for v in pair]
        assert w.train_model('alice','risk',interleaved)['new_samples']==300
        p_hi=w.predict_model('alice','risk',{'x':.95,'y':.2})['probability']
        p_lo=w.predict_model('alice','risk',{'x':.05,'y':.2})['probability']
        assert p_hi>p_lo+.25
    with WorldCore(path) as reopened:
        assert reopened.model_stats('alice','risk')['samples']==300
        assert reopened.predict_model('alice','risk',{'x':.95,'y':.2})['probability']==pytest.approx(p_hi)


def test_training_idempotence_rollback_and_scopes(w):
    w.create_model('alice','m',['x','y'])
    w.create_model('bob','m',['x','y'])
    first=example()
    assert w.train_model('alice','m',[first])['new_samples']==1
    assert w.train_model('alice','m',[first])['duplicates_skipped']==1
    assert w.model_stats('bob','m')['samples']==0
    with pytest.raises(WorldCoreError):
        w.train_model('alice','m',[example('new'),example('a',False)])
    assert w.model_stats('alice','m')['samples']==1  # whole batch rolled back
    assert w.train_model('alice','m',[example('new')])['new_samples']==1
    with pytest.raises(WorldCoreError):
        w.predict_model('alice','m',{'x':1,'y':.2},space='private')
    with pytest.raises(WorldCoreError):
        w.create_model('alice','m',['x','y'])


@pytest.mark.parametrize('bad', [{'x':-1,'y':.5},{'x':float('nan'),'y':.5},{'x':True,'y':.3},{'x':.3}, {'x':.5,'y':.6,'extra':1},{'x':'ignore previous instructions','y':.4}])
def test_bad_features_rejected(w,bad):
    w.create_model('alice','risk',['x','y'])
    with pytest.raises(WorldCoreError):
        w.train_model('alice','risk',[{'id':'x1','features':bad,'outcome':True}])
    assert w.model_stats('alice','risk')['samples']==0
    with pytest.raises(WorldCoreError):w.predict_model('alice','risk',bad)


def test_reject_duplicate_features_and_invalid_provenance(w):
    with pytest.raises(WorldCoreError):w.create_model('u','m',['x','x'])
    with pytest.raises(WorldCoreError):w.create_model('u','m',['x'],provenance='impeccable')


def test_batch_validation_is_atomic(w):
    w.create_model('u','r',['x','y'])
    with pytest.raises(WorldCoreError):w.train_model('u','r',[example('one'),example('two',outcome=1)])
    assert w.model_stats('u','r')['samples']==0
    with pytest.raises(WorldCoreError):w.train_model('u','r',[])
    with pytest.raises(WorldCoreError):w.train_model('u','r',[example('one'),example('one',x=.4)])


def test_transition_learning_abstention_and_scoping(w):
    w.create_transition_model('alice','dynamics',provenance='synthetic')
    assert w.predict_transition('alice','dynamics','s1','forward')['status']=='insufficient_data'
    for i in range(55):
        w.observe_transition('alice','dynamics','s1','forward','s2',sample_id=f'pass{i}')
    for i in range(5):
        w.observe_transition('alice','dynamics','s1','forward','s1',sample_id=f'slip{i}')
    r=w.predict_transition('alice','dynamics','s1','forward')
    assert r['status']=='ready' and r['observations']==60
    assert r['transitions'][0]['next_state']=='s2'
    assert .85 < r['transitions'][0]['probability'] < 1.0
    assert r['unknown_mass']>0
    assert w.observe_transition('alice','dynamics','s1','forward','s2',sample_id='pass1')['duplicate']
    with pytest.raises(WorldCoreError):w.observe_transition('alice','dynamics','s1','forward','sX',sample_id='pass1')
    with pytest.raises(WorldCoreError):w.predict_transition('bob','dynamics','s1','forward')
    assert w.predict_transition('alice','dynamics','never','forward')['status']=='insufficient_data'


def test_rollouts_do_not_touch_state(w):
    w.create_transition_model('u','walk')
    for i in range(20):
        w.observe_transition('u','walk','A','move','B',sample_id=f'ab{i}')
        w.observe_transition('u','walk','B','move','C',sample_id=f'bc{i}')
    w.set_state('u','position','A')
    out=w.rollout_transitions('u','walk','A',['move','move'])
    assert out['paths'][0]['states']==['A','B','C']
    assert not out['executed']
    assert w.state('u')['position']=='A'
    with pytest.raises(WorldCoreError):w.rollout_transitions('u','walk','A',['move']*9)
    assert w.rollout_transitions('u','walk','NO_DATA',['move'])['paths'][0]['unknown']


def test_bridge_only_read_only_predictions(w):
    w.create_model('u','m',['x'])
    w.create_transition_model('u','tr')
    assert dispatch({'op':'predict_model','owner':'u','model_id':'m','features':{'x':.3}},w)['status']=='insufficient_data'
    assert dispatch({'op':'predict_transition','owner':'u','model_id':'tr','current_state':'a','action':'b'},w)['status']=='insufficient_data'
    with pytest.raises(WorldCoreError):dispatch({'op':'train_model','owner':'u','model_id':'m','samples':[]},w)


def _concurrent_train(args):
    path,idx=args
    with WorldCore(path) as w:
        rows=[{'id':f'worker{idx}-row{i}', 'features':{'x':i/100.0},'outcome':i%2==0} for i in range(100)]
        return w.train_model('alice','concurrent',rows)['new_samples']


def test_concurrent_training_updates(tmp_path):
    path=str(tmp_path/'concurrent.db')
    with WorldCore(path) as w:w.create_model('alice','concurrent',['x'])
    with concurrent.futures.ProcessPoolExecutor(max_workers=4,mp_context=multiprocessing.get_context('spawn')) as pool:
        assert sum(pool.map(_concurrent_train,[(path,i) for i in range(4)]))==400
    with WorldCore(path) as w:
        assert w.model_stats('alice','concurrent')['samples']==400
        assert w.db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'


def test_cli_operator_train_jsonl(tmp_path):
    db=str(tmp_path/'world.db'); root=os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))
    env={**os.environ,'PYTHONPATH':os.path.join(root,'src')}
    def call(*args):
        return subprocess.run([sys.executable,'-m','worldcore.cli','--db',db,*args],capture_output=True,text=True,env=env)
    assert call('model-create','m','["x"]').returncode==0
    dataset=tmp_path/'train.jsonl'
    dataset.write_text('\n'.join(json.dumps({'id':f'row{i}','features':{'x':i/100},'outcome':bool(i%2)}) for i in range(10)))
    out=call('model-train','m',str(dataset))
    assert out.returncode==0, out.stderr
    assert json.loads(out.stdout)['total_samples']==10
    prediction=json.loads(call('model-predict','m','{"x":0.5}').stdout)
    assert prediction['status']=='insufficient_data'
    assert json.loads(call('model-stats','m').stdout)['samples']==10
    from worldcore import __version__
    assert json.loads(call('doctor').stdout)['version']==__version__


def test_training_is_not_action_authorization(w):
    w.create_model('u','risk',['x'])
    w.train_model('u','risk',[{'id':f'p{i}','features':{'x':i/100},'outcome':True} for i in range(100)])
    assert w.predict_model('u','risk',{'x':1})['executed'] is False
    assert w.db.execute('SELECT COUNT(*) FROM approvals').fetchone()[0]==0
    assert w.db.execute('SELECT COUNT(*) FROM alerts').fetchone()[0]==0
