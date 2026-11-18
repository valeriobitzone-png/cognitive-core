"""Bounded sequential audit on copies of the user's real archive, no fact promotion."""
from pathlib import Path
import json,hashlib,collections,random,time,sys,tempfile
R=Path(__file__).resolve().parent;source=Path('/Volumes/AMBRO/projects/CognitiveCore/realtest/data/ensemble');snap=R/'real-archive-snapshot';snap.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=[]
for name in ('connection_graph.json','HYPOTHESIS_QUEUE.json'):
 p=source/name;before=p.stat();data=p.read_bytes();after=p.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns);assert len(data)<4_000_000
 target=snap/name
 if target.exists():assert target.read_bytes()==data
 else:target.write_bytes(data)
 manifest.append({'source':str(p),'copy':str(target),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
graph=json.loads((snap/'connection_graph.json').read_text());queue=json.loads((snap/'HYPOTHESIS_QUEUE.json').read_text())
sys.path.insert(0,str(R.parent/'decisionale-locale-2026-11-10/runtime/src'))
from cognitive_core import CognitiveCore,Settings
nodes=[v['id'] for v in graph['nodes']];all_tasks=[('graph_nodes','structure'),('graph_edges','structure'),('queue_count','queue'),('excluded_count','queue')]+[(v,'degree') for v in nodes[:20]]
def oracle(key):
 if key=='graph_nodes':return len(graph['nodes'])
 if key=='graph_edges':return len(graph['edges'])
 if key=='queue_count':return len(queue['queue'])
 if key=='excluded_count':return len(queue['excluded_already_tested_later_same_pair'])
 return sum(e.get('source')==key or e.get('target')==key for e in graph['edges'])
def acquired_procedure(key):
 # Independent implementation reads the snapshot afresh; no access to oracle output.
 if key in ('queue_count','excluded_count'):
  obj=json.loads((snap/'HYPOTHESIS_QUEUE.json').read_text())
  field='queue' if key=='queue_count' else 'excluded_already_tested_later_same_pair'
  return sum(1 for _ in obj[field])
 obj=json.loads((snap/'connection_graph.json').read_text())
 if key in ('graph_nodes','graph_edges'):
  field='nodes' if key=='graph_nodes' else 'edges';return sum(1 for _ in obj[field])
 degrees=collections.Counter()
 for edge in obj['edges']:
  for endpoint in {edge.get('source'),edge.get('target')}:degrees[endpoint]+=1
 return degrees[key]

def run(policy,seed):
 rng=random.Random(seed);backlog=list(all_tasks);rng.shuffle(backlog);skills=set();failures=set();rows=[];cost=0;started=time.monotonic()
 with tempfile.TemporaryDirectory(prefix='cognitive-real-audit-') as td:
  home=Path(td);registry=home/'skills.json';core=CognitiveCore(Settings(home=home/'core',owner='experiment',namespace=f'real-{policy}-{seed}',max_cycle_ticks_per_day=300));core.drive.upsert_project('audit','Real archive audit',['graph','degree','queue'],1)
  while backlog and cost<24:
   if policy=='D':
    # Use learned competence; investigate failed skill families before repeatedly failing more tasks.
    backlog.sort(key=lambda x:(x[1] not in skills,x[1] not in failures,x[0]))
   key,family=backlog.pop(0);learn=False
   if family in failures and family not in skills and cost+4<=24:
    cost+=3;skills.add(family);learn=True;registry.write_text(json.dumps({'format':'verified-audit-procedure-v1','skills':sorted(skills),'source_hashes':[m['sha256'] for m in manifest],'provenance':'local format contract + independent record scan, not an LLM assertion'}))
   cost+=1;t=time.monotonic();expected=oracle(key)
   if family in skills:actual=acquired_procedure(key)
   elif key=='graph_nodes':actual=graph.get('counts',{}).get('nodes')
   elif key=='graph_edges':actual=graph.get('counts',{}).get('edges')
   elif key=='queue_count':actual=queue.get('n')
   else:actual=None
   correct=actual==expected
   if not correct:failures.add(family)
   row={'session':len(rows)//5,'step':len(rows),'task':key,'family':family,'output':actual,'verified_output':expected,'correct':correct,'cost_total':cost,'acquired':learn,'skills':sorted(skills),'seconds':time.monotonic()-t,'epistemic':'OBSERVED structural audit only; source scientific claims remain unverified'};rows.append(row)
   if len(rows)%5==0:
    core.vault.document('graph degree queue audit',json.dumps(row))
    topic=core.observe({'kind':'session_end','title':'graph degree queue audit','question':f'How can graph degree queue audit preserve observed metadata at session {row["session"]}?'})['topics'][0]
    for tick in range(10):
     result=core.cycle_once(topic)
     if result['status'] in ('done','abstained','stopped','blocked'):break
    row['core_cycle']=result['status'];core.close()
    if registry.exists():assert set(json.loads(registry.read_text())['skills'])==skills
    core=CognitiveCore(Settings(home=home/'core',owner='experiment',namespace=f'real-{policy}-{seed}',max_cycle_ticks_per_day=300));row['restart_verified']=True
  core.close()
 return {'policy':policy,'seed':seed,'n':len(rows),'correct':sum(v['correct'] for v in rows),'cost_units':cost,'correct_per_cost':sum(v['correct'] for v in rows)/cost,'skills':sorted(skills),'seconds':time.monotonic()-started,'rows':rows}
runs=[run(policy,seed) for policy in ('C','D') for seed in range(5)]
for m in manifest:assert sha(Path(m['source']))==m['sha256']
summary={p:{'correct_mean':sum(x['correct'] for x in runs if x['policy']==p)/5,'correct_per_cost':sum(x['correct_per_cost'] for x in runs if x['policy']==p)/5} for p in ('C','D')}
report={'source_manifest':manifest,'originals_unchanged':True,'runs':runs,'summary':summary,'limits':'Real archive data and actual structural queries, bounded accelerated sequential sessions, not weeks of unattended deployment. Explicit procedural skill acquisition from verified catalog, not neural weight training. Some initial archived counts are stale: exact array scans correct metadata only, never promote graph hypotheses to facts. Same24-unit budget and same24-item backlog per run.'}
(R/'real-archive-longitudinal-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(summary,indent=2))
