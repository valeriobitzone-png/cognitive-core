"""WHAT IF: safe, bounded, versioned multi-scenario reasoning over observed state.

Universal *interface*, not a universal simulator. Distinguishes deterministic
assumptions from held-out validated dynamics and observational frequencies.
No simulation implies authority to act; the invoking host controls permissions.
"""
from __future__ import annotations
import json
import math
import uuid
from collections import deque
from .worldmodel import _valid_atom


def _number(x):
    return type(x) in (int, float) and math.isfinite(x)


class WhatIfMixin:
    def _init_whatif_schema(self):
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS whatif_runs(
         id TEXT PRIMARY KEY, owner TEXT NOT NULL, space TEXT NOT NULL,
         created_at TEXT NOT NULL, question TEXT NOT NULL, result_json TEXT NOT NULL,
         status TEXT NOT NULL DEFAULT 'unresolved', selected TEXT,
         observed_json TEXT, observed_at TEXT, verification_source TEXT);
        CREATE INDEX IF NOT EXISTS whatif_runs_scope ON whatif_runs(owner,space,created_at);
        ''')

    def compare_futures(self, owner, question, scenarios, *, space='default', objectives=None,
                        failure_conditions=None, persist=True):
        """Compare 2..8 futures, without tool execution or automatic decisions.

        Scenarios: {id, kind:'state'|'world', actions:[...], environment?, before?, family?}.
        Objectives: {key, direction:'maximize'|'minimize', scale:positive number,weight:0..10}.
        'score' is only relative to DECLARED user preferences, not likelihood or truth.
        """
        from .engine import WorldCoreError, _text, _json, utcnow
        owner, space = _valid_atom(owner,'owner'),_valid_atom(space,'space')
        question = _text(question,'question',1000)
        if not isinstance(scenarios,list) or not 2<=len(scenarios)<=8:
            raise WorldCoreError('WHAT IF requires 2..8 alternatives')
        if not isinstance(objectives,list) or len(objectives)>8:
            raise WorldCoreError('objectives must be a list of <=8 measurable goals')
        if failure_conditions is None: failure_conditions=[]
        if not isinstance(failure_conditions,list) or len(failure_conditions)>8:
            raise WorldCoreError('invalid failure conditions')
        for rule in objectives:
            if not isinstance(rule,dict) or not isinstance(rule.get('key'),str) or rule.get('direction') not in ('maximize','minimize') or not _number(rule.get('scale')) or rule['scale']<=0 or not _number(rule.get('weight',1)) or not 0<=rule.get('weight',1)<=10:
                raise WorldCoreError('invalid measurable objective')
        for rule in failure_conditions:
            if not isinstance(rule,dict) or not isinstance(rule.get('key'),str) or rule.get('op') not in ('>','>=','<','<=','==','!=') or not _number(rule.get('threshold')):
                raise WorldCoreError('invalid failure threshold')
        ids=set(); items=[]
        base_state=self.state(owner,space=space)
        for entry in scenarios:
            if not isinstance(entry,dict):raise WorldCoreError('invalid scenario')
            sid=_valid_atom(entry.get('id'),'scenario id')
            if sid in ids:raise WorldCoreError('duplicate scenario id')
            ids.add(sid)
            kind=entry.get('kind','state')
            actions=entry.get('actions')
            if kind=='state':
                if not isinstance(actions,list) or len(actions)>8:
                    raise WorldCoreError('state scenario allows <=8 operations')
                prediction=self.simulate(owner,actions,space=space)
                resulting=prediction['predicted']
                status='simulated'
                evidence={'type':'operator_assumptions','mode':'deterministic_rules',
                          'warning':'A set/add/delete is an assumed effect, not an empirical prediction'}
                baseline=base_state
            elif kind=='calibrated_world':
                family=_valid_atom(entry.get('family'),'family')
                before=entry.get('before')
                if not isinstance(before,dict) or not isinstance(actions,list) or len(actions)!=1:
                    raise WorldCoreError('calibrated scenario requires before state and exactly one action; multi-step intervals are not calibrated')
                prediction=self.predict_calibrated_world(owner,family,before,actions[0],space=space,
                    min_confidence=entry.get('min_confidence',.5),max_width=entry.get('max_width'))
                status='simulated' if prediction['status']=='predicted' else 'abstain'
                resulting=prediction.get('state')
                baseline=before
                evidence={'type':'temporally_validated_prediction','prediction':prediction,
                          'warning':'Calibrated conditional prediction, not proof of a causal counterfactual'}
            elif kind=='world':
                environment=_valid_atom(entry.get('environment'),'environment')
                before=entry.get('before')
                if not isinstance(before,dict) or not isinstance(actions,list) or not 1<=len(actions)<=8 or any(not isinstance(a,str) for a in actions):
                    raise WorldCoreError('world scenario needs before state and 1..8 action names')
                prediction=self.simulate_hybrid_world(owner,environment,before,actions,space=space,family=entry.get('family'))
                status=prediction['status']
                resulting=prediction['trajectory'][-1]['state'] if status=='simulated' else None
                baseline=before
                evidence={'type':'estimated_dynamics','model_trace':prediction.get('trajectory',[]),
                          'warning':'Model uncertainty compounds; action choices are not interventions proven causal'}
            else:
                raise WorldCoreError('unsupported scenario kind')
            score=None; coverage=0; deltas=[]; failures=[]
            if resulting is not None:
                for objective in objectives:
                    key=objective['key'];a=baseline.get(key);b=resulting.get(key)
                    if not _number(a) or not _number(b):continue
                    sign=1 if objective['direction']=='maximize' else -1
                    change=sign*(b-a)/objective['scale']*objective.get('weight',1)
                    # Do not let unbounded user-provided state result in runaway score.
                    change=max(-1000,min(1000,change))
                    deltas.append({'key':key,'from':a,'to':b,'weighted_delta':round(change,6)})
                    coverage+=1
                if objectives and coverage==len(objectives):score=round(sum(x['weighted_delta'] for x in deltas),6)
                for rule in failure_conditions:
                    value=resulting.get(rule['key'])
                    if not _number(value):continue
                    op=rule['op'];t=rule['threshold']
                    triggered={'>':value>t,'>=':value>=t,'<':value<t,'<=':value<=t,'==':value==t,'!=':value!=t}[op]
                    if triggered:failures.append({'key':rule['key'],'op':op,'threshold':t,'observed_in_scenario':value})
            items.append({'id':sid,'status':status,'kind':kind,'projected_state':resulting,
                          'score':score,'objective_coverage':coverage,'objective_deltas':deltas,
                          'failure_futures':failures,'evidence':evidence,
                          'unknowns':[] if status=='simulated' else [prediction.get('reason','insufficient_model_evidence')],
                          'action_executed':False})
        # Reject ranking when all evidence is merely assumptions or one scenario is unknown.
        comparable=bool(objectives) and all(x['score'] is not None for x in items)
        # Point estimates alone cannot establish that competing uncertain futures differ.
        # A candidate needs a full decision rule over interval bounds, not just a higher mean.
        ranked=sorted(items,key=lambda x:x['score'],reverse=True) if comparable else []
        result={'question':question,'scenarios':items,'ranking':[x['id'] for x in ranked],
                'candidate_for_review':None,
                'confidence_gate':'automatic_candidate_abstained_without_interval_dominance_rule',
                'ranking_basis':'user_declared_objectives_not_calibrated_probability',
                'decision':'human_review_required','action_executed':False,
                'authority':{'capability':'simulation_only','host_approval_required':True,'externally_permitted':'unknown'},
                'epistemic_warning':'What-if cannot prove counterfactual causality. Unknowns, confounders and model error remain.',
                'source_state':'snapshot_at_run_time'}
        if len(_json(result))>39_500:raise WorldCoreError('what-if result exceeds store budget')
        if persist:
            run_id=uuid.uuid4().hex
            with self._transaction():
                self.db.execute('''INSERT INTO whatif_runs(id,owner,space,created_at,question,result_json)
                    VALUES (?,?,?,?,?,?)''',(run_id,owner,space,utcnow(),question,_json(result)))
            result['run_id']=run_id
        return result

    def whatif_history(self,owner,*,space='default',limit=20):
        from .engine import WorldCoreError
        if type(limit)!=int or not 1<=limit<=50:raise WorldCoreError('invalid history limit')
        with self.lock:
            rows=self.db.execute('''SELECT id,created_at,question,status,selected,observed_at,verification_source
                 FROM whatif_runs WHERE owner=? AND space=? ORDER BY created_at DESC LIMIT ?''',
                 (_valid_atom(owner,'owner'),_valid_atom(space,'space'),limit)).fetchall()
            return [dict(r) for r in rows]

    def verify_whatif(self,owner,run_id,selected,observed,*,space='default',source='user_reported'):
        """Immutable first outcome. Never relabel a simulated trajectory as confirmed causal effect."""
        from .engine import WorldCoreError, _json, utcnow
        owner,space,run_id,selected=(_valid_atom(x,'identifier') for x in (owner,space,run_id,selected))
        if source not in ('user_reported','host_verified'):
            raise WorldCoreError('unsupported verification source')
        raw=_json(observed)
        if not isinstance(observed,dict) or len(raw)>5000:raise WorldCoreError('observed must be a bounded state')
        with self._transaction():
            row=self.db.execute('''SELECT * FROM whatif_runs WHERE owner=? AND space=? AND id=?''',(owner,space,run_id)).fetchone()
            if row is None:raise WorldCoreError('what-if run not found')
            data=json.loads(row['result_json'])
            variants={x['id']:x for x in data['scenarios']}
            if selected not in variants:raise WorldCoreError('scenario not in run')
            if row['status']!='unresolved':
                if row['selected']==selected and row['observed_json']==raw and row['verification_source']==source:
                    return {'status':'unchanged','run_id':run_id}
                raise WorldCoreError('what-if outcome is immutable')
            predicted=variants[selected]['projected_state'];errors={}
            if isinstance(predicted,dict):
                for key,value in predicted.items():
                    if _number(value) and _number(observed.get(key)):
                        errors[key]=round(abs(value-observed[key]),8)
            self.db.execute('''UPDATE whatif_runs SET status='verified',selected=?,observed_json=?,observed_at=?,verification_source=? WHERE id=?''',
                            (selected,raw,utcnow(),source,run_id))
        return {'status':'verified','run_id':run_id,'source':source,'absolute_errors':errors,
                'causal_conclusion':False,'note':'Observed outcome is not proof of alternative unrealized futures'}


    def whatif_backcast(self, owner, question, target, candidate_actions, *, space='default',
                        max_depth=4, max_states=1500, persist=False):
        """Search bounded deterministic plans backwards from a declared goal.

        This is a finite action-space search over ASSUMED set/add/delete effects,
        NOT a claim of empirical causality or any permission to execute.
        Candidate actions supplied by a host are untrusted and never dispatched.
        """
        from .engine import WorldCoreError, _text, _json
        owner,space=_valid_atom(owner,'owner'),_valid_atom(space,'space')
        question=_text(question,'question',1000)
        if not isinstance(target,dict) or not 1<=len(target)<=5:
            raise WorldCoreError('target must have 1..5 bounded numeric conditions')
        allowed={'<','<=','>','>=','==','!='}
        for key,rule in target.items():
            _valid_atom(key,'goal state key')
            if not isinstance(rule,dict) or rule.get('op') not in allowed or not _number(rule.get('value')):
                raise WorldCoreError('invalid goal condition')
        if not isinstance(candidate_actions,list) or not 1<=len(candidate_actions)<=9:
            raise WorldCoreError('1..9 candidate actions required')
        if type(max_depth)!=int or not 1<=max_depth<=5 or type(max_states)!=int or not 2<=max_states<=2000:
            raise WorldCoreError('invalid search budget')
        valid_actions=[]
        for act in candidate_actions:
            if not isinstance(act,dict) or act.get('op') not in ('add','set','delete') or not isinstance(act.get('key'),str):
                raise WorldCoreError('unsupported action: only deterministic state operations')
            _valid_atom(act['key'],'state key')
            if act['op']=='add' and not _number(act.get('value')):
                raise WorldCoreError('add requires finite numeric value')
            if act['op']=='set': _json(act.get('value'))
            if act['op']=='delete' and 'value' in act: raise WorldCoreError('delete action cannot carry a value')
            if set(act)-{'op','key','value','if_equals'}: raise WorldCoreError('unknown action parameter')
            _json(act)
            valid_actions.append(act)
        start=self.state(owner,space=space)
        def achieved(state):
            for key, rule in target.items():
                n=state.get(key)
                if not _number(n):return False
                v=rule['value'];op=rule['op']
                if not {'<':n<v,'<=':n<=v,'>':n>v,'>=':n>=v,'==':n==v,'!=':n!=v}[op]:return False
            return True
        q=deque([(start,[])])
        known={_json(start)}
        seen=0;found=None;verified=False
        # No database writes. Reuse the production simulator to prove the proposed
        # plan is consistent with the current state and precondition semantics.
        while q and seen<max_states:
            state,plan=q.popleft();seen+=1
            if achieved(state):
                predicted=self.simulate(owner,plan,space=space)
                verified=predicted['predicted']==state
                if not verified:raise WorldCoreError('planner/simulator mismatch')
                found={'actions':plan,'projected_state':state,'steps':len(plan)}
                break
            if len(plan)>=max_depth:continue
            for action in valid_actions:
                key=action['key'];old=state.get(key)
                if 'if_equals' in action and old!=action['if_equals']:continue
                updated=dict(state)
                if action['op']=='add':
                    if not _number(old):continue
                    result=old+action['value']
                    if not math.isfinite(result):continue
                    updated[key]=result
                elif action['op']=='set':updated[key]=action['value']
                else:updated.pop(key,None)
                if updated==state:continue
                identifier=_json(updated)
                if identifier in known:continue
                known.add(identifier)
                q.append((updated,plan+[action]))
                if len(known)>=max_states*5:break
        answer={'status':'assumed_plan_found' if found else 'not_found_within_budget',
                'question':question,'target':target,'plan':found,
                'searched_states':seen,'search_budget':max_states,
                'method':'bounded_deterministic_search_no_causal_guarantee',
                'simulation_crosschecked':verified,'action_executed':False,
                'host_approval_required':True,
                'warning':'A proposed path is a hypothetical plan under declared rules, not proof it will work in reality.'}
        if persist and found:
            alternatives=[{'id':'plan','kind':'state','actions':found['actions']},
                          {'id':'no_action','kind':'state','actions':[]}]
            result=self.compare_futures(owner,question,alternatives,space=space,objectives=[])
            answer['run_id']=result['run_id']
        return answer

    def whatif_replay(self,owner,run_id,*,space='default'):
        """Immutable decision replay: predicted vs actual, never invented outcomes for alternatives."""
        from .engine import WorldCoreError
        owner,space,run_id=(_valid_atom(x,'identifier') for x in (owner,space,run_id))
        with self.lock:
            row=self.db.execute("SELECT result_json,status,selected,observed_json,verification_source,observed_at "
                   "FROM whatif_runs WHERE owner=? AND space=? AND id=?",(owner,space,run_id)).fetchone()
        if row is None:raise WorldCoreError('what-if run not found')
        past=json.loads(row['result_json']);selected=row['selected'];observed=json.loads(row['observed_json']) if row['observed_json'] else None
        chosen=next((x for x in past['scenarios'] if x['id']==selected),None) if selected else None
        residuals={}
        if observed is not None and chosen and isinstance(chosen['projected_state'],dict):
            for key,expected in chosen['projected_state'].items():
                actual=observed.get(key)
                if _number(actual) and _number(expected):
                    residuals[key]={'expected':expected,'actual':actual,'error':round(actual-expected,8)}
        return {'run_id':run_id,'status':row['status'],'selected':selected,
                'original_question':past['question'], 'alternatives':[x['id'] for x in past['scenarios']],
                'verified_source':row['verification_source'],'verified_at':row['observed_at'],
                'chosen_residuals':residuals,'unrealized_alternatives':'not_observable',
                'causal_claim':False,'action_executed':False,
                'warning':'Only the selected outcome was observed. Unchosen futures remain hypothetical.'}

    def whatif_stress_test(self,owner,question,plans,shocks,*,space='default',objectives=None):
        """Probe declared plans under adverse exogenous assumptions, without state writes.

        `shocks` are hypothetical changes to snapshot numeric state, not observed
        external events. Returns worst-case scores; NEVER calibrated probabilities.
        """
        from .engine import WorldCoreError, _json, _text
        owner,space=_valid_atom(owner,'owner'),_valid_atom(space,'space')
        question=_text(question,'question',1000)
        if not isinstance(plans,list) or not 2<=len(plans)<=6 or not isinstance(shocks,list) or not 1<=len(shocks)<=8:
            raise WorldCoreError('stress test needs 2..6 plans and 1..8 shocks')
        objectives=objectives or []
        if not isinstance(objectives,list) or not 1<=len(objectives)<=5:
            raise WorldCoreError('requires 1..5 measured objectives')
        for rule in objectives:
            if not isinstance(rule,dict) or not isinstance(rule.get('key'),str) or rule.get('direction') not in ('minimize','maximize') or not _number(rule.get('scale')) or rule['scale']<=0:
                raise WorldCoreError('invalid stress objective')
            _valid_atom(rule['key'],'objective key')
        original=self.state(owner,space=space)
        result=[];used=set();shock_ids=set()
        for change in shocks:
            if not isinstance(change,dict) or not isinstance(change.get('id'),str) or not isinstance(change.get('changes'),dict):
                raise WorldCoreError('invalid shock')
            shockid=_valid_atom(change['id'],'shock id')
            if shockid in shock_ids:raise WorldCoreError('duplicate shock id')
            shock_ids.add(shockid)
            if len(change['changes'])>8:raise WorldCoreError('too many changed variables')
            for key,value in change['changes'].items():
                _valid_atom(key,'shock state key')
                if not _number(value):raise WorldCoreError('shocks must be finite numbers')
            _json(change)
        for plan in plans:
            if not isinstance(plan,dict) or not isinstance(plan.get('id'),str) or not isinstance(plan.get('actions'),list) or len(plan['actions'])>8:
                raise WorldCoreError('invalid stress plan')
            identifier=_valid_atom(plan['id'],'plan id')
            if identifier in used:raise WorldCoreError('duplicate plan id')
            used.add(identifier)
            # Validate supported action types, without ever executing a host tool.
            actions=plan['actions']
            for a in actions:
                if not isinstance(a,dict) or a.get('op') not in ('add','set','delete') or not isinstance(a.get('key'),str):
                    raise WorldCoreError('unsupported stress operation')
                _valid_atom(a['key'],'action key')
                if a['op']=='add' and not _number(a.get('value')):
                    raise WorldCoreError('invalid numeric delta')
                if a['op']=='set':_json(a.get('value'))
                if set(a)-{'op','key','value','if_equals'}:raise WorldCoreError('unknown action fields')
            outcomes=[]
            for shock in shocks:
                initial={**original,**shock['changes']}
                predicted=dict(initial)
                known=True
                for a in actions:
                    key=a['key'];old=predicted.get(key)
                    if 'if_equals' in a and old!=a['if_equals']:continue
                    if a['op']=='set':predicted[key]=a['value']
                    elif a['op']=='delete':predicted.pop(key,None)
                    else:
                        if not _number(old):known=False;break
                        new=old+a['value']
                        if not math.isfinite(new):known=False;break
                        predicted[key]=new
                deltas=[]
                if known:
                    for obj in objectives:
                        x=initial.get(obj['key']);y=predicted.get(obj['key'])
                        if not _number(x) or not _number(y):known=False;break
                        sign=1 if obj['direction']=='maximize' else -1
                        deltas.append(max(-1000,min(1000,sign*(y-x)/obj['scale'])))
                outcomes.append({'shock_id':shock['id'],'score':round(sum(deltas),6) if known else None,
                                 'predicted_state':predicted if known else None,
                                 'status':'assumed_effect' if known else 'abstain'})
            scores=[x['score'] for x in outcomes]
            result.append({'plan_id':identifier,'cases':outcomes,'worst_case_score':min(scores) if all(x is not None for x in scores) else None})
        comparable=all(x['worst_case_score'] is not None for x in result)
        rank=sorted(result,key=lambda x:x['worst_case_score'],reverse=True) if comparable else []
        return {'question':question,'plans':result,'robustness_order':[x['plan_id'] for x in rank],
                'candidate_for_review':rank[0]['plan_id'] if rank else None,
                'basis':'hypothetical_shocks_not_probabilities', 'action_executed':False,
                'host_approval_required':True,'causal_claim':False,
                'warning':'Scores assume supplied effects and shocks are valid. Unknown external consequences are not simulated.'}
