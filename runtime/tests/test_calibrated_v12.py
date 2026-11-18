from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
import random
import pytest
from worldcore import WorldCore,WorldCoreError
from worldcore.calibrated import train_temporal, predict_temporal


def observations(n=120):
    rng=random.Random(531)
    start=datetime(2024,1,1,tzinfo=timezone.utc)
    rows=[]
    for i in range(n):
        x=(i*17)%31
        at=start+timedelta(minutes=i*3)
        rows.append({'sample_id':str(i),'environment':'synthetic','action':'move','before':{'x':x},
            'after':{'x':x+10+rng.uniform(-1,1)},'source':'observed','provenance':'synthetic_test_fixture',
            'before_at':at.isoformat(),'observed_at':(at+timedelta(seconds=1)).isoformat(),
            'available_at':(at+timedelta(seconds=2)).isoformat()})
    return rows


def trained(core):
    return core.train_calibrated_dynamics('a','line',observations(),as_of='2025-01-01T00:00:00Z')


def test_temporal_partitions_are_disjoint_and_available():
    bundle=train_temporal(observations(),as_of='2025-01-01T00:00:00Z')
    action=bundle['actions']['move']
    assert action['status']=='validated'
    a,b,c=map(set,(action['train_ids'],action['calibration_ids'],action['test_ids']))
    assert not a&b and not b&c and not a&c
    assert action['calibration_available_until']<action['test_start']
    assert action['gain']>.8
    guess=predict_temporal(bundle,{'x':12},'move')
    assert guess['intervals']['x'][0] < guess['state']['x'] < guess['intervals']['x'][1]


def test_delayed_labels_cannot_leak_into_later_windows():
    rows=observations(); rows[10]['available_at']='2024-12-01T00:00:00Z'
    with pytest.raises(WorldCoreError,match='availability overlaps'):
        train_temporal(rows,as_of='2025-01-01T00:00:00Z')


def test_future_observations_are_excluded_and_synthetic_labels_ignored():
    rows=observations()
    for row in rows[80:]:row['available_at']='2030-01-01T00:00:00Z'
    bundle=train_temporal(rows,as_of='2025-01-01T00:00:00Z')
    assert bundle['samples_used']==80
    bundle=train_temporal([{**r,'source':'simulated'} for r in observations()],as_of='2025-01-01T00:00:00Z')
    assert bundle['samples_used']==0 and not bundle['actions']


@pytest.mark.parametrize('mutation', ['duplicate','nan','wrong_schema','missing_provenance','bad_time'])
def test_untrusted_observations_rejected(mutation):
    rows=observations()
    if mutation=='duplicate':rows[-1]['sample_id']=rows[0]['sample_id']
    elif mutation=='nan':rows[0]['before']['x']=float('nan')
    elif mutation=='wrong_schema':rows[-1]['after']={'y':1}
    elif mutation=='missing_provenance':rows[0]['provenance']=''
    else:rows[0]['observed_at']=rows[0]['before_at']
    with pytest.raises((ValueError,WorldCoreError)):train_temporal(rows,as_of='2025-01-01T00:00:00Z')


def test_gates_and_tenant_isolation():
    with WorldCore(':memory:') as w:
        assert trained(w)['status']=='trained'
        assert w.predict_calibrated_world('a','line',{'x':100000},'move')['reason']=='out_of_distribution'
        assert w.predict_calibrated_world('a','line',{'x':12},'move',max_width=.00001)['reason']=='interval_too_wide'
        assert w.predict_calibrated_world('a','line',{'x':12},'move',min_confidence=1)['reason']=='confidence_gate'
        assert w.predict_calibrated_world('b','line',{'x':12},'move')['status']=='abstain'
        assert w.predict_calibrated_world('a','line',{'x':12},'move',space='other')['status']=='abstain'
        with pytest.raises(WorldCoreError):w.predict_calibrated_world('a','line',{'x':12},'move',min_confidence=float('nan'))


