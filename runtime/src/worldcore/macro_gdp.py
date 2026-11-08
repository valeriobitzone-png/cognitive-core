"""Historical GDP-level toy model serialization; NOT live economic or trading advice."""
from __future__ import annotations
import json,math
from pathlib import Path

FEATURE_NAMES=('current_real_gdp','last_quarter_delta','prior_quarter_delta','unemployment',
               'inflation','real_interest','treasury_bill_rate','consumption_log_growth')

def predict_next_gdp(feature_values,model_json):
    """Pure-Python inference of an explicitly historical exploratory ridge model."""
    if isinstance(model_json,(str,Path)):
        model_json=json.loads(Path(model_json).read_text())
    if not isinstance(feature_values,dict) or set(feature_values)!=set(FEATURE_NAMES):
        raise ValueError('eight explicitly defined macroeconomic input fields required')
    xs=[]
    for key in FEATURE_NAMES:
        v=feature_values[key]
        if type(v) not in (int,float) or not math.isfinite(v):raise ValueError('inputs must be finite numbers')
        xs.append(float(v))
    if len(model_json['coef'])!=len(xs):raise ValueError('bad model coefficients')
    z=[(x-m)/scale for x,m,scale in zip(xs,model_json['mean'],model_json['scale'])]
    pred=float(model_json['intercept']+sum(a*b for a,b in zip(model_json['coef'],z)))
    return {'status':'exploratory','predicted_next_real_gdp':pred,
      'unit':'real GDP billions chained 2005 U.S. dollars, statsmodels macrodata convention',
      'model_id':model_json['model_id'],'trained_through':model_json['trained_through'],
      'warning':'Historical exploratory model, potentially obsolete; not a forecast for live finance/trading'}
