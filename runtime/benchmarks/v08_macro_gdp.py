"""Historical, exploratory real-GDP level forecast with blocked temporal validation.

NOT the same v0.7 benchmark (that modeled GDP growth AND unemployment).
Any parameter choices are exploratory; user has seen benchmark holdouts, so these
are NOT an untouched blind test or evidence for future tradable alpha.
"""
from __future__ import annotations
import json
import numpy as np
from pathlib import Path
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from statsmodels.datasets import macrodata


def dataset():
    d=macrodata.load_pandas().data
    x=[];y=[];baseline=[];drift=[];years=[]
    for i in range(5,len(d)-1):
        row=d.iloc[i];previous=d.iloc[i-1];target=d.iloc[i+1]
        x.append([row.realgdp,row.realgdp-previous.realgdp,previous.realgdp-d.iloc[i-2].realgdp,
                  row.unemp,row.infl,row.realint,row.tbilrate,np.log(row.realcons/previous.realcons)])
        y.append(target.realgdp)
        baseline.append(row.realgdp)
        drift.append(2*row.realgdp-previous.realgdp)
        years.append(int(row.year))
    return (np.array(x,dtype=float),np.array(y),np.array(baseline),np.array(drift),np.array(years))


def run():
    x,y,base,drift,years=dataset()
    folds=[]
    for end,test_end in [(1980,1990),(1990,2000),(2000,2009)]:
        train=years<=end;test=(years>end)&(years<=test_end)
        # Parameter is FIXED across windows; no refitting on evaluation labels.
        m=make_pipeline(StandardScaler(),Ridge(alpha=.1))
        m.fit(x[train],y[train]);p=m.predict(x[test])
        mae=mean_absolute_error(y[test],p);persist=mean_absolute_error(y[test],base[test]);strong=mean_absolute_error(y[test],drift[test])
        folds.append({'training_period':f'1959-{end}','evaluation_period':f'{end+1}-{test_end}',
                      'test_samples':int(test.sum()),'model_mae':float(mae),'persistence_mae':float(persist),
                      'last_change_extrapolation_mae':float(strong),
                      'gain_vs_persistence':float(1-mae/persist),
                      'gain_vs_last_change_extrapolation':float(1-mae/strong),
                      'passes_both_baselines_by_ten_percent':mae<=min(.90*persist,.90*strong)})
    # Preserve earlier test and do not retroactively rewrite failed model.
    train=years<=1995;test=years>1995
    model=make_pipeline(StandardScaler(),Ridge(alpha=.1));model.fit(x[train],y[train]);p=model.predict(x[test])
    mae=mean_absolute_error(y[test],p);base_err=mean_absolute_error(y[test],base[test]);drift_err=mean_absolute_error(y[test],drift[test])
    # Export train-only coefficients; runtime does not depend on sklearn.
    artifact={'model_id':'macro_gdp_ridge_1959_1995_v08','trained_through':1995,
          'feature_names':['current_real_gdp','last_quarter_delta','prior_quarter_delta',
              'unemployment','inflation','real_interest','treasury_bill_rate','consumption_log_growth'],
          'mean':[float(v) for v in model.named_steps['standardscaler'].mean_],
          'scale':[float(v) for v in model.named_steps['standardscaler'].scale_],
          'coef':[float(v) for v in model.named_steps['ridge'].coef_],
          'intercept':float(model.named_steps['ridge'].intercept_),
          'license_notice':'statsmodels macrodata public; check underlying publication attribution before redistribution',
          'training_provenance':'statsmodels.datasets.macrodata, split years <=1995'}
    (Path(__file__).resolve().parents[1]/'training-artifacts/v08_macro_gdp_model.json').write_text(json.dumps(artifact,indent=2))
    result={'dataset':'statsmodels macrodata original public U.S. quarterly data',
           'target':'next quarter real GDP level (NOT v0.7 growth+unemployment target)',
           'parameters':'Ridge(alpha=0.1) on eight lagged/previous-quarter features, fixed across blocked folds',
           'regime':'exploratory; test windows inspected during method development; not blind',
           'eval_1996_2009':{'count':int(test.sum()),'mae':float(mae),'persistence_mae':float(base_err),
              'drift_mae':float(drift_err),'gain_vs_persistence':float(1-mae/base_err),
              'gain_vs_drift':float(1-mae/drift_err)},
           'walk_forward_folds':folds,
           'outcome':'Conditional performance, no guarantee of future prediction or economic trading benefit',
           'limitations':['Data end in 2009; no validation on contemporary economic regimes',
             'GDP levels have trend: persistence is weak; compare to last-change extrapolation',
             'Performance changes across windows; not consistently >10% versus stronger baseline',
             'This does NOT repair the separate v0.7 macro growth/unemployment failure']}
    return result

if __name__=='__main__':
    result=run();dst=Path(__file__).resolve().parents[1]/'training-artifacts/v08_macro_gdp_results.json';dst.write_text(json.dumps(result,indent=2,ensure_ascii=False));print(json.dumps(result,indent=2))
