from pathlib import Path
import json,re,statistics
import numpy as np
from sklearn.metrics import accuracy_score,f1_score
ROOT=Path(__file__).resolve().parent
ACTIONS=json.loads((ROOT/'dataset.json').read_text())['actions']
NATIVE={'wait':'WAIT','remember':'REMEMBER','research_local':'LOCAL_RESEARCH','research_web':'WEB_RESEARCH','ask_clarification':'ASK_CLARIFICATION','request_approval':'REQUIRE_APPROVAL'}
def permitted(action,item):
 s=item['state']
 if action=='WEB_RESEARCH':return s['browser_available'] and s['web_opt_in'] and s['requests_left']>0 and s['topic_status']=='open'
 if action=='LOCAL_RESEARCH':return s['local_sources']>0 and s['topic_status']=='open'
 if s['topic_status'] in ('paused','discarded') and action not in ('WAIT','REQUIRE_APPROVAL'):return False
 return action in ACTIONS

def metrics(rows):
 gold=[r['expected'] for r in rows];pred=[r['action'] for r in rows]
 return {'n':len(rows),'accuracy':accuracy_score(gold,pred),'macro_f1':f1_score(gold,pred,labels=ACTIONS,average='macro',zero_division=0),
 'valid_policy_violations':sum(r['action'] in ACTIONS and not permitted(r['action'],r['input']) for r in rows),
 'invalid_outputs':sum(r['action'] not in ACTIONS for r in rows),
 'p50_seconds':statistics.median(r['seconds'] for r in rows),'p95_seconds':float(np.quantile([r['seconds'] for r in rows],.95)),
 'native_no_call':sum(r.get('status')=='native_no_call' for r in rows)}
summary={}
for model in ('rules','statistical','qwen','lfm','granite','functiongemma'):
 p=ROOT/(model+'-results.json')
 if not p.exists():continue
 d=json.loads(p.read_text())
 if not d.get('complete'):continue
 rows=d['rows']
 summary[model]={'protocol':d.get('protocol'),'peak_child_rss_bytes':d.get('peak_child_rss_bytes'),
  'original_test':metrics([r for r in rows if r['split']=='test'])}
 if model=='functiongemma':
  # Official application boundary is the FIRST complete function call; later
  # generated function-response turns are not another proposal by the caller.
  corrected=[]
  for r in rows:
   row=dict(r);raw=r.get('raw','')
   block=re.search(r'<start_function_call>\s*call:([A-Za-z_]+)\s*\{(.*?)\}<end_function_call>',raw,re.S)
   if block:
    row['action']=NATIVE.get(block[1],'INVALID') if not block[2].strip() else 'INVALID'
   corrected.append(row)
  summary[model]['first_call_boundary_test']=metrics([r for r in corrected if r['split']=='test'])
  summary[model]['boundary_correction']='Parsing correction only, no weights/prompt changes or rerun; original raw output and initial scores retained. Latency is the original full-generation upper bound.'
  (ROOT/'functiongemma-boundary-corrected.json').write_text(json.dumps(corrected,ensure_ascii=False,indent=2))
(ROOT/'comparison-summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
p=ROOT/'self-model-results.json';d=json.loads(p.read_text());rng=np.random.default_rng(42)
differences={}
for baseline in ('B_memory_only','C_external_same_information','C_ablated_state','C_irrelevant_perturbation'):
 v=np.array([r['mean_brier']['C_self_state']-r['mean_brier'][baseline] for r in d['runs']])
 boot=np.array([rng.choice(v,len(v),replace=True).mean() for _ in range(2000)])
 differences[baseline]={'mean_difference':float(v.mean()),'seed_bootstrap95':np.quantile(boot,[.025,.975]).tolist()}
d['paired_seed_differences']=differences;p.write_text(json.dumps(d,indent=2))
