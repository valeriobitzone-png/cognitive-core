"""PR-merge and area-forecast anticipation tests."""
import math
from datetime import datetime, timedelta, timezone
from worldcore import WorldCore
from worldcore.pr_outcome import train_pr_merge, export_pr_merge_weights
from worldcore.area_forecast import train_area_forecast, export_area_weights
from worldcore.next_event import export_next_event_weights, train_next_event


def _iso(i):
    return (datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=i)).isoformat()


def pr_samples():
    """Merge iff score = -2*log_changed + 3*review_count - 4*has_bug > 0 — not recoverable by majority/sizebin alone."""
    rows = []
    t = 0
    for env in ('r1', 'r2', 'r3'):
        for i in range(50):
            changed = 1 + (i % 15)
            bug = 1.0 if (i % 7 == 0) else 0.0
            reviews = float((i % 5))  # 0..4
            log_c = math.log1p(changed)
            score = -2.0 * log_c + 3.0 * reviews - 4.0 * bug
            merged = score > 0
            rows.append({
                'environment': env, 'merged': merged, 'resolved': True, 'source': 'observed',
                'observed_at': _iso(t),
                'features': {
                    'log_changed_files': log_c,
                    'has_bug_label': bug,
                    'log_additions': math.log1p(changed * 8),
                    'n_labels': 1.0 + bug,
                    'review_count': reviews,
                },
            })
            t += 1
    return rows


def area_samples():
    """Next area after 'test' depends on signal (>=3 → docs else code); Markov cannot solve."""
    rows = []
    t = 0
    for env in ('a1', 'a2', 'a3'):
        for i in range(80):
            gap = float(i % 6)
            if i % 2 == 0:
                rows.append({'environment': env, 'area': 'test', 'source': 'observed', 'observed_at': _iso(t),
                             'features': {'days_gap': gap, 'frac_test': 0.5, 'signal': gap}})
            else:
                nxt = 'docs' if gap >= 3 else 'code'
                rows.append({'environment': env, 'area': nxt, 'source': 'observed', 'observed_at': _iso(t),
                             'features': {'days_gap': 0.0, 'frac_test': 0.2, 'signal': 0.0}})
            t += 1
    return rows


def test_pr_merge_validates_and_exports():
    d = train_pr_merge(pr_samples(), min_train=50, min_holdout=20, min_environments=3)
    assert d['status'] == 'validated', (d.get('status'), d.get('model', {}).get('accuracy'),
                                        d.get('model', {}).get('majority_accuracy'),
                                        d.get('model', {}).get('sizebin_accuracy'),
                                        d.get('model', {}).get('gain_vs_majority'),
                                        d.get('model', {}).get('gain_vs_sizebin'))
    exp = export_pr_merge_weights(d)
    assert exp['kind'] == 'pr_merge_ridge_v1' and len(exp['weights']) == len(exp['keys']) + 1


def test_area_forecast_validates_and_exports():
    d = train_area_forecast(area_samples(), min_train=40, min_holdout=20)
    assert d['status'] == 'validated', (d.get('status'), d.get('model', {}).get('accuracy'),
                                        d.get('model', {}).get('majority_accuracy'),
                                        d.get('model', {}).get('markov_accuracy'))
    exp = export_area_weights(d)
    assert exp['kind'] == 'area_forecast_ovr_v1'


def test_next_event_export():
    rows = []
    t = 0
    for env in ('x', 'y', 'z'):
        for i in range(80):
            gap = float(i % 6)
            if i % 2 == 0:
                rows.append({'environment': env, 'action': 'feat', 'source': 'observed', 'observed_at': _iso(t),
                             'features': {'days_gap': gap, 'frac_feat': 0.5, 'signal': gap}})
            else:
                rows.append({'environment': env, 'action': 'docs' if gap >= 3 else 'test', 'source': 'observed',
                             'observed_at': _iso(t), 'features': {'days_gap': 0.0, 'frac_feat': 0.3, 'signal': 0.0}})
            t += 1
    d = train_next_event(rows)
    assert d['status'] == 'validated'
    exp = export_next_event_weights(d)
    assert exp['kind'] == 'next_event_ovr_v1'


def test_worldcore_anticipation(tmp_path):
    with WorldCore(tmp_path / 'a.db') as w:
        r = w.train_pr_merge_model('valerio', 'ai', pr_samples(), min_train=50, min_holdout=20)
        assert r['status'] == 'trained' and 'export' in r, r
        a = w.train_area_forecast_model('valerio', 'ai', area_samples())
        assert a['status'] == 'trained', a
