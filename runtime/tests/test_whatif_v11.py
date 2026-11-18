import pytest
from worldcore import WorldCore, WorldCoreError

@pytest.fixture
def core(tmp_path):
    with WorldCore(tmp_path/'whatif.db') as w:
        w.set_state('alpha','hours',12)
        w.set_state('alpha','cost',100)
        yield w

def cases():
    return [
     {'id':'slow','kind':'state','actions':[{'op':'add','key':'cost','value':20}]},
     {'id':'fast','kind':'state','actions':[{'op':'add','key':'cost','value':-10}]},
    ]

def goals():
    return [{'key':'cost','direction':'minimize','scale':10,'weight':2}]

def test_evidence_not_authority_and_non_destructive(core):
    r=core.compare_futures('alpha','What if?',cases(), objectives=goals())
    assert r['ranking']==['fast','slow']
    assert r['candidate_for_review'] is None
    assert r['authority']['host_approval_required'] is True
    assert r['action_executed'] is False
    assert core.state('alpha')['cost']==100

def test_snapshot_persistence_and_observation_error(core):
    r=core.compare_futures('alpha','A vs B',cases(),objectives=goals())
    assert core.whatif_history('alpha')[0]['id']==r['run_id']
    v=core.verify_whatif('alpha',r['run_id'],'fast',{'cost':91,'hours':12})
    assert v['absolute_errors']['cost']==1 and v['causal_conclusion'] is False
    with pytest.raises(WorldCoreError):core.verify_whatif('alpha',r['run_id'],'slow',{'cost':120})
    assert core.verify_whatif('alpha',r['run_id'],'fast',{'cost':91,'hours':12})['status']=='unchanged'

def test_failures_and_incomplete_objective(core):
    s=[{'id':'over','actions':[{'op':'add','key':'cost','value':30}]},
       {'id':'none','actions':[]}]
    r=core.compare_futures('alpha','Budget',s,objectives=goals(),failure_conditions=[{'key':'cost','op':'>','threshold':120}])
    assert len(r['scenarios'][0]['failure_futures'])==1
    r2=core.compare_futures('alpha','Unknown',cases(),objectives=[{'key':'missing','direction':'maximize','scale':1}])
    assert r2['ranking']==[]

def test_owner_and_space_separation(core):
    r=core.compare_futures('alpha','Private',cases(),objectives=goals(),space='default')
    assert core.whatif_history('bravo')==[]
    assert core.whatif_history('alpha',space='other')==[]
    with pytest.raises(WorldCoreError):core.verify_whatif('bravo',r['run_id'],'fast',{})

def test_reject_unknown_world_and_injection(core):
    world=[{'id':'A','kind':'world','environment':'unknown','before':{'n':1},'actions':['run']},
           {'id':'B','kind':'state','actions':[]}]
    r=core.compare_futures('alpha','Unknown environment',world,objectives=goals())
    assert r['scenarios'][0]['status']=='abstain' and r['ranking']==[]
    for bad in [{'id':'x', 'actions':[{'op':'shell','key':'cost','value':'rm -rf /'}]},
                {'id':'x','actions':[{'op':'set','key':'bad key','value':1}]}]:
        with pytest.raises(WorldCoreError):core.compare_futures('alpha','Bad',[bad,{'id':'y','actions':[]}],objectives=[])

def test_validation_and_duplicate_ids(core):
    with pytest.raises(WorldCoreError):core.compare_futures('alpha','q',[cases()[0],cases()[0]],objectives=[])
    with pytest.raises(WorldCoreError):core.compare_futures('alpha','q',cases(),objectives=[{'key':'cost','direction':'maximize','scale':0}])

def test_simulated_data_cannot_create_world_evidence(core):
    for i in range(5):
        core.observe_world_transition('alpha','env',f'id{i}',{'n':1},'open',{'n':2},source='simulated')
    r=core.compare_futures('alpha','No facts',[{'id':'A','kind':'world','environment':'env','before':{'n':1},'actions':['open']},
       {'id':'B','kind':'state','actions':[]}],objectives=[])
    assert r['scenarios'][0]['status']=='abstain'

def test_backcast_finds_bounded_plan_without_writes(core):
    plan=core.whatif_backcast('alpha','Reduce cost and increase hours',
         {'cost':{'op':'<=','value':80},'hours':{'op':'>=','value':13}},
         [{'op':'add','key':'cost','value':-10},{'op':'add','key':'hours','value':1}],
         max_depth=4,persist=True)
    assert plan['status']=='assumed_plan_found'
    assert len(plan['plan']['actions'])==3
    assert plan['simulation_crosschecked'] is True
    assert core.state('alpha')=={'cost':100,'hours':12}
    assert core.whatif_history('alpha')[0]['id']==plan['run_id']

def test_backcast_abstains_and_does_not_use_shell(core):
    plan=core.whatif_backcast('alpha','Impossible',{'cost':{'op':'<','value':20}},
           [{'op':'add','key':'cost','value':-10}],max_depth=2)
    assert plan['status']=='not_found_within_budget' and plan['plan'] is None
    with pytest.raises(WorldCoreError):
        core.whatif_backcast('alpha','Unsafe',{'cost':{'op':'<','value':20}},
                             [{'op':'exec','key':'cost','command':'ls'}])

def test_replay_requires_real_evidence_and_is_owner_scoped(core):
    a=core.compare_futures('alpha','Review cost',cases(),objectives=goals())
    pending=core.whatif_replay('alpha',a['run_id'])
    assert pending['status']=='unresolved' and pending['chosen_residuals']=={}
    core.verify_whatif('alpha',a['run_id'],'fast',{'cost':92},source='host_verified')
    after=core.whatif_replay('alpha',a['run_id'])
    assert after['chosen_residuals']['cost']['error']==2
    assert after['causal_claim'] is False and after['unrealized_alternatives']=='not_observable'
    with pytest.raises(WorldCoreError):core.whatif_replay('bravo',a['run_id'])

def test_stress_test_with_different_futures_no_side_effect(core):
    plans=[{'id':'lower_cost','actions':[{'op':'add','key':'cost','value':-15}]},
           {'id':'do_nothing','actions':[]}]
    changes=[{'id':'normal','changes':{}},{'id':'inflation','changes':{'cost':125}}]
    result=core.whatif_stress_test('alpha','Cost inflation',plans,changes,
                                 objectives=[{'key':'cost','direction':'minimize','scale':10}])
    assert result['robustness_order']==['lower_cost','do_nothing']
    assert result['plans'][0]['worst_case_score']==1.5
    assert result['causal_claim'] is False and result['action_executed'] is False
    assert core.state('alpha')['cost']==100

def test_stress_invalid_shock_and_plan_rejected(core):
    with pytest.raises(WorldCoreError):
        core.whatif_stress_test('alpha','bad',[{'id':'A','actions':[]},{'id':'B','actions':[]}],
             [{'id':'s','changes':{'cost':float('inf')}}],
             objectives=[{'key':'cost','direction':'minimize','scale':1}])
