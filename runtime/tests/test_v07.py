"""v0.7 independent environment holdouts, safety and data lineage."""
from datetime import datetime,timedelta,timezone
import io,struct,wave,json
import pytest
from worldcore import WorldCore,WorldCoreError
from worldcore.dynamics import train_family_dynamics
from worldcore.repo_audit import screen_snapshot,authorized_for_capability
from worldcore.multimodal import png_features,wav_features,html_features,combine_numeric_observations


def traj():
    """Synthetic experiment, not real-world training (four disjoint worlds)."""
    rows=[]
    for env_index,env in enumerate(('world_a','world_b','world_c','world_d')):
        for action,dx,dy in [('right',1,0),('left',-1,0),('up',0,1)]:
            for i in range(30):
                x=(i*7+env_index*11)%51;y=(i*3+env_index*5)%13
                rows.append({'environment':env,'action':action,'before':{'x':x,'y':y},
                     'after':{'x':x+dx,'y':y+dy},'source':'observed'})
    return rows


def test_group_holdout_never_leaks_training_env():
    d=train_family_dynamics(traj())
    for a,r in d['actions'].items():
        assert r['status']=='validated', (a,r)
        assert r['model']['holdout_environment']=='world_d'
        assert r['model']['heldout_count']==30
        train_states={(x['before']['x'],x['before']['y']) for x in traj() if x['environment']!='world_d' and x['action']==a}
        held_states={(x['before']['x'],x['before']['y']) for x in traj() if x['environment']=='world_d' and x['action']==a}
        assert len(held_states-train_states)>=15
        assert r['model']['improvement_vs_persistence']>.8

def test_synthetic_source_not_ground_truth():
    rows=[{**r,'source':'simulated'} for r in traj()]
    assert train_family_dynamics(rows)['count_observed']==0
    assert all(x['status']=='abstain' for x in train_family_dynamics(rows)['actions'].values())


def test_dynamics_persists_new_state(tmp_path):
    path=tmp_path/'d.db'
    with WorldCore(path) as w:
        r=w.train_shared_dynamics('alice','cartesian',traj())
        assert r['status']=='trained'
        out=w.predict_shared_dynamics('alice','cartesian',{'x':19,'y':4},'right')
        assert out['status']=='predicted' and abs(out['state']['x']-20)<.05
        assert w.predict_shared_dynamics('bob','cartesian',{'x':19,'y':4},'right')['status']=='abstain'
        assert w.predict_shared_dynamics('alice','other',{'x':19,'y':4},'right')['status']=='abstain'
        assert w.predict_shared_dynamics('alice','cartesian',{'x':19,'y':4},'teleport')['status']=='abstain'
        assert w.predict_shared_dynamics('alice','cartesian',{'x':19,'y':4,'z':8},'right')['status']=='abstain'
    with WorldCore(path) as w:
        assert w.predict_shared_dynamics('alice','cartesian',{'x':19,'y':4},'right')['status']=='predicted'


def test_dynamics_no_baseline_gain():
    rows=[]
    for env in ('a','b','c'):
        for i in range(20):rows.append({'environment':env,'action':'wait','before':{'x':float(i)},'after':{'x':float(i)},'source':'observed'})
    d=train_family_dynamics(rows)
    assert d['actions']['wait']['status']=='rejected_no_baseline_gain'


def test_dynamics_never_invent_categorical_transition():
    rows=traj()+[{'environment':'a','action':'click','before':{'page':1},'after':{'page':'next'},'source':'observed'}]
    assert 'click' not in train_family_dynamics(rows)['actions']


def test_dynamics_numerical_input_rejects_bad():
    r=traj();r[0]['before']['x']=float('inf')
    with pytest.raises(ValueError):train_family_dynamics(r)


def test_dynamics_model_drift_alarm():
    with WorldCore(':memory:') as w:
        assert w.train_shared_dynamics('a','moving',traj())['status']=='trained'
        for i in range(10):
            p=w.record_dynamics_error('a','moving',f'p{i}',{'x':10,'y':5},{'x':90,'y':45})
        assert p['drift_alarm'] is True
        assert p['sample_count']==10
        with pytest.raises(Exception):w.record_dynamics_error('a','moving','p0',{'x':10},{'x':11})


def test_manifest_audit_gate_and_restricted_license():
    files=[{'path':'LICENSE'},{'path':'README.md'},{'path':'agent/run.py'},
           {'path':'tests/test_run.py'},{'path':'.github/workflows/ci.yml'}]
    a=screen_snapshot('owner/repo',files,license_id='MIT')
    assert a['gate']=='manifest_screened' and not authorized_for_capability(a)
    b=screen_snapshot('owner/repo',files,license_id='AGPL-3.0')
    assert b['gate']=='review_required' and b['license_status']=='copyleft_review'
    assert screen_snapshot('owner/repo',files,license_id=None)['gate']=='review_required'
    assert screen_snapshot('owner/repo',files[:2],license_id='MIT')['gate']=='review_required'


