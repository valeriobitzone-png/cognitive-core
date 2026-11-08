"""Reproducible training on real public datasets bundled with optional libraries.

Sources checked via official UCI, scikit-learn and statsmodels documentation.
No generated labels, no web scraping and no external ML model weights. This script
uses optional research dependencies; WorldCore's runtime still has zero deps.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import random
from pathlib import Path
import numpy as np
from sklearn.datasets import load_iris, load_wine, load_digits
from sklearn.ensemble import RandomForestClassifier
from worldcore.ensemble import _infer
import statsmodels.api as sm
import sklearn
import statsmodels
from worldcore import WorldCore

SOURCES = {
    'iris':{'url':'https://archive.ics.uci.edu/dataset/53/iris','license':'CC-BY-4.0','citation':'Fisher, R. (1936). Iris. UCI DOI:10.24432/C56C76'},
    'wine':{'url':'https://archive.ics.uci.edu/dataset/109/wine','license':'CC-BY-4.0','citation':'Aeberhard, S.; Forina, M. (1992). Wine. UCI DOI:10.24432/C5PC7J'},
    'digits':{'url':'https://archive.ics.uci.edu/dataset/80/optical+recognition+of+handwritten+digits','license':'CC-BY-4.0','citation':'Alpaydin, E.; Kaynak, C. (1998). UCI DOI:10.24432/C50P49'},
    'sunspots':{'url':'https://www.statsmodels.org/stable/datasets/generated/sunspots.html','license':'PUBLIC-DOMAIN','citation':'National Geophysical Data Center; statsmodels sunspots 1700–2008'},
    'macrodata':{'url':'https://www.statsmodels.org/stable/datasets/generated/macrodata.html','license':'PUBLIC-DOMAIN','citation':'U.S. macroeconomic data; FRED and BLS, compiled by Skipper Seabold'},
    'co2':{'url':'https://www.statsmodels.org/stable/datasets/generated/co2.html','license':'PUBLIC-DOMAIN','citation':'Mauna Loa atmospheric CO2 measurements; statsmodels curated series'},
}


def fingerprint(x,y):
    return hashlib.sha256(np.asarray(x,dtype=np.float64).tobytes()+np.asarray(y,dtype=np.int32).tobytes()).hexdigest()


def real_datasets():
    d=load_iris(); yield 'iris',np.asarray(d.data,float),(np.asarray(d.target)==0).astype(int),'random_grouped'
    d=load_wine();yield 'wine',np.asarray(d.data,float),(np.asarray(d.target)==0).astype(int),'random_grouped'
    d=load_digits()
    x=d.images.reshape(-1,4,2,4,2).mean(axis=(2,4)).reshape(-1,16)  # 16 pixel-block averages; fixed, unsupervised
    yield 'digits',x.astype(float),(np.asarray(d.target)>=5).astype(int),'random_grouped'
    d=sm.datasets.sunspots.load_pandas().data
    values=d['SUNACTIVITY'].to_numpy(dtype=float)
    cutoff=float(np.median(values[:215]))  # fixed using past values only
    x=np.array([values[t-3:t] for t in range(3,len(values)-1)],float)
    y=np.array([values[t]>=cutoff for t in range(3,len(values)-1)],int)
    yield 'sunspots',x,y,'chronological'
    d=sm.datasets.macrodata.load_pandas().data
    gdp=np.asarray(d['realgdp'],float)
    inflation=np.asarray(d['infl'],float)
    unemployment=np.asarray(d['unemp'],float)
    # Only predictors known before the following quarter; labels: next quarter GDP growth positive.
    x=np.array([[math.log(gdp[t]/gdp[t-1]),math.log(gdp[t-1]/gdp[t-2]),
                 inflation[t],inflation[t-1],unemployment[t],unemployment[t-1]]
                for t in range(2,len(gdp)-1)],float)
    y=np.array([gdp[t+1]>gdp[t] for t in range(2,len(gdp)-1)],int)
    yield 'macrodata',x,y,'chronological'
    d=sm.datasets.co2.load_pandas().data
    s=d['co2'].ffill().dropna()  # causal gap-fill: only past observations, never future data
    vals=s.to_numpy(dtype=float)
    # Dataset frequency ~= weekly; next-week direction based on prior two deltas and calendar cycle.
    x=np.array([[vals[t]-vals[t-1],vals[t-1]-vals[t-2],
                math.sin(2*math.pi*(t%52)/52), math.cos(2*math.pi*(t%52)/52)]
               for t in range(2,len(vals)-1)],float)
    y=np.array([vals[t+1]>vals[t] for t in range(2,len(vals)-1)],int)
    yield 'co2',x,y,'chronological'


def group_indices(x, train_frac=0.75, seed=42):
    # Whole identical feature vectors stay in one partition.
    group_keys=[hashlib.sha256(np.asarray(row,dtype=float).tobytes()).hexdigest() for row in x]
    unique=sorted(set(group_keys))
    rng=random.Random(seed);rng.shuffle(unique)
    training=set(unique[:int(len(unique)*train_frac)])
    train=np.array([i for i,g in enumerate(group_keys) if g in training],int)
    test=np.array([i for i,g in enumerate(group_keys) if g not in training],int)
    assert set(group_keys[i] for i in train).isdisjoint(group_keys[i] for i in test)
    return train,test


def normalize(train,test):
    minx=np.min(train,axis=0);maxx=np.max(train,axis=0)
    spread=np.where(maxx-minx<1e-12,1.0,maxx-minx)
    trainx=np.clip((train-minx)/spread,0,1)
    uncut=(test-minx)/spread
    count=int(np.sum((uncut<0)|(uncut>1)))
    testx=np.clip(uncut,0,1)
    return trainx,testx,count


def brier(y,p):return float(np.mean((np.asarray(y)-np.asarray(p))**2))


def assess(w, name,x,y,split,seed):
    if split=='chronological':
        count=int(len(x)*.75);tr=np.arange(count);te=np.arange(count,len(x))
    else:tr,te=group_indices(x,seed=seed)
    assert len(tr)>20 and len(te)>20
    a,b,clipped=normalize(x[tr],x[te]);yt=y[tr];yv=y[te]
    mean=float(np.mean(yt));features=[f'f{i:02}' for i in range(x.shape[1])]
    w.create_model('public_research',name,features,space='real_data',provenance='external')
    dataset=[]
    for idx,row,label in zip(tr,a,yt):
        dataset.append({'id':f'{name}-{int(idx)}','features':dict(zip(features,map(float,row))),'outcome':bool(label)})
    random.Random(seed).shuffle(dataset)
    for i in range(0,len(dataset),2000):w.train_model('public_research',name,dataset[i:i+2000],space='real_data')
    holdout=[{'id':f'{name}-{int(idx)}','features':dict(zip(features,map(float,row))),'outcome':bool(label)} for idx,row,label in zip(te,b,yv)]
    result=w.evaluate_model('public_research',name,holdout,space='real_data',min_samples=20)
    result.update({'train_rows':len(tr),'test_rows':len(te),'all_rows':len(x),'features':len(features),
     'split':split,'test_clipped_features':clipped,'train_prior':mean,'baseline_brier':brier(yv,mean),
     'baseline_accuracy':float(np.mean(yv==(mean>=0.5))),
     'train_fingerprint_sha256':fingerprint(a,yt),'holdout_fingerprint_sha256':fingerprint(b,yv),
     'source':SOURCES[name],'goal':'binary prediction; NOT general intelligence or causal world simulation'})
    # Deliberately report model failures relative to baseline.
    result['beat_constant_brier_baseline']=result['brier']<result['baseline_brier']

    # Second independent learning method: offline-trained nonlinear forest, pure Python inference.
    clf=RandomForestClassifier(n_estimators=64,max_depth=7,min_samples_leaf=3,
                              random_state=seed,n_jobs=1)
    clf.fit(a,yt)
    trees=[]
    for estimator in clf.estimators_:
        t=estimator.tree_
        nodes=[]
        for i in range(t.node_count):
            if int(t.feature[i])<0:
                probs=t.value[i][0]; probability=float(probs[1]/sum(probs)) if sum(probs) else 0.5
                nodes.append([-1,probability,-1,-1])
            else:nodes.append([int(t.feature[i]),float(t.threshold[i]),
                               int(t.children_left[i]),int(t.children_right[i])])
        trees.append(nodes)
    raw_names={
      'iris':['sepal_length','sepal_width','petal_length','petal_width'],
      'wine':['alcohol','malic_acid','ash','alcalinity_of_ash','magnesium','total_phenols','flavanoids','nonflavanoid_phenols','proanthocyanins','color_intensity','hue','od280_od315','proline'],
      'digits':[f'pixel_block_{i:02}' for i in range(16)],
      'sunspots':['activity_3_years_ago','activity_2_years_ago','activity_last_year'],
      'macrodata':['gdp_growth_current','gdp_growth_previous','inflation_current','inflation_previous','unemployment_current','unemployment_previous'],
      'co2':['co2_delta_current','co2_delta_previous','seasonal_sine','seasonal_cosine']
    }[name]
    payload={'format':'worldcore.binary_forest.v1','names':features,'trees':trees,
             'raw_names':raw_names,'scaler':{'min':list(map(float,np.min(x[tr],axis=0))),
                                            'max':list(map(float,np.max(x[tr],axis=0)))},
             'training_rows':len(tr),'source':SOURCES[name]['url']}

    w.import_ensemble('public_research',name+'_forest',payload,space='real_data')
    sk_probs=clf.predict_proba(b)[:,list(clf.classes_).index(1)]
    for k,idx in enumerate(te[:10]):
        raw_result=w.predict_raw_ensemble('public_research',name+'_forest',
                      dict(zip(raw_names,map(float,x[idx]))),space='real_data')
        assert abs(raw_result['probability']-float(sk_probs[k]))<1e-10

    # Cross-engine equivalence test; a mismatch aborts the benchmark.
    for k,row in enumerate(b[:16]):
        local=w.predict_ensemble('public_research',name+'_forest',dict(zip(features,map(float,row))),space='real_data')['probability']
        assert abs(local-float(sk_probs[k]))<1e-10,(name,k,local,float(sk_probs[k]))
    inferred=np.asarray([_infer(payload,list(row)) for row in b],dtype=float)
    assert np.max(abs(inferred-sk_probs)) < 1e-10
    result['nonlinear_forest']={'trees':len(trees),'nodes':sum(len(t) for t in trees),
      'brier':brier(yv,inferred),'accuracy':float(np.mean((inferred>=.5)==yv)),
      'beat_constant_brier_baseline':brier(yv,inferred)<result['baseline_brier'],
      'beat_incremental_brier':brier(yv,inferred)<result['brier'],
      'pure_python_inference_parity_max_error':float(np.max(abs(inferred-sk_probs)))}
    if split=='chronological':
        if name=='sunspots':
            raw=float(np.median(sm.datasets.sunspots.load_pandas().data.SUNACTIVITY.to_numpy()[:215]))
            naive=(x[te,-1]>=raw).astype(float)
        elif name=='macrodata':naive=(x[te,0]>0).astype(float)
        else:naive=(x[te,0]>0).astype(float)
        # Fixed predeclared persistence predictor; no fitting on the holdout.
        naive_prob=0.20+0.60*naive
        result['persistence_baseline']={'brier':brier(yv,naive_prob),
          'accuracy':float(np.mean((naive_prob>=.5)==yv)),
          'incremental_beats_persistence':result['brier']<brier(yv,naive_prob),
          'forest_beats_persistence':brier(yv,inferred)<brier(yv,naive_prob)}
    return result


def train_transitions(w):
    # Genuine observational sequence: sunspot activity 3-quantile state transitions.
    values=sm.datasets.sunspots.load_pandas().data.SUNACTIVITY.to_numpy(dtype=float)
    t1,t2=np.quantile(values[:220],[.33,.67]); states=['low' if v<t1 else 'high' if v>=t2 else 'mid' for v in values]
    name='sunspots_states'; w.create_transition_model('public_research',name,space='real_data',provenance='external')
    cutoff=230
    for i in range(cutoff):w.observe_transition('public_research',name,states[i],'one_year_later',states[i+1],sample_id=f'obs-{i}',space='real_data')
    holdout=[{'id':f'holdout-{i}','current_state':states[i],'action':'one_year_later','next_state':states[i+1]}
             for i in range(cutoff,len(states)-1)]
    res=w.evaluate_transitions('public_research',name,holdout,space='real_data',min_samples=3)
    res.update({'train_rows':cutoff,'test_rows':len(holdout),'source':SOURCES['sunspots'],
                'warning':'This is observed temporal correlation, not an action-causal world model.'})
    return res


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--seed',type=int,default=20261030)
    args=p.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    db=out/'worldcore_real_training.db';db.unlink(missing_ok=True)
    report={'seed':args.seed,'data_origin':'Bundled public research datasets, independently verified publisher URLs',
            'sklearn_version':sklearn.__version__,'statsmodels_version':statsmodels.__version__,
            'real_datasets':{},'notes':['No generative LLM or learned foundation model weights.','Independent holdouts excluded from training database.',
            'Time series evaluated chronologically; random datasets group duplicate feature vectors.',
            'Min-max scaling learned only from training partition; test values clipped to [0,1].']}
    with WorldCore(db) as w:
        for name,x,y,split in real_datasets():
            report['real_datasets'][name]=assess(w,name,x,y,split,args.seed)
        report['sunspot_transition']=train_transitions(w)
        report['database_integrity']=w.db.execute('PRAGMA integrity_check').fetchone()[0]
    (out/'real_data_learning_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
    for k,r in report['real_datasets'].items():
        print(k,r['train_rows'],r['test_rows'],'brier',round(r['brier'],4),'baseline',round(r['baseline_brier'],4),'beat',r['beat_constant_brier_baseline'])
    return report
if __name__=='__main__':main()
