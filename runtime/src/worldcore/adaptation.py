"""Host-driven adaptation of data, never executable code or permissions.

The host authenticates observations. These write APIs are intentionally absent
from model-facing transports. Models and outcome receipts remain immutable.
"""
from __future__ import annotations
import json
import statistics
import uuid
from .worldmodel import _valid_atom


class AdaptationMixin:
    def _init_adaptation_schema(self):
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS adaptive_heads(
          owner TEXT,space TEXT,family TEXT,version INTEGER,previous INTEGER,
          cutoff TEXT NOT NULL,PRIMARY KEY(owner,space,family));
        CREATE TABLE IF NOT EXISTS adaptive_evaluations(
          owner TEXT,space TEXT,family TEXT,sample_id TEXT,PRIMARY KEY(owner,space,family,sample_id));
        CREATE TABLE IF NOT EXISTS adaptive_events(
          id TEXT PRIMARY KEY,owner TEXT,space TEXT,family TEXT,at TEXT,details_json TEXT);
        CREATE TABLE IF NOT EXISTS adaptive_procedures(
          owner TEXT,space TEXT,procedure TEXT,variant TEXT,steps_json TEXT,
          PRIMARY KEY(owner,space,procedure,variant));
        CREATE TABLE IF NOT EXISTS adaptive_procedure_outcomes(
          owner TEXT,space TEXT,id TEXT,procedure TEXT,variant TEXT,successful INTEGER,
          source TEXT,PRIMARY KEY(owner,space,id));
        ''')

    def _adaptation_event(self, owner, space, family, details):
        from .engine import utcnow
        self.db.execute('INSERT INTO adaptive_events VALUES(?,?,?,?,?,?)',
            (uuid.uuid4().hex,owner,space,family,utcnow(),json.dumps(details,sort_keys=True,allow_nan=False)))

    def adaptive_status(self, owner, family, *, space='default'):
        owner,space,family=[_valid_atom(v,'identifier') for v in (owner,space,family)]
        with self.lock:
            head=self.db.execute('SELECT version,previous,cutoff FROM adaptive_heads WHERE owner=? AND space=? AND family=?',(owner,space,family)).fetchone()
            events=self.db.execute('SELECT details_json FROM adaptive_events WHERE owner=? AND space=? AND family=? ORDER BY rowid DESC LIMIT 20',(owner,space,family)).fetchall()
        return {'head':dict(head) if head else None,'events':[json.loads(r[0]) for r in events],
                'code_modified':False,'execution_authorized':False}

    def refresh_adaptive_world(self, owner, family, samples, *, as_of, space='default'):
        """One bounded host ingestion cycle; fresh test labels cannot be reused.

        Initial model needs existing temporal validation. Replacements must also
        beat the incumbent on the same fresh chronological holdout, per action.
        Rejected evaluations are consumed too, preventing repeated test tuning.
        """
        from .calibrated import train_temporal
        from .dynamics import _predict
        from .engine import WorldCoreError, _when, utcnow
        owner,space,family=[_valid_atom(v,'identifier') for v in (owner,space,family)]
        cutoff=_when(as_of)
        if cutoff>utcnow():raise WorldCoreError('training cutoff cannot be in the future')
        bundle=train_temporal(samples,as_of=cutoff)
        entries=bundle['actions']
        with self._transaction():
            head=self.db.execute('SELECT * FROM adaptive_heads WHERE owner=? AND space=? AND family=?',(owner,space,family)).fetchone()
            incumbent=self.db.execute('SELECT * FROM calibrated_dynamics WHERE owner=? AND space=? AND family=? '+
                ('AND version=?' if head else 'ORDER BY version DESC LIMIT 1'),
                (owner,space,family,head['version']) if head else (owner,space,family)).fetchone()
            prior=json.loads(incumbent['bundle_json']) if incumbent else None
            last_cutoff=head['cutoff'] if head else (prior['as_of'] if prior else None)
            if last_cutoff and cutoff<=last_cutoff:return {'status':'deferred','reason':'need_later_cutoff'}
            valid={k:v for k,v in entries.items() if v['status']=='validated'}
            rows={r['sample_id']:r for r in samples if r.get('source')=='observed'}
            ids=[identifier for v in entries.values() for identifier in v.get('test_ids',[])]
            if any(self.db.execute('SELECT 1 FROM adaptive_evaluations WHERE owner=? AND space=? AND family=? AND sample_id=?',
                                  (owner,space,family,i)).fetchone() for i in ids):
                return {'status':'deferred','reason':'evaluation_already_consumed'}
            if last_cutoff and any(_when(rows[i]['before_at'])<=last_cutoff for i in ids):
                return {'status':'deferred','reason':'holdout_must_follow_previous_cutoff'}
            def consume_evaluation():
                for identifier in ids:self.db.execute('INSERT INTO adaptive_evaluations VALUES(?,?,?,?)',(owner,space,family,identifier))
                if not head:
                    self.db.execute('INSERT INTO adaptive_heads VALUES(?,?,?,?,?,?)',
                        (owner,space,family,incumbent['version'] if incumbent else None,None,cutoff))
                else:self.db.execute('UPDATE adaptive_heads SET cutoff=? WHERE owner=? AND space=? AND family=?',(cutoff,owner,space,family))
            def reject(reason):
                if ids:consume_evaluation()
                result={'status':'rejected','reason':reason}
                self._adaptation_event(owner,space,family,result)
                return result
            if not valid:return reject('no_validated_actions')
            if any(v['status']!='validated' for v in entries.values()):return reject('partial_action_validation')
            comparisons={};accepted=True
            if prior:
                old_actions={k:v for k,v in prior['actions'].items() if v['status']=='validated'}
                if not set(old_actions)<=set(valid):return reject('would_remove_validated_action')
                for action,old in old_actions.items():
                    if old['model']['keys']!=valid[action]['model']['keys']:
                        return reject('replacement_state_schema_differs')
                    held=[rows[i] for i in valid[action]['test_ids']]
                    try:
                        errors=[statistics.fmean(abs(_predict(old['model'],r['before'])[k]-r['after'][k])
                                for k in old['model']['keys']) for r in held]
                        hits=sum(all(abs(_predict(old['model'],r['before'])[k]-r['after'][k])<=old['radius'][k]
                                 for k in old['model']['keys']) for r in held)
                    except KeyError:raise WorldCoreError('replacement state schema differs')
                    old_mae=statistics.fmean(errors);new=valid[action]
                    better=new['mae']<old_mae*.95 and new['validation_coverage']>=hits/len(held)
                    comparisons[action]={'incumbent_mae':old_mae,'candidate_mae':new['mae'],
                                         'incumbent_coverage':hits/len(held),'accepted':better}
                    accepted=accepted and better
            consume_evaluation()
            if not accepted:
                result={'status':'rejected','reason':'no_demonstrated_improvement','comparison':comparisons}
                self._adaptation_event(owner,space,family,result)
                return result
            version=self.db.execute('SELECT COALESCE(MAX(version),0)+1 FROM calibrated_dynamics WHERE owner=? AND space=? AND family=?',(owner,space,family)).fetchone()[0]
            self.db.execute('INSERT INTO calibrated_dynamics VALUES(?,?,?,?,?,?)',
                (owner,space,family,version,utcnow(),json.dumps(bundle,sort_keys=True,allow_nan=False)))
            self.db.execute('UPDATE adaptive_heads SET version=?,previous=? WHERE owner=? AND space=? AND family=?',
                (version,incumbent['version'] if incumbent else None,owner,space,family))
            result={'status':'promoted','version':version,'previous':incumbent['version'] if incumbent else None,
                    'comparison':comparisons,'dataset_sha256':bundle['dataset_sha256'],'causal_claim':False}
            self._adaptation_event(owner,space,family,result)
            return result

    def review_adaptive_world(self, owner, family, *, space='default'):
        """Rollback/suspend on ten or more verified failures with low coverage.

        This runs automatically after host-verified outcome resolution. Older
        predictions keep their original model version even after a rollback.
        """
        from .calibrated import wilson
        owner,space,family=[_valid_atom(v,'identifier') for v in (owner,space,family)]
        with self._transaction():
            return self._review_adaptive_world_locked(owner,family,space=space)

    def _review_adaptive_world_locked(self, owner, family, *, space):
        from .calibrated import wilson
        head=self.db.execute('SELECT * FROM adaptive_heads WHERE owner=? AND space=? AND family=?',(owner,space,family)).fetchone()
        if not head or head['version'] is None:return {'status':'inactive'}
        bundle=json.loads(self.db.execute('SELECT bundle_json FROM calibrated_dynamics WHERE owner=? AND space=? AND family=? AND version=?',
                          (owner,space,family,head['version'])).fetchone()[0])
        for action,entry in bundle['actions'].items():
            rows=self.db.execute("SELECT covered FROM calibrated_forecasts WHERE owner=? AND space=? AND family=? AND version=? AND source='host_verified' AND covered IS NOT NULL AND json_extract(prediction_json,'$.action')=? ORDER BY observed_at DESC,id DESC LIMIT 20",
                                 (owner,space,family,head['version'],action)).fetchall()
            if len(rows)<10 or wilson(sum(r[0] for r in rows),len(rows))[1]>=entry.get('coverage_target',.8):continue
            previous=head['previous']
            self.db.execute('UPDATE adaptive_heads SET version=?,previous=NULL WHERE owner=? AND space=? AND family=?',(previous,owner,space,family))
            result={'status':'rolled_back' if previous is not None else 'suspended',
                    'failed_version':head['version'],'version':previous,'action':action,'verified_outcomes':len(rows)}
            self._adaptation_event(owner,space,family,result)
            return result
        return {'status':'unchanged','version':head['version']}


    def register_adaptive_procedure(self, owner, procedure, variant, steps, *, space='default'):
        from .engine import WorldCoreError, _text
        owner,space,procedure,variant=[_valid_atom(v,'identifier') for v in (owner,space,procedure,variant)]
        if not isinstance(steps,list) or not 1<=len(steps)<=12:raise WorldCoreError('procedure needs 1..12 text steps')
        raw=json.dumps([_text(step,'step',500) for step in steps],ensure_ascii=False)
        with self._transaction():
            old=self.db.execute('SELECT steps_json FROM adaptive_procedures WHERE owner=? AND space=? AND procedure=? AND variant=?',(owner,space,procedure,variant)).fetchone()
            if old:
                if old[0]!=raw:raise WorldCoreError('procedure variant is immutable')
                return {'status':'unchanged'}
            self.db.execute('INSERT INTO adaptive_procedures VALUES(?,?,?,?,?)',(owner,space,procedure,variant,raw))
        return {'status':'registered','execution_authorized':False}

    def record_adaptive_procedure_outcome(self, owner, procedure, variant, identifier, successful, *, space='default', source='user_reported'):
        from .engine import WorldCoreError
        owner,space,procedure,variant,identifier=[_valid_atom(v,'identifier') for v in (owner,space,procedure,variant,identifier)]
        if type(successful) is not bool or source not in ('user_reported','host_verified'):raise WorldCoreError('invalid outcome')
        with self._transaction():
            if not self.db.execute('SELECT 1 FROM adaptive_procedures WHERE owner=? AND space=? AND procedure=? AND variant=?',(owner,space,procedure,variant)).fetchone():raise WorldCoreError('procedure variant not found')
            old=self.db.execute('SELECT procedure,variant,successful,source FROM adaptive_procedure_outcomes WHERE owner=? AND space=? AND id=?',(owner,space,identifier)).fetchone()
            values=(procedure,variant,int(successful),source)
            if old:
                if tuple(old)!=values:raise WorldCoreError('procedure outcome is immutable')
            else:self.db.execute('INSERT INTO adaptive_procedure_outcomes VALUES(?,?,?,?,?,?,?)',(owner,space,identifier,*values))
        return self.recommend_adaptive_procedure(owner,procedure,space=space)

    def recommend_adaptive_procedure(self, owner, procedure, *, space='default'):
        from .calibrated import wilson
        owner,space,procedure=[_valid_atom(v,'identifier') for v in (owner,space,procedure)]
        with self._snapshot():
            variants=self.db.execute('SELECT variant,steps_json FROM adaptive_procedures WHERE owner=? AND space=? AND procedure=?',(owner,space,procedure)).fetchall()
            candidates=[]
            for variant in variants:
                rows=self.db.execute("SELECT successful FROM adaptive_procedure_outcomes WHERE owner=? AND space=? AND procedure=? AND variant=? AND source='host_verified' ORDER BY rowid DESC LIMIT 40",(owner,space,procedure,variant['variant'])).fetchall()
                bounds=wilson(sum(r[0] for r in rows),len(rows))
                if len(rows)>=20 and bounds[0]>=.7:
                    candidates.append({'variant':variant['variant'],'steps':json.loads(variant['steps_json']),
                                       'observations':len(rows),'success_wilson_95':bounds})
        if not candidates:return {'status':'abstain','reason':'insufficient_verified_success','execution_authorized':False}
        best=max(candidates,key=lambda r:(r['success_wilson_95'][0],r['variant']))
        return {'status':'recommended',**best,'execution_authorized':False,'steps_are_data':True}
