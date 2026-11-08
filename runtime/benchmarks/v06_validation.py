"""Reproducible controlled v0.6 tests; no claim of generalized intelligence.

Demonstrates exact-state transition learning on four toy domains. The held-out
samples use KNOWN state-action contexts; unseen ones must abstain.
"""
from __future__ import annotations
from pathlib import Path
import json, tempfile, statistics
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from worldcore import WorldCore

DOMAINS={
    'navigation':(['home','shop','park'], ['walk','stay']),
    'browser':(['login','dashboard','settings'], ['click','back']),
    'robot':(['rest','ready','charging'], ['move','charge']),
    'workflow':(['pending','running','done'], ['start','pause']),
}

def successor(states,actions,s,a):
    i=states.index(s);j=actions.index(a)
    return states[(i+(1 if j==0 else 2))%len(states)]

def run():
    with tempfile.TemporaryDirectory() as tmp:
        with WorldCore(str(Path(tmp)/'validation.sqlite')) as w:
            total=0;correct=0;abstain_unknown=0
            for env,(states,actions) in DOMAINS.items():
                for si,state in enumerate(states):
                    for ai,act in enumerate(actions):
                        nxt=successor(states,actions,state,act)
                        for k in range(10):
                            w.observe_world_transition('bench',env,f'train_{si}_{ai}_{k}',state,act,nxt)
                for si,state in enumerate(states):
                    for ai,act in enumerate(actions):
                        expected=successor(states,actions,state,act)
                        pred=w.imagine_world('bench',env,state,[act])
                        total+=1
                        if pred['status']=='simulated' and pred['steps'][0]['states'][0]['state']==expected:
                            correct+=1
                if w.imagine_world('bench',env,'NEW_UNSEEN_STATE',['walk' if env=='navigation' else actions[0]])['status']=='abstain':
                    abstain_unknown+=1
            # News/market scenario uses synthetic timestamped movements, NOT evidence of real predictive power.
            from datetime import datetime,timedelta,timezone
            t=datetime(2025,1,1,tzinfo=timezone.utc)
            news_count=6
            for i in range(news_count):
                base=t+timedelta(hours=i*72)
                w.record_news('bench',f'news{i}','macro',base.isoformat(),'Test announcement',
                              'https://example.org/synthetic',source='synthetic_fixture')
                for symbol,ratio in [('BTC',1.04 if i%2==0 else .98),('BENCH',1.01 if i%2==0 else .99)]:
                    w.record_price('bench',symbol,base.isoformat(),100,source='synthetic_fixture')
                    w.record_price('bench',symbol,(base+timedelta(hours=24)).isoformat(),100*ratio,source='synthetic_fixture')
            market=w.news_market_study('bench','macro','BTC','BENCH',max_gap_hours=1)
            catalog=w.search_repo_candidates('world model',limit=5) # empty database intentionally
            return {'benchmark':'controlled_known_state_action_holdout','environment_domains':list(DOMAINS),
                    'training_observations':4*3*2*10,
                    'heldout_queries':total,'top_state_correct':correct,'top_state_accuracy':correct/total,
                    'out_of_distribution_abstentions':abstain_unknown,'ood_environments_tested':len(DOMAINS),
                    'market_fixture':{'synthetic':True,'events':market.get('events'),
                                      'status':market.get('status'),'trading_signal':False},
                    'repo_catalog':{'separate_database':True,'query_on_empty_db':len(catalog)},
                    'caveat':'No new-domain generalization; pre-specified deterministic transition function and repeated exact state-action contexts.'}

if __name__=='__main__':
    result=run()
    dest=Path(__file__).resolve().parents[1]/'training-artifacts'/'v06_controlled_validation.json'
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
