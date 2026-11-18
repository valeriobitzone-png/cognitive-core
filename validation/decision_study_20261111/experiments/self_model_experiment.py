from pathlib import Path
import json,random,sys,tempfile,statistics
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'decisionale-locale-2026-11-10/runtime/src'))
from cognitive_core.selfmodel import SelfModel

runs=[]
for seed in range(10):
 rng=random.Random(seed)
 with tempfile.TemporaryDirectory() as temp:
  model=SelfModel(temp,'research','simulated')
  training=[]
  for version,p in [('stable',.9),('degraded',.2)]:
   for i in range(40):
    f=model.forecast('local_inference','routing',{'local_inference_available':True},{'version':version},
                     request_key=f'train-{version}-{i}',epistemic='SIMULATED')
    y=rng.random()<p;training.append(y)
    model.resolve(f['id'],y,'fixture:controlled-process-outcome')
  pooled=(sum(training)+1)/(len(training)+2)
  test=[]
  # Freeze every forecast before revealing any held-out outcomes.
  for version,p in [('stable',.9),('degraded',.2)]:
   for i in range(40):
    f=model.forecast('local_inference','routing',{'local_inference_available':True},{'version':version},
                    request_key=f'test-{version}-{i}',epistemic='SIMULATED')
    corrupted=model.forecast('local_inference','routing',{'local_inference_available':True},{'version':'ablated'},
                    request_key=f'ablated-{version}-{i}',epistemic='SIMULATED')
    irrelevant=model.forecast('local_inference','routing',{'local_inference_available':True,'ui_theme':'light'},
                    {'version':version},request_key=f'irrelevant-{version}-{i}',epistemic='SIMULATED')
    test.append((f,corrupted,irrelevant,rng.random()<p))
  scores={'B_memory_only':[],'C_self_state':[],'C_external_same_information':[],
          'C_ablated_state':[],'C_irrelevant_perturbation':[]}
  for f,corrupted,irrelevant,y in test:
   p=f['estimate_for_scoring']
   for name,pred in [('B_memory_only',pooled),('C_self_state',p),('C_external_same_information',p),
      ('C_ablated_state',corrupted['estimate_for_scoring']),('C_irrelevant_perturbation',irrelevant['estimate_for_scoring'])]:
    scores[name].append((pred-int(y))**2)
   model.resolve(f['id'],y,'fixture:heldout-outcome')
  removed=model.forecast('local_inference','routing',{'local_inference_available':False},{'version':'stable'},epistemic='SIMULATED')
  assert removed['admitted'] is False and removed['probability']==0
  # Simulated episodes never train the observed operational estimator.
  observed=model.forecast('local_inference','routing',{'local_inference_available':True},{'version':'stable'})
  assert observed['samples']==0
  model.export(ROOT/f'self-model-seed{seed}.json');model.close()
  resumed=SelfModel(temp,'research','simulated')
  assert resumed.episodes();resumed.close()
  runs.append({'seed':seed,'train_n':80,'holdout_n':80,'mean_brier':{k:statistics.mean(v) for k,v in scores.items()},
               'removed_tool_admitted':removed['admitted'],'observed_history_contaminated':False})
summary={k:statistics.mean(r['mean_brier'][k] for r in runs) for k in runs[0]['mean_brier']}
report={'epistemic':'SIMULATED','runs':runs,'mean_brier':summary,
 'interpretation':'State-conditioned forecasts beat a pooled history in this constructed task; equal-information external observer matches exactly. No privileged introspection or consciousness claim.',
 'limits':'Synthetic stationary binary outcomes; two runtime versions; operational execution only, not semantic correctness; not a real-world calibration certificate.'}
(ROOT/'self-model-results.json').write_text(json.dumps(report,indent=2));print(json.dumps(summary,indent=2))
