"""Next-event family prediction from observed activity sequences.

Learns to anticipate the *next* categorical action (feat/fix/docs/…) from the
current action and numeric context. Pure-Python one-vs-rest ridge scoring.
Validates on temporal or per-environment holdout against majority and Markov-1
baselines. No automatic execution; observational only.
"""
from __future__ import annotations
import math
import statistics
from collections import Counter, defaultdict
from .worldmodel import _valid_atom
from .dynamics import _finite, _solve, _parse_observed_at


def _feature_vector(row, action_index, action_list, numeric_keys):
    """Bias + one-hot current action + numeric fields (bounded)."""
    vec = [1.0]
    for a in action_list:
        vec.append(1.0 if row['action'] == a else 0.0)
    for k in numeric_keys:
        vec.append(float(row['features'][k]))
    return vec


def _fit_ovr(rows, action_list, numeric_keys, reg=0.05):
    """One-vs-rest ridge: for each next-action class, score from features."""
    X = [_feature_vector(r, None, action_list, numeric_keys) for r in rows]
    n_feat = len(X[0])
    models = {}
    for target in action_list:
        y = [1.0 if r['next_action'] == target else 0.0 for r in rows]
        # gram = X^T X + reg I ; b = X^T y
        gram = [[sum(X[i][a] * X[i][b] for i in range(len(X))) + (reg if a == b else 0.0)
                 for b in range(n_feat)] for a in range(n_feat)]
        rhs = [sum(X[i][a] * y[i] for i in range(len(X))) for a in range(n_feat)]
        try:
            weights = _solve(gram, rhs)
        except ValueError:
            weights = [0.0] * n_feat
            weights[0] = statistics.fmean(y) if y else 0.0
        models[target] = weights
    return {'action_list': action_list, 'numeric_keys': numeric_keys, 'weights': models,
            'train_size': len(rows)}


def _predict_action(model, row):
    action_list = model['action_list']
    vec = _feature_vector(row, None, action_list, model['numeric_keys'])
    scores = {}
    for target, w in model['weights'].items():
        scores[target] = sum(a * b for a, b in zip(w, vec))
    # argmax; tie → lexicographic for determinism
    best = max(action_list, key=lambda a: (scores[a], a))
    return best, scores


def _accuracy(preds, actuals):
    if not actuals:
        return 0.0
    return sum(p == a for p, a in zip(preds, actuals)) / len(actuals)


def _majority_baseline(train, test):
    maj = Counter(r['next_action'] for r in train).most_common(1)[0][0]
    return _accuracy([maj] * len(test), [r['next_action'] for r in test]), maj


def _markov_baseline(train, test):
    succ = defaultdict(Counter)
    for r in train:
        succ[r['action']][r['next_action']] += 1
    global_maj = Counter(r['next_action'] for r in train).most_common(1)[0][0]
    preds = []
    for r in test:
        c = succ.get(r['action'])
        if c:
            preds.append(c.most_common(1)[0][0])
        else:
            preds.append(global_maj)
    return _accuracy(preds, [r['next_action'] for r in test])


def _clean_transitions(samples, *, require_time=False):
    """Build (current → next) transitions within each environment, time-ordered."""
    if not isinstance(samples, list) or len(samples) > 500000:
        raise ValueError('invalid sample list')
    by_env = defaultdict(list)
    for r in samples:
        if not isinstance(r, dict) or r.get('source') != 'observed':
            continue
        try:
            env = _valid_atom(r.get('environment'), 'environment')
            action = _valid_atom(r.get('action'), 'action')
        except Exception:
            continue
        at = _parse_observed_at(r.get('observed_at', r.get('at')))
        if require_time and at is None:
            continue
        feats = r.get('features') or r.get('before') or {}
        if not isinstance(feats, dict) or len(feats) > 24:
            continue
        if any(not isinstance(k, str) or len(k) > 40 or not _finite(v) for k, v in feats.items()):
            continue
        by_env[env].append({'environment': env, 'action': action, 'observed_at': at,
                            'features': {k: float(v) for k, v in feats.items()}})
    transitions = []
    for env, rows in by_env.items():
        rows = sorted(rows, key=lambda x: (x['observed_at'] is None, x['observed_at'] or 0.0, x['action']))
        for i in range(len(rows) - 1):
            cur, nxt = rows[i], rows[i + 1]
            transitions.append({
                'environment': env,
                'action': cur['action'],
                'next_action': nxt['action'],
                'observed_at': cur['observed_at'],
                'features': cur['features'],
            })
    return transitions


def _temporal_split(rows, min_train, min_holdout):
    ordered = sorted(rows, key=lambda r: (r['observed_at'], r['environment'], r['action']))
    if len(ordered) < min_train + min_holdout:
        return None, None
    cut = max(min_train, int(len(ordered) * 0.70))
    if len(ordered) - cut < min_holdout:
        cut = len(ordered) - min_holdout
    if cut < min_train:
        return None, None
    return ordered[:cut], ordered[cut:]


