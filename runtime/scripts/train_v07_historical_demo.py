"""Train a tiny, bounded observed solar-activity dynamics demo on statsmodels data.

The model is a linear numeric delta model, not a general world model, not AGI,
not an astrophysical forecasting service. Real historical data; no web scrape.
"""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from worldcore import WorldCore

def run():
    import statsmodels.api as sm
    sun=sm.datasets.sunspots.load_pandas().data
    samples=[]
    for i in range(1,len(sun)-1):
        year=int(sun.iloc[i]['YEAR'])
        env='1700_1799' if year<1800 else '1800_1899' if year<1900 else '1900_2008'
        prev=float(sun.iloc[i-1]['SUNACTIVITY']);this=float(sun.iloc[i]['SUNACTIVITY']);nxt=float(sun.iloc[i+1]['SUNACTIVITY'])
        samples.append({'environment':env,'action':'advance_year','before':{'activity':this,'change':this-prev},
                        'after':{'activity':nxt,'change':nxt-this},'source':'observed'})
    db=ROOT/'training-artifacts/v07_learned_world_models.db'
    if db.exists():db.unlink()
    with WorldCore(db) as w:
        r=w.train_shared_dynamics('research_demo','solar_activity',samples,space='historical')
        if r['status']!='trained':raise RuntimeError('historical model failed acceptance gate')
        p=w.predict_shared_dynamics('research_demo','solar_activity',{'activity':50.0,'change':5.0},'advance_year',space='historical')
        stat=w.db.execute('PRAGMA integrity_check').fetchone()[0]
        assert stat=='ok' and p['status']=='predicted'
    report={'data_provenance':'statsmodels.datasets.sunspots, historical annual 1700-2008',
         'model_type':'action-conditioned linear numeric delta, ridge regularization',
         'dataset_size':len(samples),'train_group':'1700-1899','holdout_group':'1900-2008',
         'validation':{'holdout_mae':r['validation']['actions']['advance_year']['model']['heldout_mae'],
            'persistence_mae':r['validation']['actions']['advance_year']['model']['persistence_mae'],
            'relative_improvement':r['validation']['actions']['advance_year']['model']['improvement_vs_persistence']},
         'sample_query':p,'db_integrity':stat,'db_path':str(db.name),
         'limitations':'Historical retrospective generalization only; not a general AI or reliable physical forecast'}
    (ROOT/'training-artifacts/v07_historical_training_report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=='__main__':run()
