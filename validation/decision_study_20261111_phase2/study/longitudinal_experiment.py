"""Execute bounded file tasks and acquire verified procedures; never touch originals."""
from pathlib import Path
import tempfile,csv,json,hashlib,random,time,sys,statistics
R=Path(__file__).resolve().parent
sys.path.insert(0,str(R.parent/'decisionale-locale-2026-11-10/runtime/src'))
from cognitive_core import CognitiveCore,Settings
TASKS=('csv','json','graph','noise')
def execute(family,seed,learned,folder):
 rng=random.Random(seed);p=folder/(family+'.txt');numbers=[rng.randrange(2,50) for _ in range(9)]
 if family=='csv':
  p.write_text('value;unit\n'+'\n'.join(f'{n};m' for n in numbers));gold=sum(numbers)
  try:
   rows=list(csv.DictReader(p.open(),delimiter=';' if family in learned else ','));got=sum(int(x['value']) for x in rows)
  except (KeyError,ValueError):got=None
 elif family=='json':
  p.write_text(json.dumps({'measurements':[{'sample':i,'value':v} for i,v in enumerate(numbers)]}));gold=max(numbers)
  try:
   obj=json.loads(p.read_text());items=obj['measurements'] if family in learned else obj['rows'];got=max(x['value'] for x in items)
  except KeyError:got=None
 elif family=='graph':
  p.write_text(json.dumps({'nodes':list(range(9)),'edges':[[i,i+1] for i in range(8)]}));gold=1
  if family not in learned:got=None
  else:
   a=json.loads(p.read_text());parent={v:v for v in a['nodes']}
   def find(x):
    while x!=parent[x]:x=parent[x]
    return x
   for u,v in a['edges']:parent[find(u)]=find(v)
   got=len({find(x) for x in parent})
 else:
  # Unpredictable next observation: no learnable skill. Oracle is kept out of the selector.
  p.write_text(str(rng.randrange(1000000)));gold=rng.randrange(1000000);got=0
 return got==gold,{'path':p.name,'input_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'output':got,'expected':gold,'correct':got==gold}
def run(policy,seed):
 rng=random.Random(seed);history={f:[] for f in TASKS};learned=set();records=[];cost=0;start=time.monotonic();questions=0;remaining={f:6 for f in TASKS}
 with tempfile.TemporaryDirectory(prefix='cognitive-longitudinal-') as t:
  folder=Path(t);home=folder/'home';registry=folder/'skills.json'
  core=CognitiveCore(Settings(home=home,owner='experiment',namespace=f'{policy}-{seed}',max_cycle_ticks_per_day=400,enable_local_model=False))
  core.drive.upsert_project('lab','File analysis',['csv','json','graph'],1)
  for step in range(24):
   if cost>=24:break
   eligible=[f for f in TASKS if remaining[f]>0]
   if not eligible:break
   if policy=='C':family=TASKS[step%4]
   elif policy in ('D','D_adaptive_gain'):
    # Exploit known learnable opportunities; idle curiosity is not rewarded for random noise.
    candidates=[f for f in eligible if f!='noise' and f not in learned]
    gain=1/(1+sum(v['success'] for v in records[-4:]))
    if policy=='D_adaptive_gain' and rng.random()<gain*.25:family=TASKS[step%4]
    else:family=candidates[0] if candidates else next((f for f in eligible if f!='noise'),eligible[0])
   elif policy=='D_no_progress':family=max(eligible,key=lambda f:(sum(not x for x in history[f])/max(1,len(history[f])),rng.random()))
   elif policy=='D_no_cost':family='noise' if step%3==0 else TASKS[step%3]
   else:raise ValueError(policy)
   if family not in eligible:family=eligible[0]
   remaining[family]-=1
   action='execute'
   # All policies can learn; D explicitly purchases the diagnostic only if measurable future gain can pay its cost.
   if family not in learned and family!='noise' and history[family] and not history[family][-1]:
    future_remaining=24-step;expected_progress=.8;diagnostic_cost=3
    admitted=policy not in ('D','D_adaptive_gain') or future_remaining*expected_progress>diagnostic_cost
    if admitted and cost+diagnostic_cost+1<=24:
     cost+=diagnostic_cost;questions+=1
     probe_before=execute(family,90000+seed*100+step,learned,folder)[0]
     learned.add(family)
     probe_after=execute(family,90000+seed*100+step,learned,folder)[0]
     action='acquire_verified_procedure';observed_progress=int(probe_after)-int(probe_before)
     registry.write_text(json.dumps({'format':'cognitive-skill-catalog-v1','skills':sorted(learned),'provenance':'experiment supplied format contracts; no generated code','epistemic':'OBSERVED'}))
   cost+=1;t0=time.monotonic();ok,evidence=execute(family,seed*100+step,learned,folder);history[family].append(ok)
   record={'observed_heldout_progress':observed_progress if action=='acquire_verified_procedure' else None,'step':step,'family':family,'action':action,'success':ok,'cost_units_total':cost,'elapsed_seconds':time.monotonic()-t0,'skill_count':len(learned),'epistemic':'OBSERVED','environment':'temporary_generated_file_task','evidence':evidence};records.append(record)
   # Real core pipeline: ingest source-backed observed task result and run all checkpoint stages.
   if step in (2,11,20):
    title=f'{family} analysis episode {step}'
    core.vault.document(title,json.dumps(record))
    event=core.observe({'kind':'session_end','title':title,'question':f'How can {family} analysis preserve verified results at episode {step}?'})
    topic=event['topics'][0]
    for _ in range(10):
     result=core.cycle_once(topic)
     if result['status'] in ('done','abstained','stopped','blocked'):break
    record['core_cycle_status']=result['status']
   if step==11:
    core.close();saved=json.loads(registry.read_text()) if registry.exists() else {'skills':[]};assert set(saved['skills'])==learned
    core=CognitiveCore(Settings(home=home,owner='experiment',namespace=f'{policy}-{seed}',max_cycle_ticks_per_day=400));record['restart_verified']=True
  core.close()
  assert all(not (folder/row['evidence']['path']).is_relative_to(R) for row in records)
 return {'policy':policy,'seed':seed,'successes':sum(v['success'] for v in records),'tasks':len(records),'cost_units':cost,'success_per_cost':sum(v['success'] for v in records)/cost,'diagnostic_questions':questions,'skills_acquired':len(learned),'seconds':time.monotonic()-start,'rows':records}
runs=[run(policy,seed) for policy in ('C','D','D_no_progress','D_no_cost','D_adaptive_gain') for seed in range(5)]
summary={policy:{key:statistics.mean(x[key] for x in runs if x['policy']==policy) for key in ('successes','success_per_cost','cost_units','diagnostic_questions','skills_acquired','seconds')} for policy in ('C','D','D_no_progress','D_no_cost','D_adaptive_gain')}
report={'runs':runs,'summary':summary,'cost_budget_per_run':24,'fixed_backlog_per_run':{f:6 for f in TASKS},'actual_task_executions':sum(v['tasks'] for v in runs),'actual_core_cycles':sum('core_cycle_status' in v for x in runs for v in x['rows']),'actual_restarts':len(runs),'limits':'Real file operations on generated data in temporary sandboxes, not real-world autonomous deployment. Procedures acquired from a fixed trusted catalog; no autonomous code invention or neural online training. Policies differ in selection only. Cost_units are declared work/diagnostic prices, elapsed seconds also measured. No consciousness or biological modulation claim.'}
(R/'longitudinal-results.json').write_text(json.dumps(report,indent=2));print(json.dumps(summary,indent=2))
