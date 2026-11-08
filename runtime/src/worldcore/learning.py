"""Bounded, auditable online learning for WorldCore.

Two small models: logistic binary outcomes on normalized numeric observations,
and tabular action->next-state transition models. They are NOT language models,
not evidence of AGI, and do NOT infer causality from observational traces.

No autonomous actions, no network, no hidden training corpus.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any


def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-min(z, 500.0)))
    e = math.exp(max(z, -500.0))
    return e / (1.0 + e)


def _safe_text(x: Any, name: str, max_length: int = 128) -> str:
    from .engine import WorldCoreError
    if not isinstance(x, str) or not 1 <= len(x) <= max_length or not re.fullmatch(r'[A-Za-z0-9_.:@/-]+', x):
        raise WorldCoreError(f'invalid {name}: expected safe identifier')
    return x


def _scope(owner: str, space: str, model_id: str) -> tuple[str, str, str]:
    return (_safe_text(owner, 'owner'), _safe_text(space, 'space'), _safe_text(model_id, 'model id'))


def _feature_names(names: Any) -> list[str]:
    from .engine import WorldCoreError
    if not isinstance(names, list) or not 1 <= len(names) <= 24:
        raise WorldCoreError('feature schema must contain 1..24 names')
    out = [_safe_text(x, 'feature', 64) for x in names]
    if len(set(out)) != len(out):
        raise WorldCoreError('duplicate feature')
    return out


def _vector(features: Any, names: list[str]) -> list[float]:
    from .engine import WorldCoreError
    if not isinstance(features, dict) or set(features) != set(names):
        raise WorldCoreError('features must exactly match the registered schema')
    values = []
    for name in names:
        x = features[name]
        if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or not 0 <= x <= 1:
            raise WorldCoreError(f'{name}: expected finite normalized number in [0,1]')
        values.append(float(x))
    return values


def _digest(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(encoded.encode('utf-8')).hexdigest()


class LearningMixin:
    """Methods mixed into WorldCore, using its scoped, serialized SQLite transactions."""

    def _init_learning_schema(self):
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS learned_models (
          owner TEXT NOT NULL, space TEXT NOT NULL, model_id TEXT NOT NULL,
          names TEXT NOT NULL, weights TEXT NOT NULL, bias REAL NOT NULL,
          samples INTEGER NOT NULL, provenance TEXT NOT NULL, created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL, PRIMARY KEY (owner,space,model_id));
        CREATE TABLE IF NOT EXISTS learned_samples (
          owner TEXT NOT NULL, space TEXT NOT NULL, model_id TEXT NOT NULL,
          sample_id TEXT NOT NULL, digest TEXT NOT NULL,
          PRIMARY KEY (owner,space,model_id,sample_id));
        CREATE TABLE IF NOT EXISTS transition_models (
          owner TEXT NOT NULL, space TEXT NOT NULL, model_id TEXT NOT NULL,
          provenance TEXT NOT NULL, created_at TEXT NOT NULL,
          PRIMARY KEY (owner,space,model_id));
        CREATE TABLE IF NOT EXISTS transition_samples (
          owner TEXT NOT NULL, space TEXT NOT NULL, model_id TEXT NOT NULL,
          sample_id TEXT NOT NULL, digest TEXT NOT NULL,
          PRIMARY KEY (owner,space,model_id,sample_id));
        CREATE TABLE IF NOT EXISTS transition_counts (
          owner TEXT NOT NULL, space TEXT NOT NULL, model_id TEXT NOT NULL,
          current_state TEXT NOT NULL, action TEXT NOT NULL,
          next_state TEXT NOT NULL, count INTEGER NOT NULL,
          PRIMARY KEY (owner,space,model_id,current_state,action,next_state));
        CREATE INDEX IF NOT EXISTS transition_lookup ON transition_counts(owner,space,model_id,current_state,action);
        ''')

    def create_model(self, owner: str, model_id: str, names: list[str], *, space: str = 'default', provenance: str = 'observed') -> dict:
        from .engine import WorldCoreError, utcnow
        owner, space, model_id = _scope(owner, space, model_id)
        names = _feature_names(names)
        if provenance not in ('observed', 'synthetic', 'external'):
            raise WorldCoreError('provenance must be observed, synthetic or external')
        now = utcnow()
        with self._transaction():
            try:
                self.db.execute('''INSERT INTO learned_models VALUES(?,?,?,?,?,?,?,?,?,?)''',
                    (owner, space, model_id, json.dumps(names), json.dumps([0.0]*len(names)), 0.0, 0, provenance, now, now))
            except __import__('sqlite3').IntegrityError as exc:
                raise WorldCoreError('model already exists; do not silently reset training') from exc
        return self.model_stats(owner, model_id, space=space)

    def model_stats(self, owner: str, model_id: str, *, space: str = 'default') -> dict:
        from .engine import WorldCoreError
        params = _scope(owner, space, model_id)
        with self.lock:
            r = self.db.execute('''SELECT names,samples,provenance,created_at,updated_at
              FROM learned_models WHERE owner=? AND space=? AND model_id=?''', params).fetchone()
        if r is None:
            raise WorldCoreError('model not found')
        return {'model_id': model_id, 'features': json.loads(r['names']), 'samples': r['samples'],
                'provenance': r['provenance'], 'created_at': r['created_at'], 'updated_at': r['updated_at'],
                'training': 'online logistic SGD; model weights, not language model',
                'warning': 'predictions not causally identified or independently calibrated'}

    def train_model(self, owner: str, model_id: str, samples: list[dict], *, space: str = 'default') -> dict:
        """Finite, idempotent supervised updates; holdout evaluation must be external.

        IDs make reruns safe. Model data never includes arbitrary source text.
        A reused ID with different content aborts the entire batch.
        """
        from .engine import WorldCoreError, utcnow
        params = _scope(owner, space, model_id)
        if not isinstance(samples, list) or not 1 <= len(samples) <= 20000:
            raise WorldCoreError('train_model accepts 1..20000 samples per batch')
        with self._transaction():
            model = self.db.execute('SELECT * FROM learned_models WHERE owner=? AND space=? AND model_id=?', params).fetchone()
            if model is None:
                raise WorldCoreError('model not found')
            names = json.loads(model['names'])
            weights = json.loads(model['weights'])
            bias = model['bias']
            updates = model['samples']
            # Validate the entire batch and detect intra-batch conflicts before changing the model.
            prepared, seen = [], {}
            for sample in samples:
                if not isinstance(sample, dict) or set(sample) != {'id','features','outcome'}:
                    raise WorldCoreError('each sample requires only id, features, outcome')
                sid = _safe_text(sample['id'], 'sample id')
                xs = _vector(sample['features'], names)
                if not isinstance(sample['outcome'], bool):
                    raise WorldCoreError('outcome must be boolean')
                y = float(sample['outcome'])
                digest = _digest({'features':xs,'outcome':sample['outcome']})
                if sid in seen and seen[sid] != digest:
                    raise WorldCoreError('conflicting duplicate sample id in batch')
                if sid in seen:
                    continue
                seen[sid] = digest
                prepared.append((sid, xs, y, digest))
            added = 0
            for sid, xs, y, digest in prepared:
                old = self.db.execute('''SELECT digest FROM learned_samples WHERE owner=? AND space=? AND model_id=? AND sample_id=?''', (*params, sid)).fetchone()
                if old is not None:
                    if old['digest'] != digest:
                        raise WorldCoreError('conflicting repeated sample id; transaction rolled back')
                    continue
                self.db.execute('INSERT INTO learned_samples VALUES(?,?,?,?,?)', (*params, sid, digest))
                p = _sigmoid(bias + sum(w*x for w,x in zip(weights,xs)))
                err = y - p
                lr = 0.20 / math.sqrt(1.0 + updates / 1600.0)
                # Clip gradient to protect against unusual updates.
                for i,x in enumerate(xs):
                    weights[i] += lr * (err*x - 0.0001*weights[i])
                    weights[i] = min(30.0,max(-30.0,weights[i]))
                bias = min(30.0,max(-30.0,bias + lr*err))
                updates += 1
                added += 1
            self.db.execute('''UPDATE learned_models SET weights=?,bias=?,samples=?,updated_at=?
                WHERE owner=? AND space=? AND model_id=?''',
                (json.dumps(weights),bias,updates,utcnow(),*params))
        return {'model_id':model_id,'new_samples':added,'total_samples':updates,
                'duplicates_skipped':len(prepared)-added, 'executed_actions':0}

    def predict_model(self, owner: str, model_id: str, features: dict, *, space: str = 'default', min_samples: int = 100) -> dict:
        from .engine import WorldCoreError
        params = _scope(owner, space, model_id)
        if type(min_samples) is not int or not 1 <= min_samples <= 100000:
            raise WorldCoreError('invalid min_samples')
        with self.lock:
            r = self.db.execute('SELECT names,weights,bias,samples,provenance FROM learned_models WHERE owner=? AND space=? AND model_id=?',params).fetchone()
        if r is None:
            raise WorldCoreError('model not found')
        names = json.loads(r['names'])
        xs = _vector(features,names)
        p = _sigmoid(r['bias']+sum(w*x for w,x in zip(json.loads(r['weights']),xs)))
        return {'model_id':model_id,'probability':p if r['samples']>=min_samples else None,
                'status':'ready' if r['samples']>=min_samples else 'insufficient_data',
                'samples':r['samples'],'provenance':r['provenance'], 'executed':False,
                'warning':'association/pattern prediction; not a causal world model or calibrated risk assessment'}

    def create_transition_model(self, owner: str, model_id: str, *, space: str = 'default', provenance: str = 'observed') -> dict:
        from .engine import WorldCoreError, utcnow
        params = _scope(owner, space, model_id)
        if provenance not in ('observed','synthetic','external'):
            raise WorldCoreError('invalid provenance')
        with self._transaction():
            try:
                self.db.execute('INSERT INTO transition_models VALUES(?,?,?,?,?)',(*params,provenance,utcnow()))
            except __import__('sqlite3').IntegrityError as exc:
                raise WorldCoreError('transition model already exists') from exc
        return {'model_id':model_id,'provenance':provenance,'created':True}

    def observe_transition(self, owner: str, model_id: str, current_state: str, action: str, next_state: str, *, sample_id: str, space: str = 'default') -> dict:
        from .engine import WorldCoreError
        params = _scope(owner, space, model_id)
        state = _safe_text(current_state,'current state',64)
        act = _safe_text(action,'action',64)
        nxt = _safe_text(next_state,'next state',64)
        sid = _safe_text(sample_id,'sample id')
        digest = _digest({'current_state':state,'action':act,'next_state':nxt})
        with self._transaction():
            exists = self.db.execute('SELECT 1 FROM transition_models WHERE owner=? AND space=? AND model_id=?',params).fetchone()
            if not exists:
                raise WorldCoreError('transition model not found')
            old=self.db.execute('''SELECT digest FROM transition_samples WHERE owner=? AND space=? AND model_id=? AND sample_id=?''', (*params,sid)).fetchone()
            if old:
                if old['digest'] != digest:
                    raise WorldCoreError('conflicting repeated transition id')
                return {'added':False,'duplicate':True}
            self.db.execute('INSERT INTO transition_samples VALUES(?,?,?,?,?)',(*params,sid,digest))
            self.db.execute('''INSERT INTO transition_counts VALUES(?,?,?,?,?,?,1)
              ON CONFLICT(owner,space,model_id,current_state,action,next_state)
              DO UPDATE SET count=count+1''',(*params,state,act,nxt))
        return {'added':True,'executed':False}

    def predict_transition(self, owner: str, model_id: str, current_state: str, action: str, *, space: str = 'default', min_samples: int = 15) -> dict:
        from .engine import WorldCoreError
        params = _scope(owner,space,model_id)
        state=_safe_text(current_state,'current state',64)
        act=_safe_text(action,'action',64)
        if type(min_samples) is not int or not 1 <= min_samples <= 100000:
            raise WorldCoreError('invalid min_samples')
        with self.lock:
            model=self.db.execute('SELECT provenance FROM transition_models WHERE owner=? AND space=? AND model_id=?',params).fetchone()
            if model is None:
                raise WorldCoreError('transition model not found')
            rows=self.db.execute('''SELECT next_state,count FROM transition_counts WHERE owner=? AND space=? AND model_id=?
              AND current_state=? AND action=? ORDER BY count DESC, next_state''', (*params,state,act)).fetchall()
        n=sum(r['count'] for r in rows)
        if n<min_samples:
            return {'status':'insufficient_data','observations':n,'transitions':[], 'unknown_mass':1.0,
                    'provenance':model['provenance'],'executed':False}
        denom=n+0.5*len(rows)+1.0
        return {'status':'ready','observations':n,'transitions':[
            {'next_state':r['next_state'],'count':r['count'],'probability':(r['count']+0.5)/denom} for r in rows],
            'unknown_mass':1.0/denom,'provenance':model['provenance'],'executed':False,
            'warning':'observed conditional transitions, causal only if data come from controlled interventions'}

    def rollout_transitions(self, owner: str, model_id: str, initial_state: str, actions: list[str], *, space: str = 'default', beam_width: int = 8, min_samples: int = 15) -> dict:
        from .engine import WorldCoreError
        state=_safe_text(initial_state,'initial state',64)
        if not isinstance(actions,list) or not 1 <= len(actions) <= 8:
            raise WorldCoreError('rollout expects 1..8 actions')
        actions=[_safe_text(a,'action',64) for a in actions]
        if type(beam_width) is not int or not 1 <= beam_width <= 16:
            raise WorldCoreError('beam_width must be 1..16')
        beams=[{'states':[state],'probability':1.0,'unknown':False}]
        for action in actions:
            candidates=[]
            for path in beams:
                if path['unknown']:
                    candidates.append(path)
                    continue
                pred=self.predict_transition(owner,model_id,path['states'][-1],action,space=space,min_samples=min_samples)
                if pred['status']!='ready':
                    candidates.append({'states':path['states']+['<unknown>'],'probability':path['probability'],'unknown':True})
                    continue
                for tr in pred['transitions']:
                    candidates.append({'states':path['states']+[tr['next_state']],
                                       'probability':path['probability']*tr['probability'],'unknown':False})
                candidates.append({'states':path['states']+['<unknown>'],
                                  'probability':path['probability']*pred['unknown_mass'],'unknown':True})
            candidates.sort(key=lambda p:p['probability'],reverse=True)
            beams=candidates[:beam_width]
        return {'paths':beams,'actions':actions,'executed':False,
                'warning':'beam search truncates probability mass; states do not imply guarantees'}


    def evaluate_model(self, owner: str, model_id: str, holdout: list[dict], *, space: str = 'default', min_samples: int = 100) -> dict:
        """Read-only out-of-sample binary evaluation. Reject any training-ID overlap.

        Baseline is the best constant rate in the holdout set (oracle / optimistic
        reference); beating it demonstrates value over a constant, NOT AGI.
        """
        from .engine import WorldCoreError
        params = _scope(owner, space, model_id)
        if type(min_samples) is not int or not 1 <= min_samples <= 100000:
            raise WorldCoreError('invalid min_samples')
        if not isinstance(holdout, list) or not 20 <= len(holdout) <= 20000:
            raise WorldCoreError('holdout must have 20..20000 rows')
        with self._snapshot():
            model = self.db.execute('SELECT * FROM learned_models WHERE owner=? AND space=? AND model_id=?', params).fetchone()
            if model is None:
                raise WorldCoreError('model not found')
            if model['samples'] < min_samples:
                raise WorldCoreError('insufficient training samples to evaluate')
            names = json.loads(model['names'])
            weights = json.loads(model['weights'])
            bias = model['bias']
            prepared, ids = [], set()
            for row in holdout:
                if not isinstance(row, dict) or set(row) != {'id', 'features', 'outcome'} or not isinstance(row['outcome'], bool):
                    raise WorldCoreError('holdout row must contain id, features, boolean outcome')
                sid = _safe_text(row['id'], 'holdout id')
                if sid in ids:
                    raise WorldCoreError('duplicate holdout sample id')
                ids.add(sid)
                prepared.append((sid, _vector(row['features'], names), int(row['outcome'])))
            # Chunked queries work with SQLite's maximum parameter count.
            for offset in range(0, len(prepared), 300):
                batch = [r[0] for r in prepared[offset:offset+300]]
                marks = ','.join('?' for _ in batch)
                overlap = self.db.execute(
                    f'SELECT 1 FROM learned_samples WHERE owner=? AND space=? AND model_id=? AND sample_id IN ({marks}) LIMIT 1',
                    (*params, *batch)).fetchone()
                if overlap:
                    raise WorldCoreError('training/holdout ID overlap: evaluation refused')
        values = [(float(_sigmoid(bias + sum(w*x for w, x in zip(weights, xs)))), y) for _, xs, y in prepared]
        n = len(values)
        base_rate = sum(y for _, y in values)/n
        brier = sum((p-y)**2 for p,y in values)/n
        baseline = base_rate*(1-base_rate)
        eps = 1e-12
        log_loss = -sum(y*math.log(max(p,eps)) + (1-y)*math.log(max(1-p,eps)) for p,y in values)/n
        correct = sum((p >= .5) == bool(y) for p,y in values)
        bins = [[] for _ in range(10)]
        for p,y in values:
            bins[min(9,int(p*10))].append((p,y))
        ece = sum(len(b)/n*abs(sum(p for p,_ in b)/len(b)-sum(y for _,y in b)/len(b)) for b in bins if b)
        return {'model_id':model_id,'model_fingerprint':_digest({'names':names,'weights':weights,'bias':bias,'samples':model['samples']}),
                'holdout_count':n,'training_count':model['samples'],
                'brier':round(brier,6),'constant_oracle_brier':round(baseline,6),
                'brier_skill_vs_constant':round((1-brier/baseline),6) if baseline>0 else None,
                'log_loss':round(log_loss,6),'accuracy_at_0_5':round(correct/n,6),
                'expected_calibration_error_10bin':round(ece,6),
                'holdout_prevalence':round(base_rate,6),'provenance':model['provenance'],
                'training_overlap_checked':True,'mutated':False,
                'warning':'holdout is caller-supplied, cannot verify chronological independence or original data provenance; ECE is descriptive, not a calibration guarantee'}

    def evaluate_transitions(self, owner: str, model_id: str, holdout: list[dict], *, space: str = 'default', min_samples: int = 15) -> dict:
        """Evaluate categorical next-state predictions on separate sampled transitions."""
        from .engine import WorldCoreError
        params = _scope(owner,space,model_id)
        if type(min_samples) is not int or not 1 <= min_samples <= 100000:
            raise WorldCoreError('invalid min_samples')
        if not isinstance(holdout,list) or not 20 <= len(holdout) <= 20000:
            raise WorldCoreError('holdout must have 20..20000 rows')
        prepared, seen = [], set()
        for row in holdout:
            if not isinstance(row,dict) or set(row) != {'id','current_state','action','next_state'}:
                raise WorldCoreError('transition holdout requires id,current_state,action,next_state')
            sid = _safe_text(row['id'],'sample id')
            if sid in seen:
                raise WorldCoreError('duplicate holdout sample id')
            seen.add(sid)
            prepared.append((sid, _safe_text(row['current_state'],'state',64), _safe_text(row['action'],'action',64), _safe_text(row['next_state'],'next state',64)))
        with self._snapshot():
            model = self.db.execute('SELECT provenance FROM transition_models WHERE owner=? AND space=? AND model_id=?', params).fetchone()
            if model is None:
                raise WorldCoreError('transition model not found')
            for offset in range(0, len(prepared), 300):
                batch = [r[0] for r in prepared[offset:offset+300]]
                marks = ','.join('?' for _ in batch)
                overlap = self.db.execute(
                    f'SELECT 1 FROM transition_samples WHERE owner=? AND space=? AND model_id=? AND sample_id IN ({marks}) LIMIT 1',
                    (*params,*batch)).fetchone()
                if overlap:
                    raise WorldCoreError('training/holdout ID overlap: evaluation refused')
            # One consistent DB snapshot for predictions and evaluation.
            cache = {}
            for _,state,action,_ in prepared:
                key = (state,action)
                if key in cache:
                    continue
                rows = self.db.execute('SELECT next_state,count FROM transition_counts WHERE owner=? AND space=? AND model_id=? AND current_state=? AND action=?',
                    (*params,state,action)).fetchall()
                n = sum(r['count'] for r in rows)
                if n < min_samples:
                    cache[key] = None
                else:
                    denom = n + .5*len(rows) + 1.
                    cache[key] = ({r['next_state']:(r['count']+.5)/denom for r in rows},1./denom)
        scored=0;hits=0;total_loss=0.;unseen=0
        for _,state,action,target in prepared:
            pred = cache[(state,action)]
            if pred is None:
                continue
            probs,unknown=pred
            scored+=1
            if target not in probs:
                unseen+=1
            p=probs.get(target,unknown)
            total_loss-=math.log(max(p,1e-12))
            hits += int(target == max(probs,key=probs.get))
        return {'model_id':model_id,'holdout_count':len(prepared),'scored':scored,
                'coverage':round(scored/len(prepared),6),
                'top1_accuracy':round(hits/scored,6) if scored else None,
                'mean_log_loss':round(total_loss/scored,6) if scored else None,
                'unseen_next_states':unseen,'training_overlap_checked':True,'mutated':False,
                'provenance':model['provenance'],
                'warning':'categorical conditional frequencies; unknown_mass is aggregate and unseen-state log loss is approximate, not a causal guarantee'}

    @staticmethod
    def detect_drift(reference: dict, recent: dict, *, alpha: float = 0.01) -> dict:
        """Read-only conservative two-sample alarm for an increase in Brier loss.

        Hoeffding concentration assumes independent examples; the returned flag
        is NOT proof of concept drift or a safe autonomous-decision authorization.
        """
        from .engine import WorldCoreError
        if not isinstance(reference,dict) or not isinstance(recent,dict):
            raise WorldCoreError('expected two evaluation reports')
        for report in (reference,recent):
            if not report.get('model_id') or not report.get('model_fingerprint') or report.get('training_overlap_checked') is not True:
                raise WorldCoreError('invalid or unchecked evaluation report')
            n=report.get('holdout_count')
            if type(n) is not int or n < 100 or n > 1000000:
                raise WorldCoreError('drift detection requires at least 100 independent examples per report')
            score=report.get('brier')
            if isinstance(score,bool) or not isinstance(score,(int,float)) or not math.isfinite(score) or not 0<=score<=1:
                raise WorldCoreError('invalid bounded Brier loss')
        if reference['model_id']!=recent['model_id'] or reference['model_fingerprint'] != recent['model_fingerprint']:
            raise WorldCoreError('cannot compare different models or changed training snapshots')
        if isinstance(alpha,bool) or not isinstance(alpha,(float,int)) or not math.isfinite(alpha) or not 0<alpha<=0.05:
            raise WorldCoreError('alpha must be in (0, 0.05]')
        n0=reference['holdout_count'];n1=recent['holdout_count']
        threshold=(math.sqrt(math.log(4/alpha)/(2*n0))+
                   math.sqrt(math.log(4/alpha)/(2*n1)))
        increase=float(recent['brier'])-float(reference['brier'])
        return {'model_id':reference['model_id'],'status':'alarm' if increase>threshold else 'no_alarm',
                'loss_increase':round(increase,6),'conservative_threshold':round(threshold,6),
                'alpha_nominal':float(alpha),'executed':False,'mutated':False,
                'warning':'Hoeffding bound assumes independent samples and a fixed model. Alarms flag degradation, not the cause; no alarm does not mean safe.'}
