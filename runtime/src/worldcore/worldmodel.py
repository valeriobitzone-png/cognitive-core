"""Portable discrete environment dynamics with explicit ignorance and scored predictions.

This is NOT a general pretrained vision/language/physical world model. It is an
online empirical model for any environment whose observations can be encoded as
bounded JSON states and actions. Different environments keep separate dynamics.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
import hashlib
import json
import math
import re


def _valid_atom(v, label):
    from .engine import WorldCoreError
    if not isinstance(v, str) or not re.fullmatch(r'[A-Za-z0-9_.:@/\-]{1,128}', v):
        raise WorldCoreError('invalid ' + label)
    return v


def _state(value):
    from .engine import WorldCoreError, _json
    if not isinstance(value, (dict, list, str, int, float, bool)) or isinstance(value, float) and not math.isfinite(value):
        raise WorldCoreError('state must be JSON-compatible primitive, dictionary or list')
    raw = _json(value)
    if len(raw) > 3000:
        raise WorldCoreError('world state exceeds bounded representation')
    return raw


class WorldModelMixin:
    def _init_world_model_schema(self):
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS wm_transitions(
         owner TEXT NOT NULL,space TEXT NOT NULL, environment TEXT NOT NULL,
         sample_id TEXT NOT NULL, before_state TEXT NOT NULL, action TEXT NOT NULL,
         after_state TEXT NOT NULL, observed_at TEXT NOT NULL,source TEXT NOT NULL,
         PRIMARY KEY(owner,space,environment,sample_id));
        CREATE INDEX IF NOT EXISTS wm_lookup ON wm_transitions(owner,space,environment,before_state,action);
        CREATE TABLE IF NOT EXISTS wm_predicted(
         id TEXT PRIMARY KEY,owner TEXT NOT NULL,space TEXT NOT NULL,environment TEXT NOT NULL,
         before_state TEXT NOT NULL,action TEXT NOT NULL,predicted_state TEXT NOT NULL,
         probability REAL NOT NULL,created_at TEXT NOT NULL,status TEXT NOT NULL,
         actual_state TEXT,correct INTEGER);
        CREATE INDEX IF NOT EXISTS wm_prediction_scope ON wm_predicted(owner,space,environment,status);
        ''')

    def observe_world_transition(self, owner, environment, sample_id, before, action, after, *, space='default', source='observed', observed_at=None):
        from .engine import WorldCoreError, _when
        owner, environment, sample_id, space, action = [_valid_atom(v,n) for v,n in zip(
            (owner, environment, sample_id, space, action), ('owner','environment','sample_id','space','action'))]
        if source not in ('observed','simulated','user_asserted','external'):
            raise WorldCoreError('invalid observation source')
        before_raw, after_raw = _state(before), _state(after)
        at = _when(observed_at)
        with self._transaction():
            old = self.db.execute('''SELECT before_state,action,after_state,source FROM wm_transitions
                  WHERE owner=? AND space=? AND environment=? AND sample_id=?''',(owner,space,environment,sample_id)).fetchone()
            if old:
                if tuple(old) != (before_raw,action,after_raw,source):
                    raise WorldCoreError('conflicting transition sample: immutable log')
                return {'status':'unchanged'}
            self.db.execute('''INSERT INTO wm_transitions VALUES (?,?,?,?,?,?,?,?,?)''',
                            (owner,space,environment,sample_id,before_raw,action,after_raw,at,source))
        return {'status':'observed','source':source}

    def imagine_world(self, owner, environment, before, actions, *, space='default', min_support=3,
                      max_branches=3):
        """Counterfactual rollout: no real actions. Abstain on unknown transitions.

        `observed` transitions only: never treat synthetic experience as ground truth.
        Pruning is beam-like; probabilities are conditional empirical frequencies.
        """
        from .engine import WorldCoreError
        owner,environment,space = [_valid_atom(v,n) for v,n in ((owner,'owner'),(environment,'environment'),(space,'space'))]
        if not isinstance(actions,list) or not 1<=len(actions)<=8 or any(not isinstance(a,str) for a in actions):
            raise WorldCoreError('expected 1..8 actions')
        actions=[_valid_atom(a,'action') for a in actions]
        if not isinstance(min_support,int) or not 1<=min_support<=1000 or not isinstance(max_branches,int) or not 1<=max_branches<=8:
            raise WorldCoreError('invalid support or branches')
        beam=[(_state(before),1.0)]; steps=[]
        with self.lock:
            for action in actions:
                new=[]; unknown=0
                for raw_state,prefix_p in beam:
                    rows=self.db.execute('''SELECT after_state,COUNT(*) n FROM wm_transitions
                          WHERE owner=? AND space=? AND environment=? AND before_state=? AND action=? AND source='observed'
                          GROUP BY after_state ORDER BY n DESC,after_state ASC''',
                         (owner,space,environment,raw_state,action)).fetchall()
                    total=sum(r['n'] for r in rows)
                    if total<min_support:
                        unknown+=1
                        continue
                    for r in rows[:max_branches]:
                        new.append((r['after_state'],prefix_p*r['n']/total))
                if not new:
                    return {'status':'abstain','reason':'insufficient_observed_transitions','at_step':len(steps),
                            'action':action,'environment':environment,'trajectory':steps,
                            'warning':'no evidence of generalization outside observed states'}
                new.sort(key=lambda x:(-x[1],x[0])); beam=new[:max_branches]
                steps.append({'action':action,'states':[{'state':json.loads(s),'likelihood':round(p,6)} for s,p in beam],
                              'pruned_unknown_branches':unknown})
        return {'status':'simulated','environment':environment,'steps':steps,
                'warning':'conditional frequencies are not causal probabilities, and branch pruning loses probability mass'}

    def submit_world_prediction(self, owner, environment, before, action, *, space='default', min_support=3):
        from .engine import WorldCoreError, utcnow
        import uuid
        result=self.imagine_world(owner,environment,before,[action],space=space,min_support=min_support,max_branches=1)
        if result['status']!='simulated':return result
        selected=result['steps'][0]['states'][0]
        pid=str(uuid.uuid4());raw_before=_state(before)
        with self._transaction():
            self.db.execute('''INSERT INTO wm_predicted VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                (pid,owner,space,environment,raw_before,action,_state(selected['state']),
                 selected['likelihood'],utcnow(),'pending',None,None))
        return {'status':'pending','prediction_id':pid,'predicted':selected['state'],
                'probability':selected['likelihood']}

    def resolve_world_prediction(self, owner, prediction_id, actual, *, space='default'):
        from .engine import WorldCoreError
        owner,space=_valid_atom(owner,'owner'),_valid_atom(space,'space')
        raw=_state(actual)
        with self._transaction():
            r=self.db.execute('''SELECT * FROM wm_predicted WHERE owner=? AND space=? AND id=?''',
                    (owner,space,prediction_id)).fetchone()
            if r is None:raise WorldCoreError('world prediction not found')
            if r['status']!='pending':
                if r['actual_state']==raw:return {'status':'unchanged','correct':bool(r['correct'])}
                raise WorldCoreError('prediction already resolved with a different state')
            correct=int(raw==r['predicted_state'])
            self.db.execute('''UPDATE wm_predicted SET status='resolved',actual_state=?,correct=?
                 WHERE id=?''',(raw,correct,prediction_id))
        return {'status':'resolved','correct':bool(correct),'probability_of_predicted_state':r['probability'],
                'notice':'a resolved prediction is evidence, not automatic retraining; record observed transition separately'}

    def world_model_metrics(self, owner, environment, *, space='default'):
        owner,environment,space=map(lambda v:_valid_atom(v,'identifier'),(owner,environment,space))
        with self.lock:
            count=self.db.execute('''SELECT COUNT(*) n FROM wm_transitions WHERE owner=? AND space=? AND environment=? AND source='observed' ''',(owner,space,environment)).fetchone()['n']
            row=self.db.execute('''SELECT COUNT(*) n,AVG(correct) a FROM wm_predicted WHERE owner=? AND space=? AND environment=? AND status='resolved' ''',(owner,space,environment)).fetchone()
        return {'environment':environment,'observed_transitions':count,'evaluated_predictions':row['n'],
                'top_state_accuracy':row['a'] if row['n'] else None,
                'warning':'accuracy on evaluated predictions only; unknown environments trigger abstention'}
