"""Repeatable bounded WHAT IF examples. Synthetic, no ground-truth predictive claims."""
from __future__ import annotations
import json
import time
from pathlib import Path
from worldcore import WorldCore

OUT=Path(__file__).resolve().parents[1]/'training-artifacts/v11_whatif_benchmark.json'
def run():
    measurements=[]
    t=time.perf_counter()
    with WorldCore(':memory:') as core:
        owner='benchmark'
        core.set_state(owner,'available_minutes',120)
        core.set_state(owner,'pending_tasks',3)
        core.set_state(owner,'cost_eur',100)
        comp=core.compare_futures(owner,'Budget versus time',[
            {'id':'overtime','actions':[{'op':'add','key':'available_minutes','value':60},{'op':'add','key':'cost_eur','value':30}]},
            {'id':'save_money','actions':[{'op':'add','key':'cost_eur','value':-20}]},
        ],objectives=[{'key':'cost_eur','direction':'minimize','scale':10},
                      {'key':'available_minutes','direction':'maximize','scale':60}],
        failure_conditions=[{'key':'cost_eur','op':'>','threshold':120}])
        assert comp['ranking']==['save_money','overtime']
        assert core.state(owner)['available_minutes']==120
        core.verify_whatif(owner,comp['run_id'],'save_money',{'cost_eur':85},source='host_verified')
        replay=core.whatif_replay(owner,comp['run_id'])
        assert replay['chosen_residuals']['cost_eur']['error']==5
        measurements.append({'case':'decision_replay','result':'passed','unrealized_alternatives':'not_observable'})
        bc=core.whatif_backcast(owner,'Finish 3 tasks',
            {'pending_tasks':{'op':'==','value':0}},
            [{'op':'add','key':'pending_tasks','value':-1}],max_depth=4)
        assert bc['plan']['steps']==3 and not bc['action_executed']
        measurements.append({'case':'bounded_backcast','result':'passed','searched_states':bc['searched_states']})
        s=core.whatif_stress_test(owner,'Cost robustness',
            [{'id':'plan_A','actions':[{'op':'add','key':'cost_eur','value':-15}]},
             {'id':'plan_B','actions':[{'op':'add','key':'cost_eur','value':5}]}],
            [{'id':'base','changes':{}},{'id':'high_cost','changes':{'cost_eur':140}}],
            objectives=[{'key':'cost_eur','direction':'minimize','scale':10}])
        assert s['robustness_order'][0]=='plan_A' and s['action_executed'] is False
        measurements.append({'case':'hypothetical_shock_robustness','result':'passed','unmeasured_unknowns':True})
        world=core.compare_futures(owner,'Unknown environment',[
            {'id':'unknown','kind':'world','environment':'unseen','before':{'score':1},'actions':['click']},
            {'id':'keep','actions':[]}],objectives=[{'key':'available_minutes','direction':'maximize','scale':1}])
        assert world['scenarios'][0]['status']=='abstain' and world['ranking']==[]
        measurements.append({'case':'unsupported_environment_abstention','result':'passed'})
    result={'version':'1.1.0','dataset':'synthetic_test_scenarios_not_independent_predictive_benchmark',
            'checks':measurements,'passed':len(measurements),
            'time_seconds':round(time.perf_counter()-t,4),
            'claims_not_supported':['general world understanding','causal counterfactual accuracy','host model integration certification']}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':run()
