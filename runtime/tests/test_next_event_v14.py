"""Next-event anticipation: temporal holdout, baselines, per-environment."""
from datetime import datetime, timedelta, timezone
from worldcore import WorldCore
from worldcore.next_event import train_next_event, train_next_event_per_environment, predict_next_event


def _iso(i):
    return (datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i)).isoformat()


def sequences_feature_dependent():
    """Next action after 'feat' depends on days_gap — Markov-1 cannot solve this alone.

    days_gap >= 3 → docs; else → test. Other actions cycle mildly.
    """
    rows = []
    t = 0
    for env in ('repo_a', 'repo_b', 'repo_c'):
        for i in range(100):
            gap = float(i % 6)  # 0..5
            action = 'feat' if i % 2 == 0 else ('docs' if gap >= 3 else 'test')
            # When we emit feat, the FOLLOWING event should be docs/test by gap.
            # So store feat with its gap, then the next row is the consequence.
            if i % 2 == 0:
                rows.append({
                    'environment': env, 'action': 'feat', 'source': 'observed',
                    'observed_at': _iso(t),
                    'features': {'days_gap': gap, 'frac_feat': 0.5, 'signal': gap},
                })
            else:
                nxt = 'docs' if gap >= 3 else 'test'
                rows.append({
                    'environment': env, 'action': nxt, 'source': 'observed',
                    'observed_at': _iso(t),
                    'features': {'days_gap': 0.0, 'frac_feat': 0.3, 'signal': 0.0},
                })
            t += 1
    return rows


def test_temporal_next_event_beats_baselines():
    d = train_next_event(sequences_feature_dependent(), min_train=50, min_holdout=20, min_environments=3)
    assert d['status'] == 'validated', (d.get('status'), d.get('model', {}).get('accuracy'),
                                        d.get('model', {}).get('majority_accuracy'),
                                        d.get('model', {}).get('markov_accuracy'),
                                        d.get('model', {}).get('gain_vs_majority'),
                                        d.get('model', {}).get('gain_vs_markov'))
    assert d['model']['gain_vs_majority'] >= 0.02
    assert d['model']['gain_vs_markov'] >= 0.02


def test_environment_holdout_mode_runs():
    d = train_next_event(sequences_feature_dependent(), holdout_mode='environment', min_environments=3)
    assert d['status'] in ('validated', 'rejected_no_baseline_gain', 'abstain')
    if d['status'] != 'abstain':
        assert d['model']['holdout_mode'] == 'environment'


def test_predict_requires_validated():
    d = train_next_event(sequences_feature_dependent())
    assert d['status'] == 'validated'
    out = predict_next_event(d, 'feat', {'days_gap': 5.0, 'frac_feat': 0.5, 'signal': 5.0})
    assert out['status'] == 'predicted'
    assert out['next_action'] in d['actions']


def test_rejected_when_no_signal():
    rows = []
    t = 0
    for env in ('a', 'b', 'c'):
        for i in range(40):
            rows.append({'environment': env, 'action': 'feat' if i % 2 == 0 else 'fix',
                         'source': 'observed', 'observed_at': _iso(t),
                         'features': {'days_gap': 1.0}})
            t += 1
    d = train_next_event(rows, min_train=30, min_holdout=10)
    # alternating feat/fix → markov perfect; model should not claim gain
    assert d['status'] in ('rejected_no_baseline_gain', 'validated', 'abstain')
    if d['status'] == 'validated':
        # if validated, must show real gains
        assert d['model']['gain_vs_markov'] >= 0.02


def test_per_environment_learner():
    d = train_next_event_per_environment(sequences_feature_dependent(), min_train=40, min_holdout=15)
    assert 'repo_a' in d['environments']
    assert d['environments']['repo_a']['status'] in ('validated', 'rejected_no_baseline_gain', 'abstain')


def test_worldcore_persist(tmp_path):
    with WorldCore(tmp_path / 'n.db') as w:
        r = w.train_next_event_model('valerio', 'public_ai', sequences_feature_dependent())
        assert r['status'] == 'trained', r
        p = w.predict_next_event_model('valerio', 'public_ai', 'feat',
                                      {'days_gap': 4.0, 'frac_feat': 0.5, 'signal': 4.0})
        assert p['status'] == 'predicted'
