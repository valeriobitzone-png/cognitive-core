from pathlib import Path
import json,math,statistics
import bench_phase2 as b
R=Path(__file__).resolve().parent

def wilson(k,n):
 z=1.959963984540054;p=k/n;den=1+z*z/n;center=(p+z*z/(2*n))/den;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
 return [center-half,center+half]

def f1(rows):
 out=[]
 for label in b.A:
  tp=sum(r['expected']==r['action']==label for r in rows);fp=sum(r['expected']!=label and r['action']==label for r in rows);fn=sum(r['expected']==label and r['action']!=label for r in rows);out.append(2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0)
 return sum(out)/len(out)
summary={}
for p in R.glob('*-*.json'):
 try:a=json.loads(p.read_text())
 except (ValueError,OSError):continue
 if not isinstance(a,dict) or not a.get('complete') or not all(k in a for k in ('model','protocol','split','rows')):continue
 rows=a['rows'];n=len(rows);k=sum(x['expected']==x['action'] for x in rows)
 summary[p.name]={'model':a['model'],'protocol':a['protocol'],'split':a['split'],'correct':k,'n':n,'accuracy':k/n,'wilson95':wilson(k,n),'macro_f1':f1(rows),'invalid':sum(x['action']=='INVALID' for x in rows),'valid_policy_violations':sum(x['action']!='INVALID' and not b.permitted(x['action'],x['input']) for x in rows),'p50_seconds':statistics.median(x['seconds'] for x in rows),'mean_seconds':statistics.mean(x['seconds'] for x in rows),'p95_seconds':sorted(x['seconds'] for x in rows)[math.ceil(n*.95)-1],'peak_child_rss_bytes':a.get('peak_child_rss_bytes'),'threshold25of34_met':k>=25 if n==34 else None}
(R/'comparison-phase2.json').write_text(json.dumps({'results':summary,'measurement_note':'Policy violation counts recomputed using corrected paused-project and consent gating; predictions and raw outputs untouched. Wilson intervals describe this small fixture sample, not a real-world guarantee.'},indent=2));print(json.dumps(summary,indent=2))
