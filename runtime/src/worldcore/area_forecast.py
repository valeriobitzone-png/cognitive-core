"""Predict the primary code area touched by the next activity event.

Areas: code|test|docs|ci|other. Uses one-vs-rest ridge like next_event.
"""

from __future__ import annotations
from collections import Counter, defaultdict
from .worldmodel import _valid_atom
from .dynamics import _finite, _parse_observed_at
from .next_event import (
    _fit_ovr,
    _predict_action,
    _accuracy,
    _majority_baseline,
    _markov_baseline,
    _temporal_split,
)

AREAS = ('code', 'test', 'docs', 'ci', 'other')


def _clean(samples, require_time=True):
    by_env = defaultdict(list)
    for r in samples:
        if not isinstance(r, dict) or r.get('source') != 'observed':
            continue
        area = r.get('area') or r.get('action')
        if area not in AREAS:
            continue
        try:
            env = _valid_atom(r.get('environment'), 'environment')
        except Exception:
            continue
        at = _parse_observed_at(r.get('observed_at'))
        if require_time and at is None:
            continue
        feats = r.get('features') or {}
        if not isinstance(feats, dict) or not 1 <= len(feats) <= 24:
            continue
        if any(not isinstance(k, str) or not _finite(v) for k, v in feats.items()):
            continue
        by_env[env].append({'environment': env, 'action': area, 'observed_at': at, 'features': {k: float(v) for k, v in feats.items()}})
    transitions = []
    for env, rows in by_env.items():
        rows = sorted(rows, key=lambda x: (x['observed_at'] or 0.0, x['action']))
        for i in range(len(rows) - 1):
            cur, nxt = rows[i], rows[i + 1]
            transitions.append(
                {
                    'environment': env,
                    'action': cur['action'],
                    'next_action': nxt['action'],
                    'observed_at': cur['observed_at'],
                    'features': cur['features'],
                }
            )
    return transitions


def train_area_forecast(samples, *, min_train=40, min_holdout=20, min_environments=3, holdout_mode='temporal'):
    transitions = _clean(samples, require_time=(holdout_mode == 'temporal'))
    envs = sorted({t['environment'] for t in transitions})
    if len(envs) < min_environments:
        return {'status': 'abstain', 'reason': 'need_independent_environments', 'environments': len(envs)}
    if holdout_mode == 'environment':
        held = envs[-1]
        train = [t for t in transitions if t['environment'] != held]
        test = [t for t in transitions if t['environment'] == held]
        if len(train) < min_train or len(test) < min_holdout:
            return {'status': 'abstain', 'reason': 'insufficient_disjoint_train_test', 'train': len(train), 'test': len(test)}
        meta = {'holdout_mode': 'environment', 'holdout_environment': held}
    else:
        train, test = _temporal_split(transitions, min_train, min_holdout)
        if train is None:
            return {'status': 'abstain', 'reason': 'insufficient_temporal_train_test', 'n': len(transitions)}
        meta = {'holdout_mode': 'temporal'}
    keys = sorted(set.intersection(*[set(r['features']) for r in train])) if train else []
    for t in train + test:
        t['features'] = {k: t['features'][k] for k in keys if k in t['features']}
    train = [t for t in train if set(t['features']) >= set(keys)]
    test = [t for t in test if set(t['features']) >= set(keys)]
    action_list = sorted({t['action'] for t in train} | {t['next_action'] for t in train})
    if len(action_list) < 2:
        return {'status': 'abstain', 'reason': 'need_2_areas'}
    model = _fit_ovr(train, action_list, keys)
    preds = [_predict_action(model, r)[0] for r in test]
    actuals = [r['next_action'] for r in test]
    acc = _accuracy(preds, actuals)
    maj_acc, maj = _majority_baseline(train, test)
    markov_acc = _markov_baseline(train, test)
    gain_maj = acc - maj_acc
    gain_markov = acc - markov_acc
    accepted = gain_maj >= 0.02 and gain_markov >= 0.02
    model.update(
        {
            **meta,
            'heldout_count': len(test),
            'accuracy': acc,
            'majority_accuracy': maj_acc,
            'markov_accuracy': markov_acc,
            'gain_vs_majority': gain_maj,
            'gain_vs_markov': gain_markov,
            'majority_class': maj,
        }
    )
    return {'status': 'validated' if accepted else 'rejected_no_baseline_gain', 'model': model, 'areas': action_list, 'n_transitions': len(transitions), 'note': 'Area forecast is observational'}


def export_area_weights(model_bundle):
    if model_bundle.get('status') != 'validated':
        raise ValueError('only validated models export')
    m = model_bundle['model']
    return {
        'kind': 'area_forecast_ovr_v1',
        'action_list': m['action_list'],
        'numeric_keys': m['numeric_keys'],
        'weights': m['weights'],
        'holdout_accuracy': m.get('accuracy'),
        'train_size': m.get('train_size'),
    }