def test_immutable_prediction_pinned_to_model_and_temporal_resolution():
    with WorldCore(':memory:') as w:
        trained(w)
        p=w.predict_calibrated_world('a','line',{'x':12},'move',persist=True)
        trained(w)
        assert p['model_version']==1
        with pytest.raises(WorldCoreError):w.resolve_calibrated_prediction('b',p['prediction_id'],{'x':22})
        with pytest.raises(WorldCoreError,match='precedes'):w.resolve_calibrated_prediction('a',p['prediction_id'],{'x':22},observed_at='2020-01-01T00:00:00Z')
        result=w.resolve_calibrated_prediction('a',p['prediction_id'],{'x':22})
        assert result['covered'] and result['model_version']==1
        assert w.resolve_calibrated_prediction('a',p['prediction_id'],{'x':22})['status']=='unchanged'
        with pytest.raises(WorldCoreError):w.resolve_calibrated_prediction('a',p['prediction_id'],{'x':23})
        assert w.calibrated_prediction_metrics('a','line')['resolved']==1


def test_concurrent_conflicting_outcomes_have_one_winner(tmp_path):
    path=tmp_path/'forecast.db'
    with WorldCore(path) as w:
        trained(w);identifier=w.predict_calibrated_world('a','line',{'x':12},'move',persist=True)['prediction_id']
    def resolve(value):
        try:
            with WorldCore(path) as w:return w.resolve_calibrated_prediction('a',identifier,{'x':value})['status']
        except WorldCoreError:return 'conflict'
    with ThreadPoolExecutor(max_workers=4) as pool:statuses=list(pool.map(resolve,range(20,28)))
    assert statuses.count('resolved')==1 and statuses.count('conflict')==7


def test_drift_forces_abstention_on_observed_misses():
    with WorldCore(':memory:') as w:
        trained(w)
        for i in range(10):
            p=w.predict_calibrated_world('a','line',{'x':12},'move',persist=True)
            assert p['status']=='predicted'
            w.resolve_calibrated_prediction('a',p['prediction_id'],{'x':500})
        assert w.predict_calibrated_world('a','line',{'x':12},'move')['reason']=='observed_coverage_drift'


def test_whatif_calibrated_scenarios_remain_nonexecuting():
    with WorldCore(':memory:') as w:
        trained(w)
        scenarios=[{'id':'first','kind':'calibrated_world','family':'line','before':{'x':12},'actions':['move']},
                   {'id':'second','kind':'calibrated_world','family':'line','before':{'x':13},'actions':['move']}]
        result=w.compare_futures('a','Compare futures',scenarios,objectives=[{'key':'x','direction':'maximize','scale':1}])
        assert result['candidate_for_review'] is None and not result['action_executed']
        assert result['scenarios'][0]['evidence']['prediction']['intervals']
        scenarios[0]['actions']=['move','move']
        with pytest.raises(WorldCoreError):w.compare_futures('a','Uncalibrated chain',scenarios,objectives=[])


def test_prediction_interval_property_for_in_range_states():
    bundle=train_temporal(observations(),as_of='2025-01-01T00:00:00Z')
    for x in range(31):
        result=predict_temporal(bundle,{'x':x},'move')
        low,high=result['intervals']['x']
        assert low<=result['state']['x']<=high and high>=low
    shuffled=list(reversed(observations()))
    assert train_temporal(shuffled,as_of='2025-01-01T00:00:00Z')['dataset_sha256']==bundle['dataset_sha256']


def test_bridge_cannot_upgrade_outcome_provenance():
    from worldcore.bridge import dispatch
    with WorldCore(':memory:') as w:
        run=w.compare_futures('a','provenance',[{'id':'a','actions':[]},{'id':'b','actions':[]}],objectives=[])
        result=dispatch({'op':'whatif_verify','owner':'a','run_id':run['run_id'],'selected':'a','observed':{},'source':'host_verified'},w)
        assert result['source']=='user_reported'