def train_next_event(samples, *, min_train=50, min_holdout=20, min_environments=3,
                     holdout_mode='temporal', scope='shared'):
    """Train next-action predictor.

    holdout_mode: 'temporal' (default) or 'environment' (hold out last alphabetical env).
    scope: 'shared' across environments, or ignored when calling train_next_event_per_environment.
    """
    if holdout_mode not in ('temporal', 'environment'):
        raise ValueError('holdout_mode must be temporal or environment')
    if not isinstance(min_train, int) or min_train < 1:
        raise ValueError('invalid min_train')
    if not isinstance(min_holdout, int) or min_holdout < 1:
        raise ValueError('invalid min_holdout')
    if not isinstance(min_environments, int) or min_environments < 1:
        raise ValueError('invalid min_environments')

    transitions = _clean_transitions(samples, require_time=(holdout_mode == 'temporal'))
    envs = sorted({t['environment'] for t in transitions})
    if len(envs) < min_environments:
        return {'status': 'abstain', 'reason': 'need_independent_environments',
                'environments': len(envs), 'count_transitions': len(transitions)}

    if holdout_mode == 'environment':
        held = envs[-1]
        train = [t for t in transitions if t['environment'] != held]
        test = [t for t in transitions if t['environment'] == held]
        if len(train) < min_train or len(test) < min_holdout:
            return {'status': 'abstain', 'reason': 'insufficient_disjoint_train_test',
                    'train': len(train), 'test': len(test), 'holdout_environment': held}
        holdout_meta = {'holdout_mode': 'environment', 'holdout_environment': held}
    else:
        train, test = _temporal_split(transitions, min_train, min_holdout)
        if train is None:
            return {'status': 'abstain', 'reason': 'insufficient_temporal_train_test',
                    'n': len(transitions)}
        holdout_meta = {'holdout_mode': 'temporal',
                        'train_from': train[0]['observed_at'], 'train_to': train[-1]['observed_at'],
                        'holdout_from': test[0]['observed_at'], 'holdout_to': test[-1]['observed_at']}

    # Align feature keys present in both splits
    key_sets = [set(r['features']) for r in train]
    keys = sorted(set.intersection(*key_sets)) if key_sets else []
    train = [t for t in train if set(t['features']) >= set(keys)]
    test = [t for t in test if set(t['features']) >= set(keys)]
    # restrict features to shared keys only
    for t in train + test:
        t['features'] = {k: t['features'][k] for k in keys}

    action_list = sorted({t['action'] for t in train} | {t['next_action'] for t in train})
    if len(action_list) < 2:
        return {'status': 'abstain', 'reason': 'need_2_action_classes', 'actions': action_list}

    model = _fit_ovr(train, action_list, keys)
    preds = []
    for r in test:
        pred, _ = _predict_action(model, r)
        preds.append(pred)
    actuals = [r['next_action'] for r in test]
    acc = _accuracy(preds, actuals)
    maj_acc, maj = _majority_baseline(train, test)
    markov_acc = _markov_baseline(train, test)
    gain_maj = acc - maj_acc
    gain_markov = acc - markov_acc
    # Accept if beats BOTH baselines by ≥ 2 percentage points (anticipation must be real)
    accepted = gain_maj >= 0.02 and gain_markov >= 0.02
    model.update({**holdout_meta, 'heldout_count': len(test),
                  'accuracy': acc, 'majority_accuracy': maj_acc, 'markov_accuracy': markov_acc,
                  'gain_vs_majority': gain_maj, 'gain_vs_markov': gain_markov,
                  'majority_class': maj})
    return {
        'status': 'validated' if accepted else 'rejected_no_baseline_gain',
        'model': model,
        'count_transitions': len(transitions),
        'environments': len(envs),
        'actions': action_list,
        'validation': holdout_meta['holdout_mode'],
        'note': 'Next-event scores are observational; never auto-executed',
    }


