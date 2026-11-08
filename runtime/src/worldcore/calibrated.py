"""Chronological numeric prediction with split-conformal uncertainty.

This models observed conditional effects, not identified causal interventions.
Temporal splitting prevents known label leakage; it does not ensure stationarity
or exchangeability. Coverage must be measured again on future observations.
"""
from __future__ import annotations
import hashlib
import json
import math
import statistics
from .dynamics import _fit, _predict, _numeric_state


def wilson(successes, n, z=1.96):
    if not n:
        return [0.0, 1.0]
    p = successes/n
    center = (p + z*z/(2*n))/(1+z*z/n)
    margin = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/(1+z*z/n)
    return [max(0.0, center-margin), min(1.0, center+margin)]


def train_temporal(samples, *, as_of, coverage=.8):
    from .engine import WorldCoreError, _when
    cutoff = _when(as_of)
    if type(coverage) not in (int, float) or not math.isfinite(coverage) or not .5 <= coverage <= .95:
        raise WorldCoreError('coverage must be finite and between .5 and .95')
    if not isinstance(samples, list) or not 80 <= len(samples) <= 10000:
        raise WorldCoreError('80..10000 timestamped samples required')
    rows = []
    identifiers = set()
    from .worldmodel import _valid_atom
    for source in samples:
        if not isinstance(source, dict):
            raise WorldCoreError('invalid observation')
        if source.get('source') != 'observed':
            continue
        identifier = _valid_atom(source.get('sample_id'), 'sample id')
        if identifier in identifiers:
            raise WorldCoreError('duplicate sample id')
        identifiers.add(identifier)
        before_at, observed_at, available_at = [_when(source.get(k)) if source.get(k) else None
                                                for k in ('before_at', 'observed_at', 'available_at')]
        if None in (before_at, observed_at, available_at) or not before_at < observed_at <= available_at:
            raise WorldCoreError('require before_at < observed_at <= available_at')
        if available_at > cutoff:
            continue
        provenance = source.get('provenance')
        if not isinstance(provenance, str) or not 1 <= len(provenance) <= 500:
            raise WorldCoreError('observation provenance required')
        rows.append({'sample_id': identifier, 'before_at': before_at, 'observed_at': observed_at,
                     'available_at': available_at, 'environment': _valid_atom(source.get('environment'), 'environment'),
                     'action': _valid_atom(source.get('action'), 'action'),
                     'before': _numeric_state(source.get('before')), 'after': _numeric_state(source.get('after')),
                     'provenance': provenance})
    rows.sort(key=lambda r: (r['before_at'], r['sample_id']))
    actions = {}
    for action in sorted({r['action'] for r in rows}):
        group = [r for r in rows if r['action'] == action]
        if len(group) < 80:
            actions[action] = {'status': 'abstain', 'reason': 'insufficient_temporal_observations'}
            continue
        n = len(group)
        train, calibration, test = group[:n*3//5], group[n*3//5:n*4//5], group[n*4//5:]
        if not (max(r['available_at'] for r in train) < calibration[0]['before_at'] and
                max(r['available_at'] for r in calibration) < test[0]['before_at']):
            raise WorldCoreError('label availability overlaps later prediction window')
        keys = sorted(train[0]['before'])
        if any(sorted(r['before']) != keys or sorted(r['after']) != keys for r in group):
            raise WorldCoreError('inconsistent temporal state schema')
        model = _fit(train, keys)
        scales = {k: max(1.0, statistics.pstdev([r['after'][k] for r in train])) for k in keys}
        scores = sorted(max(abs(_predict(model, r['before'])[k]-r['after'][k])/scales[k] for k in keys)
                        for r in calibration)
        rank = math.ceil((len(scores)+1)*coverage)
        if rank > len(scores):
            actions[action] = {'status': 'abstain', 'reason': 'insufficient_calibration'}
            continue
        radius = {k: scores[rank-1]*scales[k] for k in keys}
        hits = 0
        errors, baseline = [], []
        for row in test:
            guess = _predict(model, row['before'])
            hits += all(abs(guess[k]-row['after'][k]) <= radius[k] for k in keys)
            errors.append(statistics.fmean(abs(guess[k]-row['after'][k]) for k in keys))
            baseline.append(statistics.fmean(abs(row['before'][k]-row['after'][k]) for k in keys))
        mae, base = statistics.fmean(errors), statistics.fmean(baseline)
        gain = 1-mae/max(base, 1e-12)
        measured = hits/len(test)
        lower = wilson(hits, len(test))[0]
        accepted = base > 1e-8 and gain >= .1 and measured >= coverage-.1 and lower >= .5
        actions[action] = {'status': 'validated' if accepted else 'rejected', 'model': model,
                           'radius': radius, 'coverage_target': coverage, 'validation_coverage': measured,
                           'coverage_wilson_95': wilson(hits, len(test)), 'validation_count': len(test),
                           'mae': mae, 'persistence_mae': base, 'gain': gain,
                           'train_ids': [r['sample_id'] for r in train],
                           'calibration_ids': [r['sample_id'] for r in calibration],
                           'test_ids': [r['sample_id'] for r in test],
                           'train_available_until': max(r['available_at'] for r in train),
                           'calibration_available_until': max(r['available_at'] for r in calibration),
                           'test_start': test[0]['before_at']}
    return {'as_of': cutoff, 'actions': actions, 'samples_used': len(rows),
            'dataset_sha256': hashlib.sha256(json.dumps(rows, sort_keys=True, allow_nan=False).encode()).hexdigest(),
            'method': 'chronological_fit_calibrate_test_split_conformal',
            'causal_claim': False, 'coverage_assumption': 'exchangeable calibration and future residuals; not assured in temporal/open systems'}


def predict_temporal(bundle, before, action, *, min_confidence=.5, max_width=None):
    from .engine import WorldCoreError
    before = _numeric_state(before)
    if type(min_confidence) not in (int,float) or not math.isfinite(min_confidence) or not 0 <= min_confidence <= 1:
        raise WorldCoreError('invalid confidence gate')
    if max_width is not None and (type(max_width) not in (int,float) or not math.isfinite(max_width) or max_width <= 0):
        raise WorldCoreError('invalid interval width gate')
    entry = bundle['actions'].get(action)
    if not entry or entry['status'] != 'validated':
        return {'status':'abstain', 'reason':'no_validated_temporal_action'}
    if entry['coverage_wilson_95'][0] < min_confidence:
        return {'status':'abstain', 'reason':'confidence_gate'}
    model = entry['model']
    if sorted(before) != model['keys']:
        return {'status':'abstain', 'reason':'unknown_state_schema'}
    if any(not model['train_ranges'][k][0] <= before[k] <= model['train_ranges'][k][1] for k in before):
        return {'status':'abstain', 'reason':'out_of_distribution'}
    if max_width is not None and any(2*r > max_width for r in entry['radius'].values()):
        return {'status':'abstain', 'reason':'interval_too_wide'}
    prediction = _predict(model, before)
    if any(not math.isfinite(v) for v in prediction.values()):
        return {'status':'abstain', 'reason':'nonfinite_prediction'}
    return {'status':'predicted', 'state': prediction,
            'intervals':{k:[v-entry['radius'][k],v+entry['radius'][k]] for k,v in prediction.items()},
            'coverage_target':entry['coverage_target'], 'validation_coverage':entry['validation_coverage'],
            'coverage_wilson_95':entry['coverage_wilson_95'], 'causal_claim':False,
            'action_executed':False, 'warning':bundle['coverage_assumption']}
