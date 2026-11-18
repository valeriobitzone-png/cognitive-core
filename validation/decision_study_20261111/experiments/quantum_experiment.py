from pathlib import Path
import json,math,time
import numpy as np
from scipy.optimize import minimize

ROOT=Path(__file__).resolve().parent

def probabilities(a,b):
    pA=np.cos(a/2)**2;pB=np.cos(b/2)**2;stay=np.cos((a-b)/2)**2
    return np.array([pA,pB,stay])

def joint(p,order,x,y):
    first=p[order]
    return (first if x else 1-first)*(p[2] if x==y else 1-p[2])

def loss(p,rows):
    return -np.mean([math.log(max(1e-9,joint(p,*r))) for r in rows])

def fit_quantum(rows):
    candidates=[]
    for a,b in ((.5,1.5),(1.5,.5),(2.,-1.),(-1.,2.)):
        f=minimize(lambda v:loss(probabilities(*v),rows),[a,b],bounds=[(-math.pi,math.pi)]*2,method='L-BFGS-B')
        candidates.append(f)
    best=min(candidates,key=lambda r:r.fun)
    return probabilities(*best.x)

def sample(rng,p,n):
    rows=[]
    for _ in range(n):
        o=int(rng.integers(2));x=int(rng.random()<p[o]);y=x if rng.random()<p[2] else 1-x
        rows.append((o,x,y))
    return rows

began=time.monotonic();results=[];data=[]
for name,p in [('projective_2d',probabilities(.7,1.8)),('classical_dynamic',np.array([.85,.3,.8])),('independent',np.array([.5,.5,.5]))]:
    for seed in range(10):
        rng=np.random.default_rng(1000+seed)
        train=sample(rng,p,160);valid=sample(rng,p,80);test=sample(rng,p,400)
        q=fit_quantum(train)
        firsts=[[r[1] for r in train if r[0]==o] for o in (0,1)]
        classical=np.array([(sum(r)+1)/(len(r)+2) for r in firsts]+[(sum(r[1]==r[2] for r in train)+1)/(len(train)+2)])
        # Independent model has two probabilities for questions, independent of order/history.
        totals=[[r[1] if r[0]==o else r[2] for r in train] for o in (0,1)]
        static=[(sum(v)+1)/(len(v)+2) for v in totals]
        def static_loss(rows):
            return -np.mean([math.log(max(1e-9,(static[o] if x else 1-static[o])*(static[1-o] if y else 1-static[1-o]))) for o,x,y in rows])
        scores={'quantum_2params':float(loss(q,test)),
                'classical_equivalent_2params':float(loss(q,test)),
                'classical_dynamic_3params':float(loss(classical,test)),
                'classical_static_2params':float(static_loss(test))}
        results.append({'generator':name,'seed':seed,'train':len(train),'valid':len(valid),'test':len(test),'holdout_joint_nll':scores})
        for split,rows in [('train',train),('valid',valid),('test',test)]:
            data.extend({'id':f'{name}-{seed}-{split}-{i}','generator':name,'seed':seed,'split':split,'order':o,'first':x,'second':y,'epistemic':'SIMULATED'} for i,(o,x,y) in enumerate(rows))
summary={}
for name,_ in [('projective_2d',None),('classical_dynamic',None),('independent',None)]:
    rows=[r for r in results if r['generator']==name];models=list(rows[0]['holdout_joint_nll'])
    summary[name]={m:float(np.mean([r['holdout_joint_nll'][m] for r in rows])) for m in models}
    diff=np.array([r['holdout_joint_nll']['quantum_2params']-r['holdout_joint_nll']['classical_dynamic_3params'] for r in rows])
    rng=np.random.default_rng(42);boot=np.array([rng.choice(diff,len(diff),replace=True).mean() for _ in range(2000)])
    summary[name]['q_minus_dynamic_seed_bootstrap95']=np.quantile(boot,[.025,.975]).tolist()
assert all(r['holdout_joint_nll']['quantum_2params']==r['holdout_joint_nll']['classical_equivalent_2params'] for r in results)
report={'epistemic':'SIMULATED','elapsed_seconds':time.monotonic()-began,'seeds':10,'summary':summary,'runs':results,
        'conclusion':'No advantage over the matched classical dynamical representation; order effects do not identify a physical quantum mechanism.',
        'limitations':'Toy two-question projective model; synthetic generators; intervals over ten seeds, not independent real-world replications.'}
(ROOT/'quantum-results.json').write_text(json.dumps(report,indent=2))
with (ROOT/'quantum-data.jsonl').open('w') as f:
    for row in data:f.write(json.dumps(row)+'\n')
print(json.dumps(summary,indent=2))