def train_next_event_per_environment(samples, *, min_train=50, min_holdout=20):
    """Fit one next-event model per environment (temporal holdout inside each)."""
    transitions = _clean_transitions(samples, require_time=True)
    by_env = defaultdict(list)
    for t in transitions:
        by_env[t['environment']].append(t)
    # Re-inject as samples for train_next_event with min_environments=1
    results = {}
    for env, rows in sorted(by_env.items()):
        # reconstruct pseudo-samples: each transition needs features/action/next via samples API
        # Easier: call internal split on rows directly by fabricating sample list with pairs
        # Build samples as sequential events for this env only
        # We have transitions already; wrap train_next_event by expanding back to events is messy.
        # Inline temporal eval for this env:
        train, test = _temporal_split(rows, min_train, min_holdout)
        if train is None:
            results[env] = {'status': 'abstain', 'reason': 'insufficient_temporal_train_test', 'n': len(rows)}
            continue
        key_sets = [set(r['features']) for r in train]
        keys = sorted(set.intersection(*key_sets)) if key_sets else []
        for t in train + test:
            t['features'] = {k: t['features'][k] for k in keys if k in t['features']}
        action_list = sorted({t['action'] for t in train} | {t['next_action'] for t in train})
        if len(action_list) < 2:
            results[env] = {'status': 'abstain', 'reason': 'need_2_action_classes'}
            continue
        model = _fit_ovr(train, action_list, keys)
        preds = [_predict_action(model, r)[0] for r in test]
        actuals = [r['next_action'] for r in test]
        acc = _accuracy(preds, actuals)
        maj_acc, maj = _majority_baseline(train, test)
        markov_acc = _markov_baseline(train, test)
        gain_maj = acc - maj_acc
        gain_markov = acc - markov_acc
        accepted = gain_maj >= 0.02 and gain_markov >= 0.02
        model.update({'holdout_mode': 'temporal', 'holdout_environment': env,
                      'heldout_count': len(test), 'accuracy': acc,
                      'majority_accuracy': maj_acc, 'markov_accuracy': markov_acc,
                      'gain_vs_majority': gain_maj, 'gain_vs_markov': gain_markov,
                      'majority_class': maj})
        results[env] = {
            'status': 'validated' if accepted else 'rejected_no_baseline_gain',
            'model': model,
            'count_transitions': len(rows),
            'note': 'Per-environment next-event model',
        }
    return {'environments': results, 'count_transitions': len(transitions),
            'validation': 'per_environment_temporal_holdout'}


def predict_next_event(model_bundle, action, features):
    """Predict next action from a validated model bundle returned by train_next_event."""
    if not isinstance(model_bundle, dict) or model_bundle.get('status') != 'validated':
        return {'status': 'abstain', 'reason': 'no_validated_model'}
    model = model_bundle['model']
    action = _valid_atom(action, 'action')
    if not isinstance(features, dict):
        raise ValueError('features must be a dict')
    feats = {}
    for k in model['numeric_keys']:
        if k not in features or not _finite(features[k]):
            return {'status': 'abstain', 'reason': 'missing_feature', 'feature': k}
        feats[k] = float(features[k])
    row = {'action': action, 'features': feats}
    pred, scores = _predict_action(model, row)
    return {'status': 'predicted', 'next_action': pred, 'scores': scores,
            'holdout_accuracy': model.get('accuracy'),
            'requires_confirmation': True}


class NextEventMixin:
    """Persist next-event models alongside learned dynamics."""

    def train_next_event_model(self, owner, family, samples, *, space='default',
                               min_train=50, min_holdout=20, min_environments=3,
                               holdout_mode='temporal'):
        import json
        from datetime import datetime, timezone
        owner, space, family = [_valid_atom(x, 'identifier') for x in (owner, space, family)]
        result = train_next_event(samples, min_train=min_train, min_holdout=min_holdout,
                                  min_environments=min_environments, holdout_mode=holdout_mode)
        if result.get('status') != 'validated':
            return {'status': 'rejected', 'validation': result}
        stamp = datetime.now(timezone.utc).isoformat()
        fam = _valid_atom(f'{family}__nextevent', 'identifier')
        with self._transaction():
            row = self.db.execute(
                'SELECT COALESCE(MAX(version),0) v FROM learned_dynamics WHERE owner=? AND space=? AND family=?',
                (owner, space, fam)).fetchone()
            v = row['v'] + 1
            self.db.execute('INSERT INTO learned_dynamics VALUES (?,?,?,?,?,?)',
                            (owner, space, fam, v, json.dumps(result, sort_keys=True, allow_nan=False), stamp))
        return {'status': 'trained', 'version': v, 'validation': result}

    def predict_next_event_model(self, owner, family, action, features, *, space='default'):
        import json
        owner, space, family = [_valid_atom(x, 'identifier') for x in (owner, space, family)]
        fam = _valid_atom(f'{family}__nextevent', 'identifier')
        with self.lock:
            row = self.db.execute(
                'SELECT version, model_json FROM learned_dynamics WHERE owner=? AND space=? AND family=? ORDER BY version DESC LIMIT 1',
                (owner, space, fam)).fetchone()
        if not row:
            return {'status': 'abstain', 'reason': 'no_trained_model'}
        bundle = json.loads(row['model_json'])
        out = predict_next_event(bundle, action, features)
        if out.get('status') == 'predicted':
            out['model_version'] = row['version']
        return out


def export_next_event_weights(model_bundle):
    """Compact OVR weights for offline/mobile inference."""
    if not isinstance(model_bundle, dict) or model_bundle.get('status') != 'validated':
        raise ValueError('only validated models export')
    m = model_bundle['model']
    return {
        'kind': 'next_event_ovr_v1',
        'action_list': m['action_list'],
        'numeric_keys': m['numeric_keys'],
        'weights': m['weights'],
        'holdout_accuracy': m.get('accuracy'),
        'gain_vs_majority': m.get('gain_vs_majority'),
        'gain_vs_markov': m.get('gain_vs_markov'),
        'train_size': m.get('train_size'),
    }
