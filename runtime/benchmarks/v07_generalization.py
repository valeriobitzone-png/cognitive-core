"""Reproducible independent-environment and genuine historical holdout study.

The synthetic motion task is a unit-like mechanics test, not world-scale AGI.
Historical data are packaged in statsmodels. Nothing is fetched from the Internet.
"""
import json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from worldcore.dynamics import train_family_dynamics


def run():
    out={}
    # Three training environments + completely held-out fourth environment,
    # with coordinate pairs shifted between environments.
    rows=[]
    for e,env in enumerate(('arena_a','arena_b','arena_c','arena_d')):
        for action,dx,dy in [('east',1.,0.),('north',0.,1.),('west',-1.,0.)]:
            for i in range(40):
                x=float((i*11+e*7)%67);y=float((i*5+e*11)%19)
                rows.append({'environment':env,'action':action,'before':{'x':x,'y':y},
                             'after':{'x':x+dx,'y':y+dy},'source':'observed'})
    a=train_family_dynamics(rows)
    out['synthetic_motion']={'provenance':'generated deterministic known mechanics, NOT real sensor data',
        'n':len(rows),'validation':a['validation'],
        'actions':{k:{'status':v['status'],'holdout_environment':v.get('model',{}).get('holdout_environment'),
            'holdout_mae':v.get('model',{}).get('heldout_mae'),
            'persistence_mae':v.get('model',{}).get('persistence_mae'),
            'improvement':v.get('model',{}).get('improvement_vs_persistence')} for k,v in a['actions'].items()}}
    try:
        import statsmodels.api as sm
    except ImportError as ex:
        out['historical_data']={'status':'skipped','reason':'statsmodels optional benchmark dependency not installed'}
        return out
    sun=sm.datasets.sunspots.load_pandas().data
    samples=[]
    for i in range(1,len(sun)-1):
        year=int(sun.iloc[i]['YEAR'])
        env='1700_1799' if year<1800 else '1800_1899' if year<1900 else '1900_2008'
        prev=float(sun.iloc[i-1]['SUNACTIVITY']);current=float(sun.iloc[i]['SUNACTIVITY']);nxt=float(sun.iloc[i+1]['SUNACTIVITY'])
        samples.append({'environment':env,'action':'advance_year','before':{'activity':current,'change':current-prev},
                        'after':{'activity':nxt,'change':nxt-current},'source':'observed'})
    b=train_family_dynamics(samples,min_train=30,min_holdout=20)
    out['sunspots']={'provenance':'statsmodels.datasets.sunspots bundled observations','samples':len(samples),
        'holdout':'1900_2008','model_result':{k:{'status':v['status'],
        'holdout_mae':v.get('model',{}).get('heldout_mae'),
        'baseline_mae':v.get('model',{}).get('persistence_mae'),
        'improvement':v.get('model',{}).get('improvement_vs_persistence')} for k,v in b['actions'].items()}}
    macro=sm.datasets.macrodata.load_pandas().data
    samples=[]
    for i in range(1,len(macro)-1):
        year=int(macro.iloc[i]['year'])
        env='1959_1974' if year<1975 else '1975_1990' if year<1991 else '1991_2009'
        old=float(macro.iloc[i-1]['realgdp']);now=float(macro.iloc[i]['realgdp']);new=float(macro.iloc[i+1]['realgdp'])
        un=float(macro.iloc[i]['unemp']);un2=float(macro.iloc[i+1]['unemp'])
        samples.append({'environment':env,'action':'advance_quarter',
            'before':{'growth':math.log(now/old),'unemployment':un},
            'after':{'growth':math.log(new/now),'unemployment':un2},'source':'observed'})
    c=train_family_dynamics(samples,min_train=30,min_holdout=20)
    out['macrodata']={'provenance':'statsmodels.datasets.macrodata bundled U.S. quarterly macro observations',
         'samples':len(samples),'holdout':'1991_2009',
         'model_result':{k:{'status':v['status'],'holdout_mae':v.get('model',{}).get('heldout_mae'),
         'baseline_mae':v.get('model',{}).get('persistence_mae'),
         'improvement':v.get('model',{}).get('improvement_vs_persistence')} for k,v in c['actions'].items()}}
    out['limitations']=['Training on 2 past historical eras does not prove forecasting the future or general transfer',
       'Simple ridge model of numeric deltas; no latent neural world model, no semantic vision',
       'Only actions with >=10% improvement vs last-state persistence are deployable',
       'No random shuffled split; holdout complete last era or whole held-out arena']
    return out

if __name__=='__main__':
    data=run();dest=Path(__file__).resolve().parents[1]/'training-artifacts/v07_generalization_benchmark.json'
    dest.write_text(json.dumps(data,indent=2,ensure_ascii=False))
    print(json.dumps(data,indent=2,ensure_ascii=False))
