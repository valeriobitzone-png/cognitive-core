"""WorldCore persistence helpers for PR-merge and area-forecast models."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from .worldmodel import _valid_atom
from .pr_outcome import train_pr_merge, export_pr_merge_weights
from .area_forecast import train_area_forecast, export_area_weights


class AnticipationMixin:
    def train_pr_merge_model(self, owner, family, samples, *, space='default',
                             min_train=40, min_holdout=20, min_environments=3, holdout_mode='temporal'):
        owner, space, family = [_valid_atom(x, 'identifier') for x in (owner, space, family)]
        result = train_pr_merge(samples, min_train=min_train, min_holdout=min_holdout,
                                min_environments=min_environments, holdout_mode=holdout_mode)
        if result.get('status') != 'validated':
            return {'status': 'rejected', 'validation': result}
        fam = _valid_atom(f'{family}__prmerge', 'identifier')
        stamp = datetime.now(timezone.utc).isoformat()
        with self._transaction():
            row = self.db.execute(
                'SELECT COALESCE(MAX(version),0) v FROM learned_dynamics WHERE owner=? AND space=? AND family=?',
                (owner, space, fam)).fetchone()
            v = row['v'] + 1
            self.db.execute('INSERT INTO learned_dynamics VALUES (?,?,?,?,?,?)',
                            (owner, space, fam, v, json.dumps(result, sort_keys=True, allow_nan=False), stamp))
        return {'status': 'trained', 'version': v, 'validation': result, 'export': export_pr_merge_weights(result)}

    def train_area_forecast_model(self, owner, family, samples, *, space='default',
                                  min_train=40, min_holdout=20, min_environments=3, holdout_mode='temporal'):
        owner, space, family = [_valid_atom(x, 'identifier') for x in (owner, space, family)]
        result = train_area_forecast(samples, min_train=min_train, min_holdout=min_holdout,
                                     min_environments=min_environments, holdout_mode=holdout_mode)
        if result.get('status') != 'validated':
            return {'status': 'rejected', 'validation': result}
        fam = _valid_atom(f'{family}__area', 'identifier')
        stamp = datetime.now(timezone.utc).isoformat()
        with self._transaction():
            row = self.db.execute(
                'SELECT COALESCE(MAX(version),0) v FROM learned_dynamics WHERE owner=? AND space=? AND family=?',
                (owner, space, fam)).fetchone()
            v = row['v'] + 1
            self.db.execute('INSERT INTO learned_dynamics VALUES (?,?,?,?,?,?)',
                            (owner, space, fam, v, json.dumps(result, sort_keys=True, allow_nan=False), stamp))
        return {'status': 'trained', 'version': v, 'validation': result, 'export': export_area_weights(result)}
