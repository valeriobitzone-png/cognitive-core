"""Measure the baseline before considering model fine-tuning.

Accuracy here reflects these *hand-authored examples*, not real-world performance.
"""
from pathlib import Path
import json
import statistics
import time
from .decision import DecisionPlane
from .config import Settings


def evaluate(path: Path, settings: Settings):
    plane=DecisionPlane(settings)
    samples=[json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]
    successes=0;rows=[]
    for sample in samples:
        t=time.perf_counter()
        prediction=plane.decide(sample['event'])
        latency=(time.perf_counter()-t)*1000
        correct=prediction.action==sample['expected']
        successes+=int(correct)
        rows.append({'expected':sample['expected'],'got':prediction.action,
                     'correct':correct,'latency_ms':round(latency,3),
                     'model_used':prediction.model_used})
    return {'sample_count':len(samples),'accuracy':round(successes/max(1,len(samples)),4),
            'latency_ms_p50':round(statistics.median([r['latency_ms'] for r in rows]),3) if rows else None,
            'mistakes':[r for r in rows if not r['correct']],
            'model_calls':sum(r['model_used'] for r in rows)}
