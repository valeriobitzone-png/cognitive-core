"""Browser/app interaction learning from observed, consented UI transitions.

The core learns label/goal affordances and state changes, NOT an arbitrary browser
world model. Browser execution is strictly in an explicit offline evaluation host;
production is recommendation-only. No arbitrary URLs, credentials, or navigation.
"""
from __future__ import annotations
import json
import math
import re
from .worldmodel import _valid_atom

ALIASES={'create':'add','new':'add','make':'add','insert':'add','task':'item','todo':'item',
         'event':'meeting','appointment':'meeting','schedule':'meeting','remove':'delete',
         'erase':'delete','trash':'delete','discard':'delete','save':'submit','send':'submit'}

def tokens(s):
    if not isinstance(s,str):return set()
    return {ALIASES.get(w,w) for w in re.findall(r'\b\w+\b',s.lower(),re.UNICODE)}

def element_id(e):
    return str(e.get('label','')).strip()[:120]

class BrowserLearningMixin:
    def _init_browser_learning_schema(self):
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS ui_learning (
             owner TEXT NOT NULL,space TEXT NOT NULL,app TEXT NOT NULL,
             goal TEXT NOT NULL,label TEXT NOT NULL,role TEXT NOT NULL,
             before_json TEXT NOT NULL,after_json TEXT NOT NULL,
             successful INTEGER NOT NULL,at TEXT NOT NULL);
        ''')

    def record_ui_transition(self,owner,app,goal,element,before,after,successful,*,space='default'):
        from .engine import WorldCoreError,_json,utcnow
        owner,space,app=[_valid_atom(x,'identifier') for x in (owner,space,app)]
        if not isinstance(goal,str) or not 1<=len(goal)<=150:raise WorldCoreError('invalid goal')
        if not isinstance(element,dict) or not isinstance(element.get('label'),str):raise WorldCoreError('invalid element')
        if type(successful)!=bool:raise WorldCoreError('outcome must be explicitly verified')
        label=element['label'][:120]
        role=str(element.get('role','unknown'))[:40]
        # Never persist input values, passwords, typed text, email or captured HTML.
        if not isinstance(before,dict) or not isinstance(after,dict) or len(before)>64 or len(after)>64:
            raise WorldCoreError('bounded structured observations required')
        safe_before={str(k)[:40]:v for k,v in before.items() if type(v) in (int,float,bool) and math.isfinite(v)}
        safe_after={str(k)[:40]:v for k,v in after.items() if type(v) in (int,float,bool) and math.isfinite(v)}
        with self._transaction():
            self.db.execute('INSERT INTO ui_learning VALUES(?,?,?,?,?,?,?,?,?,?)',
                (owner,space,app,goal,label,role,_json(safe_before),_json(safe_after),int(successful),utcnow()))
        return {'status':'learned','observed_effect':{k:safe_after[k]-safe_before[k] for k in safe_after if k in safe_before and type(safe_after[k]) in (int,float) and type(safe_before[k]) in (int,float)}}

    def predict_ui_effect(self,owner,goal,element,*,space='default',min_examples=3):
        """Estimate numerical state deltas from previous verified UI effects.

        Requires same normalized goal and semantically related action labels.
        Abstains if effects are inconsistent or unavailable; prediction only.
        """
        from .engine import WorldCoreError
        owner,space=[_valid_atom(x,'identifier') for x in (owner,space)]
        if not isinstance(element,dict):raise WorldCoreError('invalid element')
        target=tokens(element.get('label',''));g=tokens(goal)
        with self.lock:
            rows=self.db.execute('SELECT goal,label,before_json,after_json,successful FROM ui_learning WHERE owner=? AND space=?',(owner,space)).fetchall()
        evidence=[]
        for r in rows:
            rt=tokens(r['goal']);lt=tokens(r['label'])
            if len(g&rt)/max(1,len(g|rt))<.5:continue
            if len(target&lt)/max(1,len(target|lt))<.45:continue
            if not r['successful']:continue
            before=json.loads(r['before_json']);after=json.loads(r['after_json'])
            changes={k:round(float(after[k])-float(before[k]),5) for k in before.keys() & after.keys()
                     if type(before[k]) in (int,float) and type(after[k]) in (int,float)}
            if changes:evidence.append(changes)
        if len(evidence)<min_examples:return {'status':'abstain','reason':'insufficient_transfer_evidence','n':len(evidence)}
        keys=set.intersection(*(set(e) for e in evidence))
        deltas={};disagreement={}
        for k in keys:
            vals=[e[k] for e in evidence]
            delta=sum(vals)/len(vals)
            spread=max(vals)-min(vals)
            if spread>max(.001,.25*abs(delta)):
                disagreement[k]=spread
            else:deltas[k]=round(delta,5)
        if not deltas:return {'status':'abstain','reason':'effect_not_stable','n':len(evidence),'disagreement':disagreement}
        return {'status':'predicted','numeric_state_delta':deltas,'n':len(evidence),
                'provenance':'observed_successful_ui_actions','reliability':'not probabilistically calibrated',
                'no_action_executed':True}

    def suggest_ui_action(self,owner,goal,elements,*,space='default',min_examples=2):
        from .engine import WorldCoreError
        owner,space=[_valid_atom(x,'identifier') for x in (owner,space)]
        if not isinstance(goal,str) or not goal.strip() or len(goal)>150:raise WorldCoreError('invalid goal')
        if not isinstance(elements,list) or len(elements)>150:raise WorldCoreError('too many elements')
        with self.lock:
            rows=self.db.execute('SELECT goal,label,role,successful FROM ui_learning WHERE owner=? AND space=? ORDER BY at DESC LIMIT 3000',(owner,space)).fetchall()
        goal_terms=tokens(goal)
        scored=[]
        for idx,el in enumerate(elements):
            if not isinstance(el,dict) or not isinstance(el.get('label'),str):continue
            if el.get('role') not in {'button','link','menuitem'}:continue
            text=element_id(el)
            if not text:continue
            label_terms=tokens(text)
            semantic=len(goal_terms & label_terms)/max(1,len(goal_terms | label_terms))
            neighbors=[]
            for r in rows:
                t=tokens(r['goal']);lt=tokens(r['label'])
                goal_sim=len(goal_terms&t)/max(1,len(goal_terms|t))
                action_sim=len(label_terms&lt)/max(1,len(label_terms|lt))
                weight=.7*goal_sim+.3*action_sim
                if goal_sim >= .3 and action_sim >= .2:neighbors.append((weight,bool(r['successful'])))
            total=sum(w for w,_ in neighbors)
            learned=sum(w*(1 if success else -1) for w,success in neighbors)/total if total else 0
            scored.append({'index':idx,'label':text,'role':el['role'],'score':round(.55*semantic+.45*learned,4),'support':len(neighbors),
                           'reason':'learned_ui_affordances_with_semantic_token_match'})
        scored.sort(key=lambda x:x['score'],reverse=True)
        if not scored or not any(x['support']>=min_examples and x['score']>.15 for x in scored):
            return {'status':'abstain','reason':'insufficient_observed_ui_evidence','candidates':scored[:3]}
        return {'status':'suggested','choice':scored[0],'alternatives':scored[1:4],
                'no_action_executed':True,'uncertainty':'not calibrated for arbitrary apps'}


def snapshot_page(page):
    """Bounded extraction of visible affordances from a Playwright Chromium page.

    Used only by an explicit test/authorized host with a user-visible browser.
    Element values, cookies, storage and passwords are never read.
    """
    data=page.locator('button,a,[role="button"],[role="menuitem"]').evaluate_all('''els => els.filter(e=>e.getClientRects().length).slice(0,150).map((e,i)=>({
      label:(e.getAttribute('aria-label')||e.textContent||'').trim().slice(0,120),
      role:e.getAttribute('role')||(e.tagName==='A'?'link':'button'),index:i
    }))''')
    return {'elements':data,'title':page.title()[:120]}
