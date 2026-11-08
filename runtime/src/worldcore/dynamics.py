"""Portable numeric dynamics learned from observed trajectories, not LLM weights.

Ridge-regression models share action-conditioned laws across *explicitly same-family*
environments. Splits by environment ID before fitting; no fabricated training data.
Refuses deployment unless held-out improvement beats state-persistence baseline.
No automatic execution, causal inference, or universal physics claims.
"""
from __future__ import annotations
import hashlib
import json
import math
import statistics
import uuid
from datetime import datetime,timezone
from .worldmodel import _valid_atom


def _finite(v):return type(v) in (int,float) and math.isfinite(v)


def _numeric_state(state):
    if not isinstance(state,dict) or not state or len(state)>12 or any(not isinstance(k,str) or len(k)>40 or not _finite(v) for k,v in state.items()):
        raise ValueError('dynamics state must contain 1..12 finite numeric fields')
    return {k:float(v) for k,v in state.items()}


def _solve(a,b):
    """Small regularized Gaussian-elimination system, no inference dependencies."""
    n=len(b);a=[list(row)+[b[i]] for i,row in enumerate(a)]
    for i in range(n):
        j=max(range(i,n),key=lambda j:abs(a[j][i]));a[i],a[j]=a[j],a[i]
        if abs(a[i][i])<1e-12:raise ValueError('singular learned model')
        t=a[i][i]
        for k in range(i,n+1):a[i][k]/=t
        for j in range(n):
            if j==i:continue
            c=a[j][i]
            for k in range(i,n+1):a[j][k]-=c*a[i][k]
    return [a[i][-1] for i in range(n)]


def _fit(rows,keys,reg=0.05):
    mean={k:statistics.fmean(r['before'][k] for r in rows) for k in keys}
    std={k:max(1e-6,statistics.pstdev([r['before'][k] for r in rows])) for k in keys}
    features=[[1.0]+[(r['before'][k]-mean[k])/std[k] for k in keys] for r in rows]
    n=len(keys)+1
    gram=[[sum(x[i]*x[j] for x in features)+(reg if i==j else 0) for j in range(n)] for i in range(n)]
    weights={k:_solve(gram,[sum(x[i]*(r['after'][k]-r['before'][k]) for x,r in zip(features,rows)) for i in range(n)]) for k in keys}
    return {'keys':keys,'mean':mean,'std':std,'weights':weights,'train_size':len(rows),
            'train_ranges':{k:[min(r['before'][k] for r in rows),max(r['before'][k] for r in rows)] for k in keys}}


def _predict(model,before):
    keys=model['keys'];v=[1.0]+[(before[k]-model['mean'][k])/model['std'][k] for k in keys]
    return {k:before[k]+sum(w*x for w,x in zip(model['weights'][k],v)) for k in keys}


def _errors(model,rows):
    return [statistics.fmean(abs(_predict(model,r['before'])[k]-r['after'][k]) for k in model['keys']) for r in rows]


