"""Local reproducible benchmark. Results vary by CPU/FS and are not competitor claims."""
from __future__ import annotations
import json
import statistics
import tempfile
import time
from pathlib import Path
from worldcore import WorldCore

with tempfile.TemporaryDirectory() as folder:
    db=Path(folder)/'perf.db'
    start=time.perf_counter()
    with WorldCore(db) as wc:
        setup_s=time.perf_counter()-start
        start=time.perf_counter()
        for i in range(1000):
            wc.remember('benchmark', f'note.{i}',f'memory topic{i} contains score {i}')
        writes_s=time.perf_counter()-start
        timings=[]
        for i in range(100):
            start=time.perf_counter()
            matches=wc.recall('benchmark',f'topic{i*10}',limit=5)
            timings.append((time.perf_counter()-start)*1000)
            assert matches and matches[0]['fact_key']==f'note.{i*10}'
        counterfactual=[]
        wc.set_state('benchmark','remaining',15)
        for i in range(100):
            start=time.perf_counter()
            sim=wc.simulate('benchmark',[{'op':'add','key':'remaining','value':-1}])
            counterfactual.append((time.perf_counter()-start)*1000)
            assert sim['predicted']['remaining']==14 and wc.state('benchmark')['remaining']==15
        result={'cold_start_ms':round(setup_s*1000,2),'write_1000_ms':round(writes_s*1000,2),
                'recall_p50_ms':round(statistics.median(timings),2),'recall_p95_ms':round(sorted(timings)[94],2),
                'simulation_p50_ms':round(statistics.median(counterfactual),2),'ftS5':wc.fts_enabled,
                'database_integrity':wc.db.execute('PRAGMA integrity_check').fetchone()[0],
                'caveat':'Synthetic exact-term recall only; no semantic or cross-framework benchmark.'}
        print(json.dumps(result,indent=2))
