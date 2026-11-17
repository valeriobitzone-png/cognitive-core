"""Predict whether a pull request will be merged from features known at open time.

Observational only. Temporal holdout by createdAt. Baselines: majority class and
Markov-not-applicable → use label-prior majority and size-bin majority.
"""
from __future__ import annotations
import math
import statistics
from collections import Counter, defaultdict
from .worldmodel import _valid_atom
from .dynamics import _finite, _solve, _parse_observed_at
from .next_event import _accuracy


def _fit_binary(rows, keys, reg=0.05):
    X = [[1.0] + [float(r['features'][k]) for k in keys] for r in rows]
    y = [1.0 if r['merged'] else 0.0 for r in rows]
    n = len(keys) + 1
    gram = [[sum(X[i][a] * X[i][b] for i in range(len(X))) + (reg if a == b else 0.0)
             for b in range(n)] for a in range(n)]
    rhs = [sum(X[i][a] * y[i] for i in range(len(X))) for a in range(n)]
    try:
        w = _solve(gram, rhs)
    except ValueError:
        w = [statistics.fmean(y)] + [0.0] * len(keys)
    return {'keys': keys, 'weights': w, 'train_size': len(rows)}


def _score(model, features):
    v = [1.0] + [float(features[k]) for k in model['keys']]
    return sum(a * b for a, b in zip(model['weights'], v))


def _clean_prs(samples):
    rows = []
    for r in samples:
        if not isinstance(r, dict) or r.get('source') != 'observed':
            continue
        if 'merged' not in r or type(r['merged']) is not bool:
            continue
        # only resolved PRs (closed or merged) for supervised labels
        if r.get('resolved') is False:
            continue
        try:
            env = _valid_atom(r.get('environment'), 'environment')
        except Exception:
            continue
        at = _parse_observed_at(r.get('observed_at') or r.get('created_at'))
        feats = r.get('features') or {}
        if not isinstance(feats, dict) or not 1 <= len(feats) <= 24:
            continue
        if any(not isinstance(k, str) or not _finite(v) for k, v in feats.items()):
            continue
        rows.append({'environment': env, 'merged': r['merged'], 'observed_at': at,
                     'features': {k: float(v) for k, v in feats.items()}})
    return rows


def _temporal_split(rows, min_train, min_holdout):
    ordered = sorted(rows, key=lambda r: (r['observed_at'] is None, r['observed_at'] or 0.0))
    if len(ordered) < min_train + min_holdout:
        return None, None
    cut = max(min_train, int(len(ordered) * 0.70))
    if len(ordered) - cut < min_holdout:
        cut = len(ordered) - min_holdout
    if cut < min_train:
        return None, None
    return ordered[:cut], ordered[cut:]


def train_pr_merge(samples, *, min_train=40, min_holdout=20, min_environments=3, holdout_mode='temporal'):
    if holdout_mode not in ('temporal', 'environment'):
        raise ValueError('holdout_mode must be temporal or environment')
    rows = _clean_prs(samples)
    envs = sorted({r['environment'] for r in rows})
    if len(envs) < min_environments:
        return {'status': 'abstain', 'reason': 'need_independent_environments', 'environments': len(envs), 'n': len(rows)}
    if holdout_mode == 'environment':
        held = envs[-1]
        train = [r for r in rows if r['environment'] != held]
        test = [r for r in rows if r['environment'] == held]
        if len(train) < min_train or len(test) < min_holdout:
            return {'status': 'abstain', 'reason': 'insufficient_disjoint_train_test', 'train': len(train), 'test': len(test)}
        meta = {'holdout_mode': 'environment', 'holdout_environment': held}
    else:
        # require timestamps
        rows = [r for r in rows if r['observed_at'] is not None]
        train, test = _temporal_split(rows, min_train, min_holdout)
        if train is None:
            return {'status': 'abstain', 'reason': 'insufficient_temporal_train_test', 'n': len(rows)}
        meta = {'holdout_mode': 'temporal'}
    keys = sorted(set.intersection(*[set(r['features']) for r in train])) if train else []
    train = [{**r, 'features': {k: r['features'][k] for k in keys}} for r in train]
    test = [{**r, 'features': {k: r['features'][k] for k in keys if k in r['features']}} for r in test]
    test = [r for r in test if set(r['features']) >= set(keys)]
    model = _fit_binary(train, keys)
    preds = [(_score(model, r['features']) >= 0.5) for r in test]
    actuals = [r['merged'] for r in test]
    acc = _accuracy(preds, actuals)
    maj = Counter(r['merged'] for r in train).most_common(1)[0][0]
    maj_acc = _accuracy([maj] * len(test), actuals)
    # size-bin majority baseline: bin by log1p(changed_files) if present else constant
    bin_key = 'log_changed_files' if 'log_changed_files' in keys else (keys[0] if keys else None)
    bin_maj = {}
    if bin_key:
        buckets = defaultdict(list)
        for r in train:
            b = int(r['features'][bin_key])
            buckets[b].append(r['merged'])
        for b, vals in buckets.items():
            bin_maj[b] = Counter(vals).most_common(1)[0][0]
        bin_preds = [bin_maj.get(int(r['features'].get(bin_key, 0)), maj) for r in test]
        bin_acc = _accuracy(bin_preds, actuals)
    else:
        bin_acc = maj_acc
    gain_maj = acc - maj_acc
    gain_bin = acc - bin_acc
    accepted = gain_maj >= 0.02 and gain_bin >= 0.02
    model.update({**meta, 'heldout_count': len(test), 'accuracy': acc,
                  'majority_accuracy': maj_acc, 'sizebin_accuracy': bin_acc,
                  'gain_vs_majority': gain_maj, 'gain_vs_sizebin': gain_bin,
                  'majority_class': maj, 'positive_rate_train': statistics.fmean(1.0 if r['merged'] else 0.0 for r in train)})
    return {'status': 'validated' if accepted else 'rejected_no_baseline_gain', 'model': model,
            'n': len(rows), 'environments': len(envs), 'note': 'PR merge scores are observational'}


def train_pr_merge_per_environment(samples, *, min_train=30, min_holdout=15):
    rows = _clean_prs(samples)
    by = defaultdict(list)
    for r in rows:
        by[r['environment']].append(r)
    out = {}
    for env, erows in sorted(by.items()):
        res = train_pr_merge(
            [{'environment': env, 'merged': r['merged'], 'observed_at': r['observed_at'],
              'features': r['features'], 'source': 'observed', 'resolved': True} for r in erows],
            min_train=min_train, min_holdout=min_holdout, min_environments=1, holdout_mode='temporal')
        out[env] = res
    return {'environments': out, 'n': len(rows)}


def export_pr_merge_weights(model_bundle):
    """Compact JSON-serializable weights for on-device use."""
    if model_bundle.get('status') != 'validated':
        raise ValueError('only validated models export')
    m = model_bundle['model']
    return {'kind': 'pr_merge_ridge_v1', 'keys': m['keys'], 'weights': m['weights'],
            'threshold': 0.5, 'holdout_accuracy': m.get('accuracy'),
            'train_size': m.get('train_size')}