def train_family_dynamics(samples,*,min_train=20,min_holdout=8):
    """Train using observation records: environment, action, before, after, source.

    Hold out COMPLETE environments, not shuffled transitions. Deploy only actions
    validated on distinct environments with identical feature schema.
    """
    if not isinstance(samples,list) or len(samples)>120000:raise ValueError('invalid sample list')
    clean=[]
    for r in samples:
        if not isinstance(r,dict) or r.get('source')!='observed':continue
        env=_valid_atom(r.get('environment'), 'environment');action=_valid_atom(r.get('action'),'action')
        # This learner handles numeric states only. Categorical transitions require
        # a separate model, not invented numerical encodings.
        if isinstance(r.get('before'),dict) and isinstance(r.get('after'),dict) and (
            any(type(v) not in (int,float) for v in r['before'].values()) or
            any(type(v) not in (int,float) for v in r['after'].values())):
            continue
        before=_numeric_state(r.get('before'));after=_numeric_state(r.get('after'))
        if before.keys()!=after.keys():continue
        clean.append({'environment':env,'action':action,'before':before,'after':after})
    actions=sorted({r['action'] for r in clean})
    results={}
    for action in actions:
        rows=[r for r in clean if r['action']==action];envs=sorted({r['environment'] for r in rows})
        if len(envs)<3:
            results[action]={'status':'abstain','reason':'need_3_independent_environments'};continue
        # Deterministic group holdout, resistant to input-order leakage.
        held_env=envs[-1];train=[r for r in rows if r['environment']!=held_env];test=[r for r in rows if r['environment']==held_env]
        keys=sorted(train[0]['before']) if train else []
        train=[r for r in train if sorted(r['before'])==keys];test=[r for r in test if sorted(r['before'])==keys]
        if len(train)<min_train or len(test)<min_holdout:
            results[action]={'status':'abstain','reason':'insufficient_disjoint_train_test','train':len(train),'test':len(test)};continue
        model=_fit(train,keys)
        error=_errors(model,test);mae=statistics.fmean(error)
        baseline=statistics.fmean(statistics.fmean(abs(r['before'][k]-r['after'][k]) for k in keys) for r in test)
        improvement=1-mae/max(baseline,1e-12)
        # Unchanged state: a trivial baseline is perfect, do not claim learning.
        accepted=baseline>1e-8 and improvement>=.10
        model.update({'holdout_environment':held_env,'heldout_count':len(test),'heldout_mae':mae,
                      'persistence_mae':baseline,'improvement_vs_persistence':improvement,
                      'holdout_p90_error':sorted(error)[math.ceil(.90*len(error))-1]})
        results[action]={'status':'validated' if accepted else 'rejected_no_baseline_gain','model':model,
                         'note':'Held-out environment differs from training environments; shared dynamics only'}
    return {'actions':results,'count_observed':len(clean),'validation':'group_holdout_by_environment',
            'note':'Not an open-world universal simulator; only numeric dynamics from explicitly similar environments'}


