import json
import os
import subprocess
import sys
import pytest
from worldcore.engine import WorldCore, WorldCoreError


def batch(prefix, start=0, n=25):
    return [{'id':f'{prefix}{i}', 'features':{'x':(i%50)/50}, 'outcome':i%3==0} for i in range(start,start+n)]


def test_holdout_does_not_mutate_and_blocks_overlap(tmp_path):
    path=tmp_path/'models.db'
    with WorldCore(path) as w:
        w.create_model('u','risk',['x'],provenance='synthetic')
        w.train_model('u','risk',batch('train',n=110))
        old=w.model_stats('u','risk')
        result=w.evaluate_model('u','risk',batch('test'),min_samples=100)
        assert result['holdout_count']==25
        assert 0<=result['brier']<=1
        assert 0<=result['expected_calibration_error_10bin']<=1
        assert result['training_overlap_checked'] and not result['mutated']
        assert w.model_stats('u','risk')==old
        with pytest.raises(WorldCoreError,match='overlap'):
            w.evaluate_model('u','risk',batch('train',n=25))
        with pytest.raises(WorldCoreError,match='duplicate'):
            w.evaluate_model('u','risk',batch('new',n=24)+batch('new',n=1))
        with pytest.raises(WorldCoreError):
            w.evaluate_model('other','risk',batch('test'))
        assert w.db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'


def test_holdout_requires_trained_model(tmp_path):
    with WorldCore(tmp_path/'db') as w:
        w.create_model('u','r',['x'])
        with pytest.raises(WorldCoreError, match='insufficient'):
            w.evaluate_model('u','r',batch('test'))


def test_transition_evaluation_and_overlap(tmp_path):
    with WorldCore(tmp_path/'db') as w:
        w.create_transition_model('u','m',provenance='synthetic')
        for i in range(50):
            w.observe_transition('u','m','idle','go','active',sample_id=f'train{i}')
        holdout=[{'id':f'test{i}', 'current_state':'idle','action':'go','next_state':'active'} for i in range(30)]
        result=w.evaluate_transitions('u','m',holdout)
        assert result['coverage']==1
        assert result['top1_accuracy']==1
        assert result['scored']==30
        assert result['mutated'] is False
        with pytest.raises(WorldCoreError,match='overlap'):
            w.evaluate_transitions('u','m',[dict(holdout[0],id='train0')]+holdout[1:])
        with pytest.raises(WorldCoreError):
            w.evaluate_transitions('not-u','m',holdout)


def test_new_evaluation_cli(tmp_path):
    root=os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))
    env={**os.environ,'PYTHONPATH':os.path.join(root,'src')}
    db=str(tmp_path/'demo.db')
    def cmd(*args):
        return subprocess.run([sys.executable,'-m','worldcore.cli','--db',db,*args],env=env,text=True,capture_output=True)
    assert cmd('model-create','risk','["x"]').returncode==0
    path=tmp_path/'train.jsonl'
    path.write_text('\n'.join(json.dumps(x) for x in batch('train',n=110)))
    assert cmd('model-train','risk',str(path)).returncode==0
    hold=tmp_path/'holdout.jsonl'
    hold.write_text('\n'.join(json.dumps(x) for x in batch('test')))
    out=cmd('model-evaluate','risk',str(hold))
    assert out.returncode==0,out.stderr
    assert json.loads(out.stdout)['holdout_count']==25
    wrong=cmd('model-evaluate','risk',str(path))
    assert wrong.returncode==2
    assert 'overlap' in wrong.stderr


def test_drift_detection_conservative_and_rejects_garbage():
    from worldcore.learning import LearningMixin
    a={'model_id':'r','holdout_count':4000,'training_overlap_checked':True,'model_fingerprint':'abc','brier':.15}
    b={'model_id':'r','holdout_count':4000,'training_overlap_checked':True,'model_fingerprint':'abc','brier':.48}
    assert LearningMixin.detect_drift(a,b)['status']=='alarm'
    assert LearningMixin.detect_drift(a,a)['status']=='no_alarm'
    with pytest.raises(WorldCoreError):LearningMixin.detect_drift(a,dict(b,model_id='other'))
    with pytest.raises(WorldCoreError):LearningMixin.detect_drift(a,dict(b,holdout_count=2))
    with pytest.raises(WorldCoreError):LearningMixin.detect_drift(a,b,alpha=1)


def test_drift_rejects_changed_model_weights():
    from worldcore.learning import LearningMixin
    a={'model_id':'r','holdout_count':1000,'training_overlap_checked':True,'model_fingerprint':'a','brier':.15}
    with pytest.raises(WorldCoreError,match='changed'):
        LearningMixin.detect_drift(a,dict(a,model_fingerprint='b',brier=.5))
