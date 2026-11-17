"""Temporal holdout, configurable thresholds, per-environment dynamics."""
from datetime import datetime, timedelta, timezone
import pytest
from worldcore import WorldCore
from worldcore.dynamics import train_family_dynamics, train_environment_dynamics


def _iso(i):
    return (datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=i)).isoformat()


def traj_env():
    rows=[]
    for env_index,env in enumerate(('world_a','world_b','world_c','world_d')):
        for action,dx,dy in [('right',1,0),('left',-1,0),('up',0,1)]:
            for i in range(30):
                x=(i*7+env_index*11)%51;y=(i*3+env_index*5)%13
                rows.append({'environment':env,'action':action,'before':{'x':float(x),'y':float(y)},
                             'after':{'x':float(x+dx),'y':float(y+dy)},'source':'observed',
                             'observed_at':_iso(env_index*30+i)})
    return rows


def traj_temporal_linear():
    """Shared law over time across three envs; later window is holdout."""
    rows=[]
    t=0
    for env in ('alpha','beta','gamma'):
        for i in range(40):
            x=float(i)
            rows.append({'environment':env,'action':'right','before':{'x':x},
                         'after':{'x':x+1.0},'source':'observed','observed_at':_iso(t)})
            t+=1
    return rows


def traj_one_env(env='solo', n=60):
    rows=[]
    for i in range(n):
        x=float(i)
        rows.append({'environment':env,'action':'right','before':{'x':x},
                     'after':{'x':x+2.0},'source':'observed','observed_at':_iso(i)})
    return rows


def test_default_holdout_still_environment_group():
    d=train_family_dynamics(traj_env())
    assert d['holdout_mode']=='environment'
    assert d['validation']=='group_holdout_by_environment'
    for a,r in d['actions'].items():
        assert r['status']=='validated'
        assert r['model']['holdout_environment']=='world_d'
        assert r['model']['holdout_mode']=='environment'


def test_temporal_holdout_uses_later_window():
    rows=traj_temporal_linear()
    d=train_family_dynamics(rows, holdout_mode='temporal', min_environments=3)
    assert d['validation']=='temporal_holdout_by_observed_at'
    r=d['actions']['right']
    assert r['status']=='validated'
    assert r['model']['holdout_mode']=='temporal'
    assert r['model']['holdout_from'] > r['model']['train_to']
    assert abs(r['model']['heldout_mae']) < 0.05
    assert r['model']['improvement_vs_persistence'] >= 0.10


def test_temporal_requires_timestamps():
    rows=[{k:v for k,v in r.items() if k!='observed_at'} for r in traj_temporal_linear()]
    d=train_family_dynamics(rows, holdout_mode='temporal', min_environments=1)
    assert d['count_observed']==0
    assert d['actions']=={}


def test_configurable_min_environments():
    rows=[r for r in traj_env() if r['environment'] in ('world_a','world_b')]
    # with default 3 → abstain
    d=train_family_dynamics(rows)
    assert d['actions']['right']['status']=='abstain'
    assert d['actions']['right']['reason']=='need_3_independent_environments'
    # with min_environments=2 and enough rows → can validate via env holdout (held=world_b)
    d2=train_family_dynamics(rows, min_environments=2)
    assert d2['actions']['right']['status'] in ('validated','rejected_no_baseline_gain','abstain')
    assert d2['min_environments']==2


def test_configurable_thresholds_abstain():
    rows=traj_temporal_linear()
    d=train_family_dynamics(rows, holdout_mode='temporal', min_train=200, min_holdout=50)
    assert d['actions']['right']['status']=='abstain'
    assert d['actions']['right']['reason']=='insufficient_temporal_train_test'


def test_invalid_holdout_mode():
    with pytest.raises(ValueError):
        train_family_dynamics(traj_env(), holdout_mode='shuffle')


def test_per_environment_learner_validates_solo_repo():
    rows=traj_one_env('nova_like', n=60)
    d=train_environment_dynamics(rows, min_train=20, min_holdout=8)
    assert d['validation']=='per_environment_temporal_holdout'
    env=d['environments']['nova_like']
    r=env['actions']['right']
    assert r['status']=='validated'
    assert r['model']['holdout_environment']=='nova_like'
    assert abs(r['model']['heldout_mae']) < 0.05


def test_per_environment_rejects_environment_holdout_mode():
    d=train_environment_dynamics(traj_one_env(), holdout_mode='environment')
    assert d['validation']=='unsupported_for_per_environment'
    assert d['environments']=={}


def test_worldcore_temporal_and_per_env(tmp_path):
    path=tmp_path/'dyn.db'
    with WorldCore(path) as w:
        shared=w.train_shared_dynamics('valerio','motion',traj_temporal_linear(),
                                       holdout_mode='temporal', min_environments=3)
        assert shared['status']=='trained'
        out=w.predict_shared_dynamics('valerio','motion',{'x':10.0},'right')
        assert out['status']=='predicted' and abs(out['state']['x']-11.0)<0.1

        per=w.train_per_environment_dynamics('valerio','repo',traj_one_env('nova', n=50))
        assert per['status']=='trained'
        assert per['environments']['nova']['status']=='trained'
        p=w.predict_environment_dynamics('valerio','repo','nova',{'x':5.0},'right')
        assert p['status']=='predicted' and abs(p['state']['x']-7.0)<0.1
        # other env abstains
        assert w.predict_environment_dynamics('valerio','repo','other',{'x':5.0},'right')['status']=='abstain'


def test_environment_mode_still_default_on_worldcore(tmp_path):
    with WorldCore(tmp_path/'e.db') as w:
        r=w.train_shared_dynamics('a','cartesian',traj_env())
        assert r['status']=='trained'
        assert r['validation']['holdout_mode']=='environment'