class DynamicsMixin:
    def _init_dynamic_schema(self):
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS calibrated_dynamics(
          owner TEXT NOT NULL,space TEXT NOT NULL,family TEXT NOT NULL,version INTEGER NOT NULL,
          trained_at TEXT NOT NULL,bundle_json TEXT NOT NULL,
          PRIMARY KEY(owner,space,family,version));
        CREATE TABLE IF NOT EXISTS calibrated_forecasts(
          id TEXT PRIMARY KEY,owner TEXT NOT NULL,space TEXT NOT NULL,family TEXT NOT NULL,
          version INTEGER NOT NULL,created_at TEXT NOT NULL,prediction_json TEXT NOT NULL,
          actual_json TEXT,observed_at TEXT,source TEXT,covered INTEGER,mae REAL);
        CREATE INDEX IF NOT EXISTS calibrated_forecast_scope
          ON calibrated_forecasts(owner,space,family,version,observed_at);
        CREATE TABLE IF NOT EXISTS learned_dynamics(
          owner TEXT,space TEXT,family TEXT,version INTEGER,model_json TEXT NOT NULL,
          created_at TEXT NOT NULL,PRIMARY KEY(owner,space,family,version));
        CREATE TABLE IF NOT EXISTS learned_dynamics_pending(
          id TEXT PRIMARY KEY,owner TEXT NOT NULL,space TEXT NOT NULL,family TEXT NOT NULL,
          model_version INTEGER NOT NULL,before_json TEXT NOT NULL,action TEXT NOT NULL,
          predicted_json TEXT NOT NULL,created_at TEXT NOT NULL,status TEXT NOT NULL,
          observed_json TEXT,observed_at TEXT,mae REAL);
        CREATE INDEX IF NOT EXISTS learned_pending_scope ON learned_dynamics_pending(owner,space,family,status);
        CREATE TABLE IF NOT EXISTS learned_dynamics_errors(
          owner TEXT,space TEXT,family TEXT,version INTEGER,prediction_id TEXT NOT NULL,
          mae REAL NOT NULL,observed_at TEXT NOT NULL,PRIMARY KEY(owner,space,family,prediction_id));
        ''')

    def train_shared_dynamics(self,owner,family,samples,*,space='default'):
        owner,space,family=[_valid_atom(x,'identifier') for x in (owner,space,family)]
        result=train_family_dynamics(samples)
        if not any(a['status']=='validated' for a in result['actions'].values()):
            return {'status':'rejected','validation':result}
        stamp=datetime.now(timezone.utc).isoformat()
        with self._transaction():
            row=self.db.execute('SELECT COALESCE(MAX(version),0) v FROM learned_dynamics WHERE owner=? AND space=? AND family=?',(owner,space,family)).fetchone()
            v=row['v']+1
            self.db.execute('INSERT INTO learned_dynamics VALUES (?,?,?,?,?,?)',
                            (owner,space,family,v,json.dumps(result,sort_keys=True,allow_nan=False),stamp))
        return {'status':'trained','version':v,'actions':{k:a['status'] for k,a in result['actions'].items()},
                'validation':result}

    def train_dynamics_from_world_log(self,owner,family,environments,*,space='default'):
        """Fit only from persisted observed transitions selected by host.

        Host MUST authenticate source and environment identity. An asserted
        'observed' label is not an independent sensor attestation.
        """
        from .engine import WorldCoreError
        owner,space,family=[_valid_atom(x,'identifier') for x in (owner,space,family)]
        if not isinstance(environments,list) or not 3<=len(environments)<=50 or len(set(environments))!=len(environments):
            raise WorldCoreError('3..50 distinct environments required for holdout')
        envs=[_valid_atom(x,'environment') for x in environments]
        with self.lock:
            rows=[]
            for env in envs:
                rows.extend(self.db.execute("""SELECT environment,before_state,action,after_state FROM wm_transitions
                    WHERE owner=? AND space=? AND environment=? AND source='observed'
                    ORDER BY sample_id""",(owner,space,env)).fetchall())
        if len(rows)>120000:raise WorldCoreError('too many observations')
        samples=[{'environment':r['environment'],'action':r['action'],'before':json.loads(r['before_state']),
                  'after':json.loads(r['after_state']),'source':'observed'} for r in rows]
        return self.train_shared_dynamics(owner,family,samples,space=space)

    def predict_shared_dynamics(self,owner,family,before,action,*,space='default',max_z=3.5):
        owner,space,family,action=[_valid_atom(x,'identifier') for x in (owner,space,family,action)]
        before=_numeric_state(before)
        with self.lock:
            row=self.db.execute('''SELECT version,model_json FROM learned_dynamics WHERE owner=? AND space=? AND family=? ORDER BY version DESC LIMIT 1''',
                                (owner,space,family)).fetchone()
        if not row:return {'status':'abstain','reason':'no_trained_model'}
        a=json.loads(row['model_json'])['actions'].get(action)
        if not a or a['status']!='validated':return {'status':'abstain','reason':'action_not_validated'}
        model=a['model'];keys=model['keys']
        if sorted(before)!=keys:return {'status':'abstain','reason':'unknown_state_schema'}
        if any(abs((before[k]-model['mean'][k])/model['std'][k])>max_z for k in keys):
            return {'status':'abstain','reason':'out_of_distribution','model_version':row['version']}
        predicted=_predict(model,before)
        return {'status':'predicted','state':predicted,'model_version':row['version'],
                'holdout_mae':model['heldout_mae'],'holdout_p90_error':model['holdout_p90_error'],
                'interval_coverage_not_guaranteed':True,'requires_confirmation':True}

    def submit_learned_prediction(self,owner,family,before,action,*,space='default'):
        """Immutable model-version-pinned prediction prior to observation."""
        from .engine import utcnow
        owner,space,family,action=[_valid_atom(x,'identifier') for x in (owner,space,family,action)]
        result=self.predict_shared_dynamics(owner,family,before,action,space=space)
        if result['status']!='predicted':return result
        pid=str(uuid.uuid4())
        with self._transaction():
            # Atomic compare against the version used by predict_shared_dynamics;
            # caller must retry if a newer model appeared between calls.
            latest=self.db.execute('''SELECT MAX(version) v FROM learned_dynamics
               WHERE owner=? AND space=? AND family=?''',(owner,space,family)).fetchone()['v']
            if latest!=result['model_version']:
                return {'status':'abstain','reason':'model_changed_during_submission'}
            self.db.execute('INSERT INTO learned_dynamics_pending VALUES (?,?,?,?,?,?,?,?,?,?,?, ?,?)',
                (pid,owner,space,family,latest,json.dumps(_numeric_state(before),sort_keys=True),action,
                 json.dumps(result['state'],sort_keys=True),utcnow(),'pending',None,None,None))
        return {'status':'pending','prediction_id':pid,'predicted':result['state'],
                'model_version':result['model_version'],'holdout_mae':result['holdout_mae'],
                'warning':'Prediction must be resolved against externally observed state'}

    def resolve_learned_prediction(self,owner,prediction_id,actual,*,space='default',at=None):
        """Score against real outcome without silently switching model versions.

        Authorization and truth of actual observation are asserted by the host.
        """
        from .engine import WorldCoreError,_when
        owner,space=[_valid_atom(x,'identifier') for x in (owner,space)]
        if not isinstance(prediction_id,str) or len(prediction_id)>64:raise WorldCoreError('invalid prediction id')
        actual=_numeric_state(actual)
        now=_when(at)
        with self._transaction():
            row=self.db.execute('''SELECT * FROM learned_dynamics_pending
                WHERE id=? AND owner=? AND space=?''',(prediction_id,owner,space)).fetchone()
            if row is None:raise WorldCoreError('prediction not found in caller scope')
            raw=json.dumps(actual,sort_keys=True)
            if row['status']=='resolved':
                if row['observed_json']!=raw:raise WorldCoreError('prediction already resolved differently')
                return {'status':'unchanged','mae':row['mae'],'model_version':row['model_version']}
            predicted=json.loads(row['predicted_json'])
            if actual.keys()!=predicted.keys():raise WorldCoreError('actual state has different schema')
            mae=statistics.fmean(abs(predicted[k]-actual[k]) for k in predicted)
            self.db.execute('''UPDATE learned_dynamics_pending SET observed_json=?,observed_at=?,mae=?,status='resolved'
                        WHERE id=?''',(raw,now,mae,prediction_id))
            self.db.execute('''INSERT INTO learned_dynamics_errors VALUES (?,?,?,?,?,?,?)''',
                   (owner,space,row['family'],row['model_version'],prediction_id,mae,now))
            history=self.db.execute('''SELECT mae FROM learned_dynamics_errors WHERE owner=? AND space=?
                AND family=? AND version=? ORDER BY observed_at DESC LIMIT 20''',
                (owner,space,row['family'],row['model_version'])).fetchall()
            trained=self.db.execute('''SELECT model_json FROM learned_dynamics WHERE owner=? AND space=?
                AND family=? AND version=?''',(owner,space,row['family'],row['model_version'])).fetchone()
        a=json.loads(trained['model_json'])['actions'][row['action']]
        threshold=a['model']['holdout_p90_error']
        recent=statistics.fmean(x['mae'] for x in history)
        return {'status':'resolved','prediction_id':prediction_id,'model_version':row['model_version'],
            'mae':mae,'recent_mae':recent,'evaluations':len(history),
            'drift_alarm':len(history)>=10 and recent>max(.001,threshold*2),
            'action_executed_by_worldcore':False,
            'warning':'Ground truth must be validated by authorized host; results are observational'}

    def record_dynamics_error(self,owner,family,prediction_id,predicted,actual,*,space='default',at=None):
        owner,space,family,prediction_id=[_valid_atom(x,'identifier') for x in (owner,space,family,prediction_id)]
        predicted=_numeric_state(predicted);actual=_numeric_state(actual)
        if predicted.keys()!=actual.keys():raise ValueError('prediction schema differs from observed')
        mae=statistics.fmean(abs(predicted[k]-actual[k]) for k in predicted)
        with self._transaction():
            row=self.db.execute('SELECT version,model_json FROM learned_dynamics WHERE owner=? AND space=? AND family=? ORDER BY version DESC LIMIT 1',(owner,space,family)).fetchone()
            if not row:raise ValueError('no learned model')
            when=at or datetime.now(timezone.utc).isoformat()
            self.db.execute('INSERT INTO learned_dynamics_errors VALUES (?,?,?,?,?,?,?)',(owner,space,family,row['version'],prediction_id,mae,when))
            rows=self.db.execute('''SELECT mae FROM learned_dynamics_errors WHERE owner=? AND space=? AND family=? AND version=? ORDER BY observed_at DESC LIMIT 20''',
                                 (owner,space,family,row['version'])).fetchall()
        baseline=max([x['model']['holdout_p90_error'] for x in json.loads(row['model_json'])['actions'].values() if x['status']=='validated'],default=0)
        recent=statistics.fmean(x['mae'] for x in rows)
        return {'status':'tracked','mae':mae,'rolling_mae':recent,'sample_count':len(rows),
                'drift_alarm':len(rows)>=10 and recent>max(.001,baseline*2),
                'note':'Alarm is heuristic; never automatically retrain or take actions'}

    def train_calibrated_dynamics(self, owner, family, samples, *, as_of, space='default', coverage=.8):
        from .calibrated import train_temporal
        from .engine import WorldCoreError, _when, utcnow
        owner,space,family=[_valid_atom(v,'identifier') for v in (owner,space,family)]
        cutoff = _when(as_of)
        now = utcnow()
        if cutoff > now:
            raise WorldCoreError('training cutoff cannot be in the future')
        bundle = train_temporal(samples, as_of=cutoff, coverage=coverage)
        if not any(v['status']=='validated' for v in bundle['actions'].values()):
            return {'status':'rejected', 'validation':bundle}
        with self._transaction():
            version = self.db.execute('SELECT COALESCE(MAX(version),0)+1 FROM calibrated_dynamics WHERE owner=? AND space=? AND family=?',
                                      (owner,space,family)).fetchone()[0]
            self.db.execute('INSERT INTO calibrated_dynamics VALUES (?,?,?,?,?,?)',
                            (owner,space,family,version,now,json.dumps(bundle,sort_keys=True,allow_nan=False)))
        return {'status':'trained','version':version,'validation':bundle}

    def predict_calibrated_world(self, owner, family, before, action, *, space='default', min_confidence=.5, max_width=None, persist=False):
        from .calibrated import predict_temporal, wilson
        from .engine import utcnow, WorldCoreError
        owner,space,family,action=[_valid_atom(v,'identifier') for v in (owner,space,family,action)]
        if type(persist) is not bool:
            raise WorldCoreError('persist must be boolean')
        # Prediction, version selection and ledger insertion share one transaction.
        with self._transaction():
            head=self.db.execute('SELECT version FROM adaptive_heads WHERE owner=? AND space=? AND family=?',
                                 (owner,space,family)).fetchone()
            if head and head['version'] is None:
                return {'status':'abstain','reason':'adaptive_model_suspended'}
            row = self.db.execute('SELECT * FROM calibrated_dynamics WHERE owner=? AND space=? AND family=? '+
                ('AND version=?' if head else 'ORDER BY version DESC LIMIT 1'),
                (owner,space,family,head['version']) if head else (owner,space,family)).fetchone()
            if not row:
                return {'status':'abstain','reason':'no_calibrated_model'}
            bundle=json.loads(row['bundle_json'])
            recent = self.db.execute("SELECT covered FROM calibrated_forecasts WHERE owner=? AND space=? AND family=? AND version=? AND json_extract(prediction_json,'$.action')=? AND covered IS NOT NULL ORDER BY observed_at DESC,id DESC LIMIT 20",
                                     (owner,space,family,row['version'],action)).fetchall()
            target=bundle['actions'].get(action,{}).get('coverage_target',.8)
            if len(recent)>=10 and wilson(sum(r[0] for r in recent),len(recent))[1] < target:
                return {'status':'abstain','reason':'observed_coverage_drift','evaluations':len(recent)}
            result = predict_temporal(bundle,before,action,
                                      min_confidence=min_confidence,max_width=max_width)
            result['model_version']=row['version']
            result['action']=action
            if result['status']=='predicted' and persist:
                identifier=uuid.uuid4().hex
                self.db.execute('INSERT INTO calibrated_forecasts(id,owner,space,family,version,created_at,prediction_json) VALUES (?,?,?,?,?,?,?)',
                                (identifier,owner,space,family,row['version'],utcnow(),json.dumps(result,sort_keys=True,allow_nan=False)))
                result['prediction_id']=identifier
        return result

    def resolve_calibrated_prediction(self, owner, prediction_id, actual, *, space='default', observed_at=None, source='user_reported'):
        from .engine import WorldCoreError, _when, utcnow
        owner,space,prediction_id=[_valid_atom(v,'identifier') for v in (owner,space,prediction_id)]
        if source not in ('user_reported','host_verified'):
            raise WorldCoreError('invalid verification source')
        actual=_numeric_state(actual)
        raw=json.dumps(actual,sort_keys=True,allow_nan=False)
        at=_when(observed_at)
        if at > utcnow():
            raise WorldCoreError('outcome observation cannot be in the future')
        with self._transaction():
            row=self.db.execute('SELECT * FROM calibrated_forecasts WHERE id=? AND owner=? AND space=?',(prediction_id,owner,space)).fetchone()
            if row is None:
                raise WorldCoreError('prediction not found in caller scope')
            if row['actual_json'] is not None:
                if row['actual_json'] != raw or row['source'] != source:
                    raise WorldCoreError('prediction outcome is immutable')
                return {'status':'unchanged','covered':bool(row['covered']),'mae':row['mae']}
            if at < row['created_at']:
                raise WorldCoreError('outcome precedes prediction')
            prediction=json.loads(row['prediction_json'])
            if actual.keys() != prediction['state'].keys():
                raise WorldCoreError('outcome schema differs from prediction')
            covered=all(prediction['intervals'][k][0] <= v <= prediction['intervals'][k][1] for k,v in actual.items())
            mae=statistics.fmean(abs(prediction['state'][k]-v) for k,v in actual.items())
            self.db.execute('UPDATE calibrated_forecasts SET actual_json=?,observed_at=?,source=?,covered=?,mae=? WHERE id=?',
                            (raw,at,source,int(covered),mae,prediction_id))
            if source=='host_verified':
                self._review_adaptive_world_locked(owner,row['family'],space=space)
        return {'status':'resolved','covered':covered,'mae':mae,'model_version':row['version'],'causal_claim':False}

    def calibrated_prediction_metrics(self, owner, family, *, space='default'):
        from .calibrated import wilson
        owner,space,family=[_valid_atom(v,'identifier') for v in (owner,space,family)]
        with self.lock:
            rows=self.db.execute('SELECT covered,mae FROM calibrated_forecasts WHERE owner=? AND space=? AND family=?',
                                 (owner,space,family)).fetchall()
        scored=[r for r in rows if r['covered'] is not None]
        hits=sum(r['covered'] for r in scored)
        return {'submitted':len(rows),'resolved':len(scored),'pending':len(rows)-len(scored),
                'joint_interval_coverage':hits/len(scored) if scored else None,
                'coverage_wilson_95':wilson(hits,len(scored)),
                'mae':statistics.fmean(r['mae'] for r in scored) if scored else None,
                'warning':'Coverage is conditional on submitted and resolved forecasts; inspect abstention separately.'}