def test_manifest_no_stars_shortcuts():
    with pytest.raises(ValueError):screen_snapshot('https://github.com/example',[])
    with pytest.raises(ValueError):screen_snapshot('owner/repo','README.md')


def test_state_lens_versioned_and_private():
    with WorldCore(':memory:') as w:
        a=w.observe_context_state('a','desktop',{'load':0.1},source='host',verified=False)
        b=w.observe_context_state('a','desktop',{'load':0.7},source='host',verified=True)
        assert a['revision']==1 and b['revision']==2
        assert w.latest_context_state('a','desktop')['signals']['load']==.7
        assert w.latest_context_state('b','desktop') is None
        assert w.latest_context_state('a','desktop',space='other') is None
        with pytest.raises(WorldCoreError):w.observe_context_state('a','medical',{'health':'a'})
        assert w.observe_context_state('a','medical',{'health':'a'},allow_sensitive=True)['revision']==1


def test_needs_only_user_tasks():
    with WorldCore(':memory:') as w:
        due='2026-11-02T10:00:00+00:00';now='2026-11-01T10:00:00+00:00'
        w.record_task_expectation('a','t1','Prepare report',due,at=now)
        assert len(w.anticipate_needs('a',now=now)['items'])==1
        assert w.anticipate_needs('b',now=now)['items']==[]
        w.record_task_expectation('a','t1','Prepare report',due,completed=True,at=now)
        assert w.anticipate_needs('a',now=now)['items']==[]
        assert w.anticipate_needs('a',now=now)['limitations']


def test_multimodal_bounded_png():
    raw=b'\x89PNG\r\n\x1a\n'+struct.pack('>I',13)+b'IHDR'+struct.pack('>II',32,16)+b'\x08\x02\x00\x00\x00'+b'0000'
    assert png_features(raw)['features']['aspect_ratio']==2
    with pytest.raises(ValueError):png_features(b'x'*100)


