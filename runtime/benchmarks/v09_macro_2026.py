"""Vintage-aware warning: current-vintage GDP sequence, NOT genuine point-in-time train/test.
Values from FRED GDPC1, 2026-10-29; quarter dates in source list.
This compares two deterministic BASELINES, not a learned WorldCore macro forecast.
"""
import json
from pathlib import Path
SERIES=[('2025Q3',24112.966),('2025Q4',24125.479),('2026Q1',24274.383),('2026Q2',24408.011),('2026Q3',24611.077)]
URL='https://fred.stlouisfed.org/graph/?g=GplE'
BEA='https://www.bea.gov/news/2026/gdp-advance-estimate-3rd-quarter-2026'

def run():
    rows=[]
    for i in range(2,len(SERIES)):
        q,actual=SERIES[i];previous=SERIES[i-1][1];before=SERIES[i-2][1]
        persists=previous;momentum=previous+(previous-before)
        rows.append({'quarter':q,'actual':actual,'persistence':round(persists,3), 'last_change':round(momentum,3),
                     'absolute_error_persistence':round(abs(actual-persists),3),
                     'absolute_error_last_change':round(abs(actual-momentum),3)})
    p=sum(r['absolute_error_persistence'] for r in rows);m=sum(r['absolute_error_last_change'] for r in rows)
    return {'data_source':URL,'release_source':BEA,'release_date':'2026-10-29',
            'unit':'billions chained 2017 USD, SAAR','method':'rolling forecasts with no learned model; current revised vintage; only three outcomes',
            'rows':rows,'mean_absolute_error_persistence':p/len(rows),'mean_absolute_error_last_change':m/len(rows),
            'relative_improvement_last_change':1-m/p,
            'limits':['Not out-of-vintage point-in-time; revisions cause look-ahead risk','Only three forecast errors','No news-market correlation','No trade or live forecast validation']}
if __name__=='__main__':
 result=run();p=Path('training-artifacts/v09_macro_2026_report.json');p.parent.mkdir(exist_ok=True,parents=True);p.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
