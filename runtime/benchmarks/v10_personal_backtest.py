"""Deterministic backtest on synthetic consent-free commute durations.

The separation is chronological; events after the split are never included in training.
This does NOT constitute a real user's travel performance or live traffic estimate.
"""
from __future__ import annotations
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from worldcore import WorldCore

def run():
    start=datetime(2025,6,1,8,0,tzinfo=timezone.utc)
    train=[22,25,26,29,31,36,24,28,32,40,21,30,33,27,34,23,37,29,33,39]
    heldout=[24,25,30,32,35,41,28,33,27,37]
    with TemporaryDirectory() as d,WorldCore(Path(d)/'commute.db') as w:
        for i,v in enumerate(train):
            w.observe_travel('synthetic','home','office',(start+timedelta(days=i)).isoformat(),v)
        forecast=w.travel_forecast('synthetic','home','office')
        # No re-training on the holdout.
        threshold=forecast['minutes']
        coverage=sum(v<=threshold for v in heldout)/len(heldout)
        mae=sum(abs(v-forecast['median_minutes']) for v in heldout)/len(heldout)
        result={'type':'synthetic_chronological_holdout','train_n':len(train),'test_n':len(heldout),
                'forecast_minutes_p80':threshold,'empirical_holdout_coverage':coverage,
                'median_absolute_error_minutes':mae,'caveat':'toy durations, not real traffic data'}
    out=Path('training-artifacts/v10_personal_backtest.json');out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
if __name__=='__main__':run()
