"""Data changes, immutable code: prospective selection and outcome-driven rollback."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
import hashlib
from pathlib import Path
import random
import pytest
from worldcore import WorldCore,WorldCoreError
from worldcore.bridge import dispatch


def observations(batch=0,offset=10):
    start=datetime(2024 if batch==0 else 2025,6,1,tzinfo=timezone.utc)
    rng=random.Random(531);rows=[]
    for i in range(120):
        at=start+timedelta(minutes=3*i);x=(i*17)%31
        rows.append({'sample_id':f'b{batch}_{i}','environment':'synthetic','action':'move',
                     'before':{'x':x},'after':{'x':x+offset+rng.uniform(-1,1)},
                     'source':'observed','provenance':'synthetic_fixture_not_real_user',
                     'before_at':at.isoformat(),'observed_at':(at+timedelta(seconds=1)).isoformat(),
                     'available_at':(at+timedelta(seconds=2)).isoformat()})
    return rows


def refresh(w,batch=0,offset=10):
    return w.refresh_adaptive_world('a','family',observations(batch,offset),
        as_of=f'{2025 if batch==0 else 2026}-01-01T00:00:00Z')


def test_bootstrap_then_fresh_improvement_and_version_pinning():
    with WorldCore(':memory:') as w:
        assert refresh(w)['version']==1
        forecast=w.predict_calibrated_world('a','family',{'x':12},'move',persist=True)
        assert refresh(w,1,12)['version']==2
        assert w.adaptive_status('a','family')['head']['previous']==1
        assert w.predict_calibrated_world('a','family',{'x':12},'move')['model_version']==2
        assert forecast['model_version']==1
        assert w.adaptive_status('other','family')['head'] is None
        assert w.adaptive_status('a','family',space='other')['head'] is None


def test_no_improvement_rejected_and_holdout_consumed():
    with WorldCore(':memory:') as w:
        refresh(w)
        assert refresh(w,1)['reason']=='no_demonstrated_improvement'
        result=w.refresh_adaptive_world('a','family',observations(1),as_of='2026-02-01T00:00:00Z')
        assert result['reason']=='evaluation_already_consumed'
        assert w.predict_calibrated_world('a','family',{'x':12},'move')['model_version']==1


def test_old_or_future_labels_cannot_force_replacement():
    with WorldCore(':memory:') as w:
        refresh(w)
        result=w.refresh_adaptive_world('a','family',observations(0,12),as_of='2026-01-01T00:00:00Z')
        assert result['reason'] in ('evaluation_already_consumed','holdout_must_follow_previous_cutoff')
        rows=observations(1,12)
        for row in rows:row['available_at']='2030-01-01T00:00:00Z'
        assert w.refresh_adaptive_world('a','family',rows,as_of='2026-01-01T00:00:00Z')['status']=='rejected'
        with pytest.raises(WorldCoreError,match='future'):
            w.refresh_adaptive_world('a','family',rows,as_of='2031-01-01T00:00:00Z')


@pytest.mark.parametrize('previous',[False,True])
def test_verified_failures_automatically_rollback_or_suspend(previous):
    with WorldCore(':memory:') as w:
        refresh(w)
        if previous:refresh(w,1,12)
        ids=[w.predict_calibrated_world('a','family',{'x':12},'move',persist=True)['prediction_id'] for _ in range(10)]
        for identifier in ids:w.resolve_calibrated_prediction('a',identifier,{'x':1000},source='host_verified')
        status=w.adaptive_status('a','family')
        assert status['head']['version']==(1 if previous else None)
        assert status['events'][0]['status']==('rolled_back' if previous else 'suspended')
        if not previous:
            # Legacy research training cannot bypass a suspended adaptive head.
            w.train_calibrated_dynamics('a','family',observations(),as_of='2025-01-01T00:00:00Z')
            assert w.predict_calibrated_world('a','family',{'x':12},'move')['reason']=='adaptive_model_suspended'


def test_user_reported_failures_do_not_change_active_version():
    with WorldCore(':memory:') as w:
        refresh(w);refresh(w,1,12)
        ids=[w.predict_calibrated_world('a','family',{'x':12},'move',persist=True)['prediction_id'] for _ in range(10)]
        for identifier in ids:w.resolve_calibrated_prediction('a',identifier,{'x':1000})
        assert w.adaptive_status('a','family')['head']['version']==2


def test_failed_review_rolls_back_outcome_transaction(monkeypatch):
    with WorldCore(':memory:') as w:
        refresh(w)
        p=w.predict_calibrated_world('a','family',{'x':12},'move',persist=True)
        def crash(*args,**kwargs):raise RuntimeError('injected review failure')
        monkeypatch.setattr(w,'_review_adaptive_world_locked',crash)
        with pytest.raises(RuntimeError,match='injected'):
            w.resolve_calibrated_prediction('a',p['prediction_id'],{'x':1000},source='host_verified')
        assert w.db.execute('SELECT actual_json FROM calibrated_forecasts').fetchone()[0] is None
        assert w.adaptive_status('a','family')['head']['version']==1


def test_schema_change_and_partial_action_model_do_not_replace():
    with WorldCore(':memory:') as w:
        refresh(w)
        rows=observations(1,12)
        for row in rows:
            row['before']['y']=row['before']['x'];row['after']['y']=row['after']['x']
        assert w.refresh_adaptive_world('a','family',rows,as_of='2026-01-01T00:00:00Z')['reason']=='replacement_state_schema_differs'
        rows=observations(1,12)
        for row in rows:row['sample_id']='fresh_'+row['sample_id']
        # Fresh timestamps are needed after the rejected schema evaluation.
        for row in rows:
            for key in ('before_at','observed_at','available_at'):
                row[key]=row[key].replace('2025','2026')
        rows.append({**rows[0],'sample_id':'rare','action':'rare_action'})
        assert w.refresh_adaptive_world('a','family',rows,as_of='2026-10-01T00:00:00Z')['reason']=='partial_action_validation'
        assert w.adaptive_status('a','family')['head']['version']==1


def test_two_connections_serialize_same_ingestion(tmp_path):
    db=tmp_path/'world.db'
    with WorldCore(db):pass
    def run(_):
        with WorldCore(db) as w:return refresh(w)['status']
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,range(2)))
    assert sorted(results)==['deferred','promoted']
    with WorldCore(db) as w:assert w.db.execute('SELECT COUNT(*) FROM calibrated_dynamics').fetchone()[0]==1


def test_procedures_are_immutable_data_and_need_verified_evidence():
    with WorldCore(':memory:') as w:
        w.register_adaptive_procedure('a','meeting','prepare',['Prepare a draft; never send without authority'])
        with pytest.raises(WorldCoreError,match='immutable'):
            w.register_adaptive_procedure('a','meeting','prepare',['Execute arbitrary code'])
        for i in range(30):
            result=w.record_adaptive_procedure_outcome('a','meeting','prepare',f'user{i}',True)
        assert result['status']=='abstain'
        for i in range(20):
            result=w.record_adaptive_procedure_outcome('a','meeting','prepare',f'host{i}',True,source='host_verified')
        assert result['status']=='recommended' and result['execution_authorized'] is False
        with pytest.raises(WorldCoreError,match='immutable'):
            w.record_adaptive_procedure_outcome('a','meeting','prepare','user0',True,source='host_verified')
        assert w.recommend_adaptive_procedure('b','meeting')['status']=='abstain'
        for i in range(40):
            result=w.record_adaptive_procedure_outcome('a','meeting','prepare',f'failure{i}',False,source='host_verified')
        assert result['status']=='abstain'


def test_adaptation_never_writes_source_or_grants_transport_authority(tmp_path):
    source=Path(__file__).resolve().parents[1]/'src/worldcore'
    before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.glob('*.py')}
    with WorldCore(tmp_path/'world.db') as w:
        refresh(w)
        assert not dispatch({'op':'adaptive_status','owner':'a','family':'family'},w)['execution_authorized']
        for op in ('refresh_adaptive_world','register_adaptive_procedure','record_adaptive_procedure_outcome'):
            with pytest.raises(WorldCoreError):dispatch({'op':op,'owner':'a'},w)
    assert before=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.glob('*.py')}


def test_failed_validation_also_consumes_holdout():
    with WorldCore(':memory:') as w:
        refresh(w)
        rows=observations(1)
        for row in rows:row['after']=dict(row['before'])
        assert w.refresh_adaptive_world('a','family',rows,as_of='2026-01-01T00:00:00Z')['reason']=='no_validated_actions'
        result=w.refresh_adaptive_world('a','family',observations(1,12),as_of='2026-02-01T00:00:00Z')
        assert result['reason']=='evaluation_already_consumed'
