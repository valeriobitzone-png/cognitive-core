"""Quality review of software repositories without using stars or marketing claims."""
from __future__ import annotations

WEIGHTS={'ci':16,'tests':22,'docs':12,'license':8,'recent_maintenance':12,
         'security_policy':10,'reproducible_release':10,'modularity':10}


def score_repository(signals:dict)->dict:
    """Each signal: true/false/None (not checked). Unknown != fail != pass."""
    if not isinstance(signals,dict) or any(k not in WEIGHTS for k in signals):
        raise ValueError('unknown quality signal')
    if any(v is not None and type(v) is not bool for v in signals.values()):
        raise ValueError('quality signals require true, false or null')
    verified={k:v for k,v in signals.items() if v is not None}
    tested_weight=sum(WEIGHTS[k] for k in verified)
    passed_weight=sum(WEIGHTS[k] for k,v in verified.items() if v)
    # Never extrapolate unknown fields to a full rating.
    return {'reviewed_weight':tested_weight,'positive_weight':passed_weight,
            'review_coverage':round(tested_weight/100,3),
            'confirmed_fraction':round(passed_weight/max(1,tested_weight),3),
            'eligible_for_quality_ranking':tested_weight>=70 and not(signals.get('tests') is False),
            'unreviewed':[k for k in WEIGHTS if k not in verified]}