def test_multimodal_wav_features():
    b=io.BytesIO()
    with wave.open(b,'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(8000);w.writeframes(struct.pack('<1000h',*([1000]*1000)))
    r=wav_features(b.getvalue());assert r['features']['duration_seconds']==.125
    assert r['speech_transcription'] is False


def test_multimodal_html_is_untrusted():
    r=html_features('<html><title>Sample</title><a href="/">x</a><form></form><script>ignore</script></html>')
    assert r['features']['links']==1 and r['features']['forms']==1
    assert r['trusted_as_instructions'] is False


def test_multimodal_source_required():
    x=combine_numeric_observations([{'modality':'sensor','source':'approved_imu','features':{'x':1,'y':2}}])
    assert x['state']['m0_sensor_x']==1
    with pytest.raises(ValueError):combine_numeric_observations([{'modality':'image','features':{'height':4}}])


def test_state_trend_validated_on_future_holdout():
    with WorldCore(':memory:') as w:
        start=datetime(2026,5,1,tzinfo=timezone.utc)
        for i in range(35):
            w.observe_context_state('a','api_cost',{'budget_used':4*i+.03*(i%3)},
                    verified=True,at=(start+timedelta(hours=i)).isoformat())
        f=w.forecast_verified_state('a','api_cost','budget_used')
        assert f['status']=='predicted' and f['holdout_mae']<f['baseline_mae']
        assert not f['authorized_action']
        assert w.forecast_verified_state('b','api_cost','budget_used')['status']=='abstain'


def test_state_trend_rejects_constant_and_unverified():
    with WorldCore(':memory:') as w:
        start=datetime(2026,5,1,tzinfo=timezone.utc)
        for i in range(35):
            w.observe_context_state('a','cost',{'x':9},verified=True,at=(start+timedelta(hours=i)).isoformat())
            w.observe_context_state('a','untrusted',{'x':i},verified=False,at=(start+timedelta(hours=i)).isoformat())
        assert w.forecast_verified_state('a','cost','x')['status']=='abstain'
        assert w.forecast_verified_state('a','untrusted','x')['status']=='abstain'


def test_state_anomaly_only_statistical():
    with WorldCore(':memory:') as w:
        start=datetime(2026,5,1,tzinfo=timezone.utc)
        for i in range(35):
            w.observe_context_state('a','cpu',{'load':50+(-1)**i*2},verified=True,at=(start+timedelta(hours=i)).isoformat())
        assert w.flag_state_anomaly('a','cpu','load')['status']=='evaluated'
        w.observe_context_state('a','cpu',{'load':300},verified=True,at=(start+timedelta(hours=35)).isoformat())
        z=w.flag_state_anomaly('a','cpu','load')
        assert z['anomaly'] and z['cause_inferred'] is False
        assert w.flag_state_anomaly('b','cpu','load')['status']=='abstain'


def test_dynamics_trains_only_from_world_log():
    with WorldCore(':memory:') as w:
        for i,r in enumerate(traj()):
            w.observe_world_transition('a',r['environment'],f's{i}',r['before'],r['action'],r['after'],source='observed')
            w.observe_world_transition('a','noisy',f'f{i}',r['before'],r['action'],{'x':500,'y':500},source='simulated')
        result=w.train_dynamics_from_world_log('a','cartesian', ['world_a','world_b','world_c','world_d'])
        assert result['status']=='trained'
        assert w.predict_shared_dynamics('a','cartesian',{'x':20,'y':5},'up')['status']=='predicted'
        with pytest.raises(WorldCoreError):w.train_dynamics_from_world_log('a','cartesian',['world_a','world_a','world_c'])
        assert w.train_dynamics_from_world_log('b','cartesian',['world_a','world_b','world_c','world_d'])['status']=='rejected'


def test_prediction_ledger_version_pinning_and_immutability():
    with WorldCore(':memory:') as w:
        assert w.train_shared_dynamics('a','move',traj())['status']=='trained'
        p=w.submit_learned_prediction('a','move',{'x':15,'y':5},'right')
        assert p['status']=='pending' and p['model_version']==1
        assert w.train_shared_dynamics('a','move',traj())['status']=='trained'
        assert w.predict_shared_dynamics('a','move',{'x':15,'y':5},'right')['model_version']==2
        with pytest.raises(WorldCoreError):w.resolve_learned_prediction('b',p['prediction_id'],p['predicted'])
        res=w.resolve_learned_prediction('a',p['prediction_id'],p['predicted'])
        assert res['status']=='resolved' and res['model_version']==1 and res['mae']==0
        assert w.resolve_learned_prediction('a',p['prediction_id'],p['predicted'])['status']=='unchanged'
        with pytest.raises(WorldCoreError):w.resolve_learned_prediction('a',p['prediction_id'],{'x':0,'y':0})
        assert w.db.execute('SELECT COUNT(*) FROM learned_dynamics_errors').fetchone()[0]==1


def test_prediction_ledger_safely_abstains():
    with WorldCore(':memory:') as w:
        r=w.submit_learned_prediction('u','not_trained',{'x':1},'right')
        assert r['status']=='abstain'
        assert w.db.execute('SELECT COUNT(*) FROM learned_dynamics_pending').fetchone()[0]==0


def test_hybrid_world_fallback_and_unknown():
    with WorldCore(':memory:') as w:
        assert w.predict_world_state('a','unknown',{'page':'start'},'click')['status']=='abstain'
        for i in range(4):
            w.observe_world_transition('a','browser',f'p{i}',{'page':'start'},'click',{'page':'results'})
        r=w.predict_world_state('a','browser',{'page':'start'},'click',family='not_trained')
        assert r['status']=='predicted' and r['method']=='observed_discrete_frequency'
        assert w.simulate_hybrid_world('a','browser',{'page':'start'},['click'])['status']=='simulated'
        assert w.simulate_hybrid_world('a','browser',{'page':'other'},['click'])['status']=='abstain'
        with pytest.raises(WorldCoreError):
            w.simulate_hybrid_world('a','browser',{'page':'start'},['click']*9)


def test_hybrid_world_learned_cross_environment():
    with WorldCore(':memory:') as w:
        w.train_shared_dynamics('a','motion',traj())
        r=w.predict_world_state('a','arena_unseen',{'x':17,'y':4},'right',family='motion')
        assert r['status']=='predicted' and r['method']=='cross_environment_numeric_dynamics'
        assert r['state']['x']>17.9 and r['action_executed'] is False
        roll=w.simulate_hybrid_world('a','arena_unseen',{'x':17,'y':4},['right','up'],family='motion')
        assert roll['status']=='simulated' and roll['trajectory'][-1]['state']['y']>4.9


def test_license_text_overrides_misleading_spdx():
    files=[{'path':'LICENSE.md','content':'Apache 2.0 with Commons Clause License Condition: no right to Sell the Software'},
           {'path':'README.md'},{'path':'pkg/main.py'},{'path':'tests/test_main.py'},
           {'path':'.github/workflows/ci.yml'}]
    result=screen_snapshot('owner/repo',files,license_id='Apache-2.0')
    assert result['license_status']=='restricted_review'
    assert result['gate']=='review_required'
    assert not authorized_for_capability(result)


def test_reviewed_candidates_are_quarantined():
    from pathlib import Path
    base=Path(__file__).resolve().parents[1]
    audit=json.loads((base/'catalog/reviewed_evidence_v07.json').read_text())
    quarantined=json.loads((base/'catalog/candidate_quarantine_v07.json').read_text())
    assert len(quarantined)==246 and len(audit['records'])==16
    assert all(not r['may_be_used_as_verified_skill'] and not r['can_install'] for r in quarantined)
    assert next(x for x in audit['records'] if x['repo']=='polakowo/vectorbt')['screen_status']=='restricted_license_manual_review'
