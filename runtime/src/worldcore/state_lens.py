"""Versioned, attributable personal-agent state and bounded anticipations.

Predictions are advice with uncertainty. Never infer protected/sensitive traits,
create a diagnosis, or execute an action. Evidence must come from an authorized host.
"""
from __future__ import annotations
from datetime import datetime,timezone,timedelta
import json,math,uuid
from .worldmodel import _valid_atom

SENSITIVE={'health','diagnos','medicat','religion','politic','sexual','biometric','criminal','mental','depress','anxiet','therapy','blood','heart_rate','race','ethnic'}

class StateLensMixin:
    def _init_state_lens_schema(self):
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS context_observations(
         owner TEXT,space TEXT,context_id TEXT,revision INTEGER,at TEXT,source TEXT,
         verified INTEGER NOT NULL,signal_json TEXT NOT NULL,
         PRIMARY KEY(owner,space,context_id,revision));
        CREATE TABLE IF NOT EXISTS task_expectations(
         owner TEXT,space TEXT,task_id TEXT,revision INTEGER,due_at TEXT,priority INTEGER,
         completed INTEGER,description TEXT,source TEXT,created_at TEXT,
         PRIMARY KEY(owner,space,task_id,revision));
        CREATE TABLE IF NOT EXISTS recommendation_feedback(
         owner TEXT,space TEXT,recommendation_id TEXT,at TEXT,helpful INTEGER,reason TEXT,
         PRIMARY KEY(owner,space,recommendation_id));
        ''')

    def observe_context_state(self,owner,context_id,signals,*,space='default',source='host',verified=False,allow_sensitive=False,at=None):
        from .engine import WorldCoreError, _when, _json
        owner,space,context_id,source=[_valid_atom(x,'identifier') for x in (owner,space,context_id,source)]
        if not isinstance(signals,dict) or not 1<=len(signals)<=32 or any(not isinstance(k,str) or not k.isidentifier() for k in signals):
            raise WorldCoreError('bounded named signal dictionary required')
        if any(any(part in k.lower() for part in SENSITIVE) for k in signals) and not allow_sensitive:
            raise WorldCoreError('explicit consent required for sensitive signals')
        if type(verified) is not bool:raise WorldCoreError('verification flag must be boolean')
        raw=_json(signals)
        if len(raw)>5000:raise WorldCoreError('signals too large')
        at=_when(at)
        with self._transaction():
            r=self.db.execute('SELECT COALESCE(MAX(revision),0) v FROM context_observations WHERE owner=? AND space=? AND context_id=?',
                              (owner,space,context_id)).fetchone()
            v=r['v']+1
            self.db.execute('INSERT INTO context_observations VALUES (?,?,?,?,?,?,?,?)',(owner,space,context_id,v,at,source,int(verified),raw))
        return {'status':'versioned','revision':v,'verified':verified}

    def latest_context_state(self,owner,context_id,*,space='default'):
        owner,space,context_id=[_valid_atom(x,'identifier') for x in (owner,space,context_id)]
        with self.lock:
            row=self.db.execute('''SELECT revision,at,source,verified,signal_json FROM context_observations
                WHERE owner=? AND space=? AND context_id=? ORDER BY revision DESC LIMIT 1''',
                (owner,space,context_id)).fetchone()
        if row is None:return None
        result=dict(row);result['signals']=json.loads(result.pop('signal_json'));return result

    def record_task_expectation(self,owner,task_id,description,due_at,*,space='default',priority=2,completed=False,source='user',at=None):
        from .engine import WorldCoreError,_when
        owner,space,task_id,source=[_valid_atom(x,'identifier') for x in (owner,space,task_id,source)]
        if not isinstance(description,str) or not 1<=len(description)<=400:raise WorldCoreError('invalid task')
        if not isinstance(priority,int) or priority not in range(1,6) or type(completed) is not bool:raise WorldCoreError('invalid task flags')
        due_at=_when(due_at);at=_when(at)
        with self._transaction():
            r=self.db.execute('SELECT COALESCE(MAX(revision),0) v FROM task_expectations WHERE owner=? AND space=? AND task_id=?',(owner,space,task_id)).fetchone()
            v=r['v']+1
            self.db.execute('INSERT INTO task_expectations VALUES (?,?,?,?,?,?,?,?,?,?)',
                            (owner,space,task_id,v,due_at,priority,int(completed),description,source,at))
        return {'status':'versioned','revision':v}

    def anticipate_needs(self,owner,*,space='default',now=None,horizon_hours=72,limit=20):
        """Only anticipates explicitly recorded tasks (not guessed psychological needs)."""
        from .engine import WorldCoreError,_when
        owner,space=[_valid_atom(x,'identifier') for x in (owner,space)]
        if not 1<=horizon_hours<=720 or not 1<=limit<=100:raise WorldCoreError('invalid horizon')
        now=datetime.fromisoformat(_when(now).replace('Z','+00:00'))
        with self.lock:
            rows=self.db.execute('''SELECT t.* FROM task_expectations t JOIN
              (SELECT task_id,MAX(revision) rev FROM task_expectations WHERE owner=? AND space=? GROUP BY task_id) x
              ON t.task_id=x.task_id AND t.revision=x.rev
              WHERE t.owner=? AND t.space=? AND t.completed=0''',(owner,space,owner,space)).fetchall()
        out=[]
        for r in rows:
            due=datetime.fromisoformat(r['due_at'].replace('Z','+00:00'))
            h=(due-now).total_seconds()/3600
            if h>horizon_hours:continue
            out.append({'task_id':r['task_id'],'description':r['description'],'source':r['source'],
                        'due_at':r['due_at'],'hours_remaining':round(h,2),'overdue':h<0,
                        'priority':r['priority'],'kind':'deadline_attention',
                        'prediction_type':'deterministic_deadline_from_user_state',
                        'estimated_probability':None,'suggestion':'Review or reschedule the task if needed',
                        'executes_action':False})
        return {'status':'suggestions','items':sorted(out,key=lambda x:(not x['overdue'],x['hours_remaining'], -x['priority']))[:limit],
                'limitations':'No hidden inference about the user; task suggestions not probabilistic future events'}

    def record_recommendation_feedback(self,owner,recommendation_id,helpful,reason,*,space='default',at=None):
        from .engine import WorldCoreError,_when
        owner,space,recommendation_id=[_valid_atom(x,'identifier') for x in (owner,space,recommendation_id)]
        if type(helpful) is not bool or not isinstance(reason,str) or len(reason)>400:
            raise WorldCoreError('invalid feedback')
        with self._transaction():
            self.db.execute('INSERT INTO recommendation_feedback VALUES (?,?,?,?,?,?)',
                            (owner,space,recommendation_id,_when(at),int(helpful),reason))
        return {'status':'recorded'}

    def forecast_verified_state(self,owner,context_id,signal,*,space='default',horizon_hours=1,min_points=12):
        """Chronological holdout trend forecasting for an observed numeric signal.

        Return abstention if the trend does not beat last-value persistence.
        Not medical, market, or behavioral causal inference. No automatic actions.
        """
        from .engine import WorldCoreError
        import statistics, math
        owner,context_id,space=[_valid_atom(x,'identifier') for x in (owner,context_id,space)]
        if not isinstance(signal,str) or not signal.isidentifier():raise WorldCoreError('invalid signal')
        if not 0<horizon_hours<=72 or not 8<=min_points<=200:raise WorldCoreError('invalid forecast configuration')
        with self.lock:
            rows=self.db.execute('''SELECT at,signal_json FROM context_observations
                  WHERE owner=? AND space=? AND context_id=? AND verified=1
                  ORDER BY at ASC,revision ASC LIMIT 10000''',(owner,space,context_id)).fetchall()
        data=[]
        for r in rows:
            signals=json.loads(r['signal_json']);v=signals.get(signal)
            if type(v) in (int,float) and math.isfinite(v):
                dt=datetime.fromisoformat(r['at'].replace('Z','+00:00'))
                data.append((dt.timestamp(),float(v)))
        data=sorted(set(data))
        if len(data)<min_points:return {'status':'abstain','reason':'not_enough_verified_signal_history','count':len(data)}
        dt=[data[i+1][0]-data[i][0] for i in range(len(data)-1)]
        if not dt or min(dt)<=0:return {'status':'abstain','reason':'duplicate_or_invalid_times'}
        # Hold out the most recent observations; no information leakage.
        tsize=max(4,len(data)//5);train,test=data[:-tsize],data[-tsize:]
        def fit(seq):
            x0=seq[0][0];xs=[(x-x0)/3600 for x,_ in seq];ys=[y for _,y in seq]
            mx=statistics.fmean(xs);my=statistics.fmean(ys)
            var=sum((x-mx)**2 for x in xs)
            if var<1e-8:return None
            slope=sum((x-mx)*(y-my) for x,y in zip(xs,ys))/var
            return x0,slope,my-slope*mx
        fit_model=fit(train)
        if fit_model is None:return {'status':'abstain','reason':'insufficient_time_variation'}
        x0,slope,intercept=fit_model
        errs=[abs(intercept+slope*((t-x0)/3600)-y) for t,y in test]
        baseline=[abs(train[-1][1]-test[0][1])]+[abs(test[i-1][1]-test[i][1]) for i in range(1,len(test))]
        mae=statistics.fmean(errs);base=statistics.fmean(baseline)
        if base<1e-9 or mae>=base*.9:
            return {'status':'abstain','reason':'trend_does_not_beat_persistence','holdout_mae':mae,'baseline_mae':base}
        latest=data[-1]
        # Refit on all available observations after successful disjoint validation.
        new=fit(data)
        final=new[2]+new[1]*((latest[0]+3600*horizon_hours-new[0])/3600)
        return {'status':'predicted','context_id':context_id,'signal':signal,
                'predicted_value':final,'target_at':datetime.fromtimestamp(latest[0]+3600*horizon_hours,timezone.utc).isoformat(),
                'holdout_mae':mae,'baseline_mae':base,'p90_abs_error':sorted(errs)[math.ceil(.9*len(errs))-1],
                'count':len(data),'authorized_action':False,'confidence_calibrated':False,
                'warning':'Linear trend only; uncertainty may increase beyond observed time span'}

    def flag_state_anomaly(self,owner,context_id,signal,*,space='default',min_points=12,threshold=4.0):
        """Robust anomaly on latest verified numeric sample, never inferred diagnosis."""
        from .engine import WorldCoreError
        import statistics,math
        owner,context_id,space=[_valid_atom(x,'identifier') for x in (owner,context_id,space)]
        if not isinstance(signal,str) or not signal.isidentifier():raise WorldCoreError('invalid signal')
        if not 8<=min_points<=200 or not 2<=threshold<=12:raise WorldCoreError('invalid threshold')
        with self.lock:
            rows=self.db.execute('''SELECT at,signal_json FROM context_observations
                WHERE owner=? AND space=? AND context_id=? AND verified=1 ORDER BY at DESC,revision DESC LIMIT 1000''',
                (owner,space,context_id)).fetchall()
        nums=[]
        for r in rows:
            v=json.loads(r['signal_json']).get(signal)
            if type(v) in (int,float) and math.isfinite(v):nums.append(float(v))
        if len(nums)<min_points+1:return {'status':'abstain','reason':'insufficient_verified_history'}
        prior=nums[1:];median=statistics.median(prior)
        mad=statistics.median([abs(x-median) for x in prior])
        spread=1.4826*mad if mad>=1e-12 else statistics.pstdev(prior)
        if spread<1e-12:return {'status':'abstain','reason':'zero_reference_dispersion'}
        z=abs(nums[0]-median)/spread
        return {'status':'evaluated','anomaly':z>=threshold,'robust_z':round(z,4),
                'count':len(nums),'cause_inferred':False,'action_taken':False,
                'warning':'Statistical outlier, not a diagnosis, threat, or confirmed causal event'}
